/* Binds window.LEAD to the poster. Same contract as the CRM teaser posters (brief §13.1),
 * inlined so each poster renders with no external request. Include last in <body>. */
(function () {
  var L = window.LEAD || {};
  var root = document.documentElement;
  function setVar(n, v) { if (v) root.style.setProperty(n, v); }
  setVar('--brand-primary', L.primary);
  setVar('--brand-accent', L.accent);
  setVar('--brand-ink', L.ink);
  setVar('--brand-bg', L.bg);
  function each(sel, fn) { Array.prototype.forEach.call(document.querySelectorAll(sel), fn); }
  ['business_name', 'area', 'headline', 'subline', 'phone_display', 'preview_domain', 'cta',
   'eyebrow1', 'eyebrow2', 'eyebrow3', 'p1_lead', 'p1_sub', 'p2_tag', 'wa_label', 'badge_sub',
   'p2_big', 'p3_big1', 'p3_big2'].forEach(function (k) {
    each('[data-lead="' + k + '"]', function (el) { el.textContent = L[k] || ''; });
  });
  // arrays: chat bubbles (poster 2) and benefit rows (poster 3)
  each('[data-render="bubbles"]', function (el) {
    (L.p2_bubbles || []).forEach(function (b) {
      var d = document.createElement('div'); d.className = 'b ' + (b.from === 'us' ? 'us' : 'them'); d.textContent = b.text; el.appendChild(d);
    });
  });
  each('[data-render="benefits"]', function (el) {
    (L.p3_benefits || []).forEach(function (t) {
      var row = document.createElement('div'); row.className = 'bn';
      var r = document.createElement('span'); r.className = 'ring'; r.textContent = '✓';
      var s = document.createElement('span'); s.className = 'tx'; s.textContent = t;
      row.appendChild(r); row.appendChild(s); el.appendChild(row);
    });
    (L.p3_checks || []).forEach(function (t) {  // alt class used by some layouts
      var row = document.createElement('div'); row.className = 'chk';
      var r = document.createElement('span'); r.className = 'tick'; r.textContent = '✓';
      var s = document.createElement('span'); s.textContent = t;
      row.appendChild(r); row.appendChild(s); el.appendChild(row);
    });
  });
  var lines = L.poster_lines || [];
  each('[data-lead="poster_line"]', function (el) {
    var i = parseInt(el.getAttribute('data-index') || '0', 10);
    el.textContent = lines[i] || '';
  });
  each('[data-lead="logo"]', function (el) {
    el.innerHTML = '';
    if (L.logo_data_url) {
      var img = document.createElement('img'); img.src = L.logo_data_url; img.alt = L.business_name || '';
      el.appendChild(img); el.classList.add('has-logo');
    } else {
      var w = document.createElement('span'); w.className = 'wordmark'; w.textContent = L.business_name || '';
      el.appendChild(w); el.classList.add('has-wordmark');
    }
  });
  each('[data-lead="hero"]', function (el) {
    if (L.hero_image_data_url) { el.style.backgroundImage = 'url("' + L.hero_image_data_url + '")'; el.classList.add('has-hero'); }
    else { el.classList.add('no-hero'); }
  });
  root.classList.add('lead-ready');
})();
