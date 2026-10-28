# Teasers

The first-touch WhatsApp image: an **illustrative sponsored post** for the lead (their name, logo, colours, area)
on a 3D phone, with enquiries landing in WhatsApp. It is always labelled "Illustration: your ad could look like this"
and never shows result numbers.

```
ad/ad.css, ad.js     shared components (phone, sponsored post, glass bubbles, chat list) and the window.LEAD binder
ad/d1|d2|d3/         the three layouts: Golden Hour, Studio, Two Phones
ad/photos/<sub>/     bg.jpg (1080×1350) and post.jpg (720×900) per subcategory
shared/fonts*        Inter + Montserrat, inlined into every render
```

- Copy per subcategory lives in `config/subcategories.yaml` → `ad_teaser`. The layout per subcategory is `ad_direction`.
- `python -m pipeline rerender --offline` renders fixture leads to `out/teasers/samples/` for a visual check.
- The renderer blocks every network request: templates must be self-contained (`tests/test_teaser.py` checks this).
