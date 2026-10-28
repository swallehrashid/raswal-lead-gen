from datetime import date, datetime, timedelta, timezone

from pipeline.store import MemoryStore


def test_purge_removes_old_raw_and_files_of_dead_leads_only(cfg):
    s = MemoryStore()
    old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    new = datetime.now(timezone.utc).isoformat()
    s.tables["places_raw"][("a", old)] = {"place_id": "a", "payload": {}, "fetched_at": old}
    s.tables["places_raw"][("b", new)] = {"place_id": "b", "payload": {}, "fetched_at": new}
    today = date(2026, 12, 1)
    for i, (status, listed) in enumerate([("skipped", "2026-10-12"), ("won", "2026-10-12"), ("reserve", "2026-10-12"),
                                          ("skipped", "2026-11-25"), ("interested", "2026-10-12")]):
        path = f"teasers/x/{i}.jpg"
        s.files[path] = b"jpg"
        s.files[f"current/p{i}.jpg"] = b"jpg"
        s.tables["leads"][str(i)] = {"id": str(i), "place_id": f"p{i}", "status": status, "list_date": listed,
                                     "teaser_path": path, "brand": {}}
    res = s.purge(cfg, today)
    assert res["places_raw"] == 1 and ("b", new) in s.tables["places_raw"]
    kept = {k for k in s.files if k.startswith("teasers")}
    assert kept == {"teasers/x/1.jpg", "teasers/x/3.jpg", "teasers/x/4.jpg"}     # won, recent, interested
    assert "current/p0.jpg" not in s.files and "current/p1.jpg" in s.files


def test_unsent_leads_from_before_the_pivot_do_not_block_relisting(cfg):
    from datetime import date

    from pipeline.gates import GateContext
    from pipeline.store import _fill_contacted
    rows = [{"place_id": "old", "status": "shortlisted", "list_date": "2026-10-27", "sent_at": None},
            {"place_id": "new", "status": "shortlisted", "list_date": "2026-10-30", "sent_at": None},
            {"place_id": "sent_old", "status": "sent", "list_date": "2026-10-27", "sent_at": "2026-10-27T08:00:00+00:00"}]
    ctx = GateContext()
    _fill_contacted(ctx, cfg, date(2026, 11, 1), rows, lambda pid: None)
    assert "old" not in ctx.listed_place_ids and "new" in ctx.listed_place_ids       # the pivot date frees only unsent old drafts
    assert "sent_old" in ctx.contacted_place_ids                                     # anyone actually contacted stays contacted
