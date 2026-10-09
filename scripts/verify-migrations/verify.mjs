// Apply supabase/migrations/*.sql and supabase/seed.sql to PGlite (Postgres compiled to WASM)
// with Supabase auth/storage stubs, then check RLS behaviour.
//
//   cd scripts/verify-migrations && npm install && npm run verify
//
// This verifies SQL syntax, ordering, idempotency and the RLS rules. It is not a full
// Supabase stack (no GoTrue, no Storage API); `supabase db push` remains the real test.

import { PGlite } from "@electric-sql/pglite";
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const migDir = join(root, "supabase", "migrations");
const seedPath = join(root, "supabase", "seed.sql");

const ADMIN = "swallehmtawazo@gmail.com";
let failures = 0;
const ok = (msg) => console.log(`  ok   ${msg}`);
const fail = (msg) => { failures++; console.log(`  FAIL ${msg}`); };
const expect = (cond, msg) => (cond ? ok(msg) : fail(msg));

async function expectError(db, sql, msg) {
  try { await db.exec(sql); fail(`${msg} (no error raised)`); }
  catch (e) { ok(`${msg} → ${String(e.message).split("\n")[0]}`); }
}

const db = new PGlite();
await db.exec(readFileSync(join(here, "supabase_stubs.sql"), "utf8"));

const files = readdirSync(migDir).filter((f) => f.endsWith(".sql")).sort();
console.log("Applying migrations:");
for (const f of files) {
  try { await db.exec(readFileSync(join(migDir, f), "utf8")); ok(f); }
  catch (e) { fail(`${f}: ${e.message}`); process.exit(1); }
}
console.log("Re-applying migrations (idempotency):");
for (const f of files) {
  try { await db.exec(readFileSync(join(migDir, f), "utf8")); ok(f); }
  catch (e) { fail(`${f} is not re-runnable: ${e.message}`); }
}
if (existsSync(seedPath)) {
  console.log("Applying seed.sql:");
  try { await db.exec(readFileSync(seedPath, "utf8")); ok("seed.sql"); }
  catch (e) { fail(`seed.sql: ${e.message}`); process.exit(1); }
} else {
  fail("supabase/seed.sql missing");
  await db.exec(`insert into settings (key, value) values ('admin', '{"admin_email": "${ADMIN}"}')`);
}

const asRole = async (role, email, fn) => {
  await db.exec(`set role ${role}`);
  const claims = email ? JSON.stringify({ email, role }) : JSON.stringify({ role });
  await db.query(`select set_config('request.jwt.claims', $1, false)`, [claims]);
  try { return await fn(); } finally { await db.exec("reset role"); }
};

console.log("Pipeline (service_role) writes:");
await asRole("service_role", null, async () => {
  await db.exec(`
    insert into businesses (place_id, name, name_norm, subcategory) values
      ('p1', 'Kilima Homes', 'kilima homes', 'property_agency'),
      ('p2', 'Tausi Builders', 'tausi builders', 'construction'),
      ('p3', 'Reserve One', 'reserve one', 'property_agency');
    insert into leads (place_id, list_date, subcategory, track, rank, status) values
      ('p1', '2026-10-12', 'property_agency', 'web', 1, 'shortlisted'),
      ('p3', '2026-10-12', 'property_agency', 'web', 21, 'reserve');
    insert into storage.objects (bucket_id, name, metadata) values ('leadgen', 'teasers/2026-10-12/x.jpg', '{"size": 120000}');
  `);
  const n = await db.query(`select increment_api_usage('2026-10', 'places', 'text_search_enterprise_atmosphere', 3) as c`);
  expect(n.rows[0].c === 3, "increment_api_usage counts");
  const n2 = await db.query(`select increment_api_usage('2026-10', 'places', 'text_search_enterprise_atmosphere', 2) as c`);
  expect(n2.rows[0].c === 5, "increment_api_usage accumulates");
});
const ev = await db.query(`select count(*)::int as c from events where type = 'created'`);
expect(ev.rows[0].c === 2, "insert trigger writes 'created' events");

console.log("Admin (authenticated, admin email):");
await asRole("authenticated", ADMIN, async () => {
  const r = await db.query(`select count(*)::int as c from leads`);
  expect(r.rows[0].c === 2, "admin can read leads");
  const s = await db.query(`select count(*)::int as c from settings`);
  expect(s.rows[0].c >= 1, "admin can read settings (no policy recursion)");
  await db.exec(`update leads set status = 'skipped', skip_reason = 'too_big' where place_id = 'p1'`);
  const p = await db.query(`select promote_reserve(id) as id from leads where place_id = 'p1'`);
  expect(p.rows[0].id !== null, "promote_reserve returns the promoted lead");
  const st = await db.query(`select status from leads where place_id = 'p3'`);
  expect(st.rows[0].status === "shortlisted", "reserve promoted to shortlisted");
  const u = await db.query(`select usage_stats() as u`);
  expect(u.rows[0].u.storage_bytes === 120000, "usage_stats sums storage object sizes");
  const o = await db.query(`select count(*)::int as c from storage.objects where bucket_id = 'leadgen'`);
  expect(o.rows[0].c === 1, "admin can see leadgen storage objects");
  await db.exec(`insert into suppression (phone_e164, reason) values ('+254700000001', 'opted_out')`);
  ok("admin can add suppression");
  await expectError(db, `select increment_api_usage('2026-10', 'places', 'x', 1)`, "admin cannot call pipeline-only increment_api_usage");
});
const sev = await db.query(`select count(*)::int as c from events where type = 'status'`);
expect(sev.rows[0].c === 2, "status changes are logged to events (skip + promotion)");

console.log("Another signed-in user:");
await asRole("authenticated", "someone@example.com", async () => {
  const r = await db.query(`select count(*)::int as c from leads`);
  expect(r.rows[0].c === 0, "non-admin sees no leads");
  const s = await db.query(`select count(*)::int as c from settings`);
  expect(s.rows[0].c === 0, "non-admin sees no settings");
  const o = await db.query(`select count(*)::int as c from storage.objects`);
  expect(o.rows[0].c === 0, "non-admin sees no storage objects");
  await expectError(db, `insert into suppression (phone_e164, reason) values ('+254700000002', 'manual')`, "non-admin insert is rejected");
  await expectError(db, `select usage_stats()`, "non-admin usage_stats is rejected");
  const up = await db.query(`update leads set notes = 'x' returning id`);
  expect(up.rows.length === 0, "non-admin update touches nothing");
});

console.log("Anonymous:");
await asRole("anon", null, async () => {
  await expectError(db, `select * from leads`, "anon cannot read leads");
  await expectError(db, `select * from settings`, "anon cannot read settings");
});

console.log(failures ? `\n${failures} check(s) FAILED` : "\nAll migration checks passed.");
process.exit(failures ? 1 : 0);
