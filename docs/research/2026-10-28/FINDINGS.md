# What's working in Kenyan property ads (research, 28 Oct 2026)

Source: `scripts/research_trends.py` via Apify ($1.68 of the free $5): 190 active Facebook/Instagram ads from the Meta Ad Library
(Kenya; "plots for sale", "land for sale", "ready title deed", "apartment for rent Nairobi", "house for rent"),
150 TikTok videos from 6 Kenyan property hashtags, 84 Instagram posts from 4. Raw data in `raw/`.
An ad that has run for months is an ad that pays, so "longest running" is the signal used below.

## Facebook / Instagram ads (70 real-estate ads after removing noise)
- **CTA: "Send WhatsApp message" on 41 of 70 (59%).** Click-to-WhatsApp is the standard; "Learn more" is a distant second (7).
- **Format: video 25, image 18, carousel 14.** Video leads, but simple image ads run longest (Beulla Property: one image, 284 days).
- **The winning land ad is the same shape every time:**
  `[AREA] PLOTS FOR SALE` → price ("Only KSh 445,000") → ✅ checklist (ready title deeds, water & electricity, graded roads,
  beacons, fenced, neighbours) → deposit ("Start with KSh 30K deposit") → free site visit → "Call/WhatsApp 07…".
- **Hooks that keep running:** "Still paying rent? Own your own plot in Kikuyu for 499K" (Pro-Property, also on TikTok);
  "KSH 250,000 ONLY – … PLOTS WITH READY TITLES!"; "Title deed inclusive / all-inclusive"; "transferable within 21 days";
  "touching tarmac" / "4 km from tarmac"; "Free daily site visits"; Swahili one-liners ("NUNUA PLOTI NA UJENGE").
- **Rentals:** amenities list + "ready for immediate move-in" + "book your viewing"; TSAVO's long-runner opens on pain:
  "Tired of matatus eating your salary".

## TikTok (150 videos)
- **House-hunting walk-throughs dominate** (#househuntinginnairobikenya is the #2 tag). Top: house-hunting vlog 774k plays,
  "What $194,000 gets you in Nairobi" 675k, "this is what $700 is supposed to look like" 290k.
- **88% use original audio**: people talk over the footage. Voice matters, which is why every template now has a voice-over.
- Median length 61 s (land/house tours run long); our ads stay 15–45 s because they are paid placements, not organic.
- Top tags: #realestatekenya #househuntinginnairobikenya #kenyantiktok🇰🇪 #kitengela #landforsalekenya #nairobirealestate #fyp.

## Instagram (84 posts)
- 75% carousels. The repeat format: "🔥 NEW LISTING 🔥 / Location: Kilimani / Price: Kshs 88K / ✅ Price includes service charge
  ✅ 24hr security ✅ Ample parking".
- Organic reach is small (top post 26 likes), which is the case for paid ads.
- Top tags: #nairobirealestate #househuntingnairobi #apartmentsforrentnairobi #landforsaleinkenya #kilimaniapartments.

## What changed in the templates because of this
| Template | Change |
|---|---|
| All six | Voice-over on the key points (Kenyan English, Gemini TTS); the music ducks under it |
| L1 Plot Tour | Voice opens with "Still paying rent? Own land in {area}." |
| L2 The Offer | Voice reads the winning structure: area → price → deposit → ready title → minutes from landmark → free visit |
| A1 New Listings | Listing chip now reads "NEW LISTING" (the Instagram format) |
| A2 Viewing Day | Voice opens with "House hunting in {area}? Come on in." (the TikTok format) |
| A3 Budget | Hook is now "WHAT KES 60,000 A MONTH GETS YOU IN NAIROBI" (the 675k-play format) |
| Ad captions (`build_pilot.captions`) | Caps headline + price + ✅ checklist + free visit + WhatsApp ask + hashtags |

## Re-run
`.venv/bin/python scripts/research_trends.py --budget 2` (needs `APIFY_TOKEN`), then compare with this file. Every few weeks is enough.
