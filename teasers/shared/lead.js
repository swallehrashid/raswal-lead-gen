/* Binds window.LEAD to the template (brief §13.1). Include at the END of <body>.
 *
 * Markup hooks:
 *   data-lead="business_name|area|headline|subline|phone_display|preview_domain|cta"  → text
 *   data-lead="poster_line" data-index="0..2"                                       → text
 *   data-lead="logo"        → <img> of logo_data_url, or a wordmark of business_name
 *   data-lead="hero"        → background-image from hero_image_data_url (else class "no-hero")
 *   data-lead="nav"         → filled with LEAD.nav items as <a>
 * CSS variables set on :root: --brand-primary, --brand-accent, --brand-ink, --brand-bg
 */
(function () {
  var L = window.LEAD || {};
  var root = document.documentElement;
  function setVar(name, value) { if (value) root.style.setProperty(name, value); }
  setVar('--brand-primary', L.primary);
  setVar('--brand-accent', L.accent);
  setVar('--brand-ink', L.ink);
  setVar('--brand-bg', L.bg);

  function each(sel, fn) { Array.prototype.forEach.call(document.querySelectorAll(sel), fn); }
  ['business_name', 'area', 'headline', 'subline', 'phone_display', 'preview_domain', 'cta'].forEach(function (k) {
    each('[data-lead="' + k + '"]', function (el) { el.textContent = L[k] || ''; });
  });
  var lines = L.poster_lines || [];
  each('[data-lead="poster_line"]', function (el) {
    var i = parseInt(el.getAttribute('data-index') || '0', 10);
    el.textContent = lines[i] || '';
  });
  each('[data-lead="nav"]', function (el) {
    el.innerHTML = '';
    (L.nav || []).forEach(function (item) {
      var a = document.createElement('a'); a.textContent = item; a.href = '#'; el.appendChild(a);
    });
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
