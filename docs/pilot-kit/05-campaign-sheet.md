# 05 · Campaign sheet (Ads Manager)

`python -m pipeline generate --lead-id <id> --final --offer offer.json` writes a ready-filled copy of this for each client to
`raswal-pipeline/pilots/<slug>/final/campaign-sheet.md`, with `captions.txt`, the three `ad*_video_final.mp4`,
`ad*_still_4x5.jpg` and `ad*_status_15s.mp4`. Upload those by hand: there is no Meta API automation yet.

| Setting | Value |
|---|---|
| Objective | Engagement → Messaging apps → **WhatsApp** |
| Budget | KES 5,000 all-in, campaign budget, 7 days |
| Ad sets | **1** (keeps learning in one place) |
| Location | radius ~40 km around the project / Nairobi |
| Audience | Advantage+ on; no age/gender narrowing |
| Placements | Advantage+ placements; **exclude Audience Network** |
| Ads | the 3 videos (+ the 4:5 still for feed, the 15 s cut for WhatsApp Status) |
| Copy | primary text / headline / CTA / pre-filled message from `captions.txt` |
| Day 3 | pause the clear loser if its cost per chat is more than 2× the winner |
| Stop rule | more than KES 250 per chat after 48 h: change the creative or widen the audience **the same day** |
| Review | submit by early afternoon: review is usually minutes to a few hours, up to 24 h |

Never write "guaranteed", "returns", "ROI", "investment opportunity" or personal-attribute phrasing ("Are you Kenyan in Dubai?").
