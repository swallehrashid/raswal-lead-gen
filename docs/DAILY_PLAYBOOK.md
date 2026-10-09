# Raswal Lead Generator — Daily Playbook

*Swalleh's routine, Monday to Friday, from 12 Oct to mid-December 2026, with an optional January run.*

**Daily goal:** send up to 30 strictly qualified, personalised WhatsApp messages (20 website, 10 content) with teaser images, follow up on time, and turn "yes" replies into demos the same day.

---

## The day at a glance

| When | What | Time |
|---|---|---|
| Night before, ~21:30 (automatic) | The nightly job builds tomorrow's list | 0 min (optional 1-min check) |
| 08:30 | **Review**: approve or skip in the dashboard | 10–15 min |
| 09:30–11:00 | **Send batch 1**: ~15 messages | ~30 min |
| 11:30 | Check replies and log them | 5–10 min |
| 14:00–15:30 | **Send batch 2**: ~15 messages, plus follow-ups due today | 30–50 min |
| 15:30 and 19:00 | Check replies and log them | 5–10 min each |
| Afternoon/evening | **Demos**: at most 3 website + 3 content | ≤ 1 hour each |
| Friday, end of day | **Weekly review** | 20 min |

**Realistic load:**
- **Week 1:** about 1–1.5 hours/day plus demos.
- **From week 3:** follow-ups stack up and it's about 1.5–2 hours/day plus demos.

If it gets too heavy, cut new sends to 25. Do not drop follow-ups, because most replies come from them.

---

## 1. Night before (automatic)

- The job runs Sunday to Thursday at about 21:30 and builds the list for the next weekday.
- **Optional check before bed:** the dashboard banner says either "Tomorrow's list ready: 18 web / 9 content" or shows an error.
- **If it failed:** GitHub mobile app → the repo → Actions → **Nightly** → **Run workflow**. The list will be ready in about 40 minutes.
- **Fewer than 30 is fine.** The bar is never lowered to fill the list.

**Themed days** (one subcategory per day):

| Mon | Tue | Wed | Thu | Fri |
|---|---|---|---|---|
| Property agencies | Land & developers | Construction | Hardware & supplies | Roofing & steel |

---

## 2. Morning review (08:30, 10–15 min)

Open **Today → Review**. For each card, check these five things in about 20 seconds:

1. **Facts are true at a glance.** The current-site screenshot matches the claim. For example, it really does show "suspended", or the Website button really does go to Facebook.
2. **The teaser looks like *them*.** The logo isn't broken, the colours aren't ugly, and the name is spelled right.
3. **It's the right size.** It isn't a national brand, a building or a tiny kiosk that slipped through.
4. **The message reads like a person wrote it.** Pick variant A or B and edit if needed. Keep it under about 480 characters.
5. **Content leads only:** tap their Instagram, Facebook or TikTok and set the social state:
   - `none` or `stale` → good lead.
   - `active` → still OK.
   - `polished` → **skip** (they probably already have an agency).

Then tap **Approve**, or **Skip** with a reason. The skip reasons are what improve the filters, so always pick one.

---

## 3. Sending (two batches of about 15)

Spread the messages out. Never send all 30 in 20 minutes; the dashboard warns you after 15 in an hour.

### On your phone (dashboard installed as an app)

1. **Open chat** (opens WhatsApp with their number).
2. Come back to the dashboard and tap **Share image + caption**. Pick their chat; it's at the top of your recents.
3. Check that the caption came through with the image, then send.
4. Back in the dashboard, tap **Sent ✓**.

If the caption didn't carry over: **Copy caption** and paste it into the image's caption box.

### On WhatsApp Web (desktop)

1. **Open chat** → **Copy image** → paste into the chat.
2. **Copy caption** → paste it into the caption box → send.
3. Tap **Sent ✓**.

### If the number isn't on WhatsApp

Tap **No WhatsApp**. A reserve lead replaces it automatically.

### Rules for every first message

- The image goes **with** the caption, in one message.
- No links, no prices.
- One question only.
- Address the **business**, not a guessed person.

---

## 4. Replies (check about 3 times a day, respond within about 1 hour)

1. Find the lead in **Inbox log**.
2. Tap **Log reply** and pick the type.
3. Use a **quick reply** snippet if one fits, but adjust it to their words.

| They say | You do |
|---|---|
| "Yes, send it" / "Interested" | **Mark interested** → choose Website or Content → it moves to the **Demo queue** |
| "How much?" | Use the price quick reply, which always offers the preview first |
| "Who is this?" | Use the intro quick reply (name, Raswal, found them on Google Maps, offer to stop) |
| "Not now" | Snooze. Suggest January or pick a date. |
| "We have someone" | Polite close, then mark `lost` with reason `has_provider` |
| "Stop" / annoyed | Apologise once, then mark **opted out**. They are never contacted again. |

---

## 5. Follow-ups (in batch 2)

Open **Follow-ups → Due today**.

| Follow-up | When | Content |
|---|---|---|
| **FU1** | 3 working days after the first message | Short text: "did you see the preview?" |
| **FU2** | 8 working days after the first message | The last one: a different angle, plus "I won't keep messaging" |
| *(none)* | After FU2 | The lead becomes `no_response` and is **never** messaged again unless they reply |
| **Demo follow-ups** | 1 and 4 working days after a demo link | Check whether they've looked at it |

---

## 6. Demos (at most 3 website + 3 content per day)

1. Open the **Demo queue**, oldest first.
2. Tap **Export lead pack** to get the JSON and a ZIP of logo, hero image and teaser. Hand it to the web-demo or content-demo repo.
3. Build the demo (about 1 hour).
4. Paste the preview link into the lead and send it in the WhatsApp chat.
5. Tap **Mark demo sent**. Demo follow-ups are scheduled automatically.

**Same-day rule:** a "yes" before about 17:00 gets its link the same day. A later "yes" gets it first thing the next morning.

**Over the cap:** if the queue is past today's cap, send the holding reply ("I'll have it ready for you tomorrow morning") and do it first thing.

---

## 7. Weekly review (Friday, 20 min)

Open **Stats** and look at:

1. **Reply, interested, demo and won rates** per subcategory and per track. Is one subcategory clearly weak?
2. **Which top fact codes get replies.** For example, does "dead site" beat "no website"?
3. **Skip reasons** from your morning reviews. Are the same false positives coming through?
4. **Gate rejection counts** and **areas running low.** Is it time for tier 2 areas?
5. **API usage and storage** against the free caps.

Then make **1–2 changes at most** in `config/` (weights, thresholds, queries, areas, exclusions). Too many changes at once makes it impossible to tell what worked.

---

## 8. Protecting the WhatsApp number (0114 129 809)

This number is also SahilPay's contact line, so a restriction would hurt both businesses.

**Ramp up in week 1** (12–16 Oct):

| Mon | Tue | Wed | Thu | Fri |
|---|---|---|---|---|
| 15 | 20 | 25 | 30 | 30 |

**Ongoing rules:**
- No more than about 15 sends an hour.
- Stop immediately for anyone who says stop.
- **Stop all sending for 48 hours** if WhatsApp shows any warning or restriction notice, or if lots of new messages sit on one grey tick. Then restart at 10 a day.
- Keep messages specific. Generic messages are what get reported and blocked.

---

## 9. Calendar

| Date | Plan |
|---|---|
| Mon 12 Oct | Start (follow the ramp in §8) |
| Tue 20 Oct | **Mashujaa Day.** No list; the Monday-night job skips automatically. |
| Through November | Full pace |
| Mon 14 – Fri 18 Dec | Last strong week |
| 21 Dec – 1 Jan | No new sends; demos and replies only |
| Mon 4 Jan 2027 | Resume, if extending into January |

**Front-load October and November.** Decision-makers go quiet in late December.
