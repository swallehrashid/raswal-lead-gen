# Raswal Lead Generator — Setup Checklist

Do these steps over the weekend so Sunday night's run produces Monday's list. Each step lists what to save as a **secret** (GitHub → repo → Settings → Secrets and variables → Actions).

---

## 1. GitHub (10 min)

- [ ] Create a **private** repo named `raswal-lead-generator`.
- [ ] Add a `docs/` folder containing `PROJECT_BRIEF.md`, `DAILY_PLAYBOOK.md` and `SETUP_CHECKLIST.md`.
- [ ] Open the repo in Claude Code and say: *"Read docs/PROJECT_BRIEF.md and build milestones M0–M5 in order."*
- [ ] Install the **GitHub mobile app**. You'll use it to re-run the nightly job if it ever fails.
- [ ] Notes on GitHub Actions:
  - Actions are on by default.
  - Private repos on GitHub Free get **2,000 minutes/month**. The pipeline needs about 800.

---

## 2. Google Cloud: Places API + PageSpeed Insights (20 min)

Your card is already on file, so the safety caps below are essential.

- [ ] Create a project named `raswal-leadgen`.
- [ ] Enable **Places API (New)**. Not the legacy "Places API".
- [ ] Enable **PageSpeed Insights API**.
- [ ] Create **two API keys**:
  - Key 1, restricted to *Places API (New)* only → secret `GOOGLE_PLACES_API_KEY`
  - Key 2, restricted to *PageSpeed Insights API* only → secret `PSI_API_KEY`
- [ ] **Quota cap:** IAM & Admin → Quotas → Places API (New) → set *Text Search requests per day* to **45**. This is the hard stop that prevents charges.
- [ ] **Budget alert:** Billing → Budgets & alerts → create a budget of **$1** with email alerts at 50% and 100%.
- [ ] **After the first test run**, check Billing → Reports and filter by SKU.
  - Usage should show under **"Places API Text Search Enterprise + Atmosphere"**.
  - That SKU has 1,000 free calls/month. The pipeline uses at most 900.
  - If it shows a different SKU, stop and tell Claude Code; the field mask needs fixing.

---

## 3. Gemini API (5 min)

- [ ] Go to Google AI Studio → **Get API key** → secret `GEMINI_API_KEY`.
- [ ] Set the secret `GEMINI_MODEL` to the current **Flash** model name shown in AI Studio.
- [ ] Notes on the free tier:
  - It allows a limited number of requests per minute and per day. The pipeline makes about 40–60 calls a night and throttles itself.
  - Prompts on the free tier may be used by Google. Only public business data goes in (names, reviews, website findings), never your clients' private data.

---

## 4. Supabase (15 min)

- [ ] Create a new **free** project named `raswal-leadgen`. Choose the region closest to Kenya that's offered (e.g. Frankfurt or London).
- [ ] Save these as secrets (Settings → API):
  - Project URL → `SUPABASE_URL`
  - `anon` key → `SUPABASE_ANON_KEY`
  - `service_role` key → `SUPABASE_SERVICE_ROLE_KEY`
    - **Never put this one in the dashboard or anywhere public.**
- [ ] Auth → Providers: **Email** on, magic link on. Turn **sign-ups off** once you've logged in for the first time.
- [ ] Auth → URL configuration: Site URL `https://leads.raswaltechsolutions.com`.
- [ ] Let Claude Code run the migrations in `supabase/migrations`. Set the admin email in `seed.sql` to `swallehmtawazo@gmail.com`.
- [ ] Storage: the private bucket `leadgen` (created by migration).
- [ ] Notes on the free plan:
  - The project **pauses after 7 days of inactivity**. The daily heartbeat workflow prevents that, including over the December break.
  - Limits are 500 MB database and 1 GB files. The nightly cleanup keeps usage well under both.

---

## 5. Nova Host: dashboard subdomain (15 min)

- [ ] **First, make sure raswaltechsolutions.com itself loads something credible.** Prospects will look you up before replying.
- [ ] In cPanel → **Domains/Subdomains**, create `leads.raswaltechsolutions.com`. Note its document root, e.g. `/home/USER/leads.raswaltechsolutions.com`.
- [ ] Run **SSL/TLS Status → AutoSSL** (Let's Encrypt) so the subdomain has HTTPS.
- [ ] In cPanel → **FTP Accounts**, create an FTP user **restricted to that subdomain folder only**. Save these as secrets:
  - `FTP_SERVER` (e.g. `ftp.raswaltechsolutions.com`)
  - `FTP_USERNAME`
  - `FTP_PASSWORD`
  - `FTP_DIR` (usually `/` for a folder-scoped user)
- [ ] For the demo repos later: check whether Nova Host supports a **wildcard subdomain** (`*.raswaltechsolutions.com`) with SSL.
  - If yes, every preview gets `{slug}.raswaltechsolutions.com` automatically.
  - If not, previews need a subdomain created per client, or a path like `preview.raswaltechsolutions.com/{slug}`.

---

## 6. WhatsApp (0114 129 809) (5 min)

- [ ] Check the profile name, photo and About text that a stranger sees. It should read naturally for "Swalleh from Raswal". Two options:
  - Name: **Swalleh Rashid**, with About: "Raswal Tech Solutions · SahilPay"
  - Or a clean personal photo
- [ ] Link **WhatsApp Web** on your desktop if you'll send from there.
- [ ] On your Android phone, open the dashboard in Chrome → menu → **Install app**. This is what makes the one-tap "Share image + caption" work.

---

## 7. Teaser templates (your part, 1–2 hours)

- [ ] For each of the five subcategories:
  - Copy the **hero section** of the finished website template into `teasers/web/<subcategory>/index.html`.
  - Copy the **three poster templates** into `teasers/content/<subcategory>/poster-1..3.html`.
- [ ] Tell Claude Code which placeholders to wire up (business name, area, logo, colours, hero image, headline, poster lines), following brief §13.
- [ ] **Rename the five subcategory keys** in `config/subcategories.yaml` if your template names differ from the working names: `property_agency`, `land_developers`, `construction`, `hardware_supplies`, `roofing_steel`.
- [ ] Add your existing clients' phone numbers (Premar, Jamar, Rawa, etc.) to the suppression list so they're never cold-messaged.

---

## 8. First runs

| When | Run | Check |
|---|---|---|
| Saturday | `python -m pipeline nightly --subcategory property_agency --dry-run` (≤ 5 Places calls) | The CSV in `out/` shows sensible businesses, gate reasons and scores |
| Saturday | Same command without `--dry-run`, with `--max-places-calls 10` | Leads appear in the dashboard and the teasers look right. Then check the SKU in Billing → Reports (§2). |
| Sunday ~21:30 | First scheduled run → Monday's list | The banner says the list is ready |
| Monday 08:30 | Follow `DAILY_PLAYBOOK.md` | — |

---

## All secrets in one place

| Secret | From |
|---|---|
| `GOOGLE_PLACES_API_KEY` | Google Cloud (§2) |
| `PSI_API_KEY` | Google Cloud (§2) |
| `GEMINI_API_KEY` | Google AI Studio (§3) |
| `GEMINI_MODEL` | Google AI Studio (§3) |
| `SUPABASE_URL` | Supabase (§4) |
| `SUPABASE_ANON_KEY` | Supabase (§4) |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase (§4) |
| `FTP_SERVER` | Nova Host (§5) |
| `FTP_USERNAME` | Nova Host (§5) |
| `FTP_PASSWORD` | Nova Host (§5) |
| `FTP_DIR` | Nova Host (§5) |


## 7. Apify (optional): "already advertising" + Instagram activity

1. Create an account at apify.com, open Settings → API & Integrations, copy the **personal API token**.
2. Settings → Limits: set a monthly spending limit of **$10**.
3. Local runs: add `APIFY_TOKEN=...` to `.env`. GitHub: repo → Settings → Secrets → `APIFY_TOKEN`.
4. First sync: GitHub → Actions → "Ad library sync" → Run workflow (or `python -m pipeline adlib-sync`). It then runs every Sunday 18:00 EAT.

Without a token nothing breaks: every lead's ads status stays "unknown" and you can set it by hand on the review card
(or check the Ad Library link on the card).
