# Monday runbook (and every working day after)

Everything runs on your phone/PC. Meta account steps are in `pilot-kit/`; the nightly list builds itself.

## The daily loop
1. **Open the dashboard** (leads.raswaltechsolutions.co.ke → Today). Last night's list is there: **20 land + 10 agencies** (change the mix in Settings; adjust weekly from Stats → reply rate by subcategory).
2. **Review**: each card shows the ad-mockup teaser, the angle chip (A not advertising · B already advertising · C no site), the Ad Library link, social state, and 2 messages. Approve or skip. Skip reasons teach the filters.
3. **Send**: Send tab → share image + caption → WhatsApp. Max 15 an hour; batch windows 09:30-11:00 and 14:00-15:30.
4. **Replies**: Inbox → log the reply. A "yes please send the plan" → open the lead → **Send the pilot plan**.
5. **Generate the plan** (on your PC, a few minutes):
   ```bash
   cd ~/Projects/raswal-lead-gen && .venv/bin/python -m pipeline generate
   ```
   It builds the 3 tailored ads + the scroll-story page, deploys to `{slug}.raswaltechsolutions.co.ke/pilot/`, and puts the link and the ready message on the lead (Plans tab → copy → send → "Mark plan sent").
6. **They say yes to the pilot** → lead → **Start the pilot** (Pilots tab). Follow `pilot-kit/` docs 01-06: offer form, 5 questions, route, M-Pesa, build the campaign, go live (target: 24 hours).
7. **Daily during a pilot**: Pilots tab → enter yesterday's numbers → **Copy daily update** → send. Red flag at KES 250+/chat after 48 h.
8. **Day 7**: **Copy day-7 report** → send → Converted / Declined.

## Final-quality files for a live pilot
```bash
.venv/bin/python -m pipeline generate --lead-id <id> --final --offer offer.json
```
Writes `raswal-pipeline/pilots/<slug>/final/` with the three ad videos, the 4:5 stills, the 15 s Status cuts, `captions.txt` and `campaign-sheet.md`.

## Once a week
- Stats → reply rate per subcategory: if agencies reply more, try 15/10 (Settings → Daily mix).
- Sunday: the Ad Library sync runs at 18:00 and the list at 21:30 (both GitHub Actions). If a run failed the dashboard banner says so; re-run it from GitHub → Actions.

## If something breaks
- No list this morning: GitHub → Actions → Nightly → Run workflow.
- A plan page won't build: `.venv/bin/python -m pipeline generate --lead-id <id> --dry-run` shows the error; the page builder is `~/Projects/raswal-pipeline/build_pilot.py`.
- Whole-system check: `.venv/bin/python scripts/e2e.py` (10-15 min, changes nothing live).
