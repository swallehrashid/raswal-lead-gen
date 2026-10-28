/* Binds window.LEAD to the ad-mockup teaser. Self-contained: no requests. Include last in <body>. */
(function () {
  var L = window.LEAD || {}, A = L.ad || {}, root = document.documentElement;
  var WA = '<svg viewBox="0 0 24 24"><path d="M17.47 14.38c-.3-.15-1.76-.87-2.03-.97-.27-.1-.47-.15-.67.15-.2.3-.77.97-.94 1.17-.17.2-.35.22-.64.07-.3-.15-1.26-.46-2.4-1.48-.88-.79-1.48-1.76-1.65-2.06-.17-.3-.02-.46.13-.6.13-.14.3-.35.45-.52.15-.17.2-.3.3-.5.1-.2.05-.37-.02-.52-.08-.15-.67-1.62-.92-2.2-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.52.08-.8.37-.27.3-1.04 1.02-1.04 2.48 0 1.46 1.07 2.88 1.21 3.08.15.2 2.1 3.2 5.08 4.49.7.3 1.26.49 1.7.63.72.23 1.37.2 1.88.12.57-.08 1.76-.72 2-1.41.25-.7.25-1.29.17-1.41-.07-.13-.27-.2-.57-.35zM12.05 21.8h-.01a9.9 9.9 0 0 1-5.03-1.38l-.36-.21-3.74.98 1-3.65-.24-.37a9.86 9.86 0 0 1-1.51-5.26c0-5.45 4.44-9.88 9.89-9.88 2.64 0 5.12 1.03 6.99 2.9a9.83 9.83 0 0 1 2.89 6.99c0 5.45-4.44 9.88-9.88 9.88zM20.46 3.49A11.8 11.8 0 0 0 12.05 0C5.5 0 .16 5.34.16 11.9c0 2.1.55 4.14 1.59 5.95L.06 24l6.3-1.65a11.9 11.9 0 0 0 5.69 1.45h.01c6.55 0 11.89-5.34 11.89-11.9 0-3.18-1.24-6.17-3.48-8.41z"/></svg>';
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  function lum(hex) {
    var m = /^#?([0-9a-f]{6})$/i.exec(hex || ''); if (!m) return 0.2;
    var v = [0, 2, 4].map(function (i) { var c = parseInt(m[1].substr(i, 2), 16) / 255; return c <= .03928 ? c / 12.92 : Math.pow((c + .055) / 1.055, 2.4); });
    return .2126 * v[0] + .7152 * v[1] + .0722 * v[2];
  }
  function on(hex) { return lum(hex) > .42 ? '#111111' : '#ffffff'; }
  function set(n, v) { if (v) root.style.setProperty(n, v); }
  var primary = L.primary || '#0e4d3a', accent = L.accent || '#d4a537';
  // a very light brand "primary" would vanish on white: fall back to the vertical palette for the avatar and wordmark
  if (lum(primary) > .6) primary = L.ad_primary || '#0e4d3a';
  // a dark brand accent would vanish on the dark scene: use the vertical's gold instead
  if (lum(accent) < .18) accent = L.ad_accent || '#d4a537';
  set('--primary', primary); set('--accent', accent); set('--on-primary', on(primary)); set('--on-accent', on(accent));
  function fill(t) { return String(t || '').replace(/\{area\}/g, L.area || 'Nairobi'); }
  function txt(sel, v) { $$(sel).forEach(function (e) { e.textContent = v; }); }

  var AD_SCREEN = '<div class="screen"><div class="island"></div><div class="glare"></div>'
    + '<div class="status"><i>9:41</i><i>5G ▮▮▮</i></div>'
    + '<div class="feedbar">Feed<span>Sponsored</span></div>'
    + '<div class="post"><div class="post-head"><div class="avatar" data-ad="avatar"></div><div><div class="pname" data-ad="name"></div><div class="psub">Sponsored · 🌍</div></div></div>'
    + '<div class="caption" data-ad="caption"></div>'
    + '<div class="creative"><div class="seal" data-ad="seal"></div><div class="c-head" data-ad="headline"></div><div class="chips" data-ad="chips"></div><div class="badge" data-ad="badge"></div></div>'
    + '<div class="cta"><small>Message {name}</small><span class="btn" data-ad="btn"></span></div>'
    + '<div class="reacts"><span>👍 Like</span><span>💬 Comment</span><span>↪ Share</span></div></div></div>';
  var CHAT_SCREEN = '<div class="screen"><div class="island"></div><div class="glare"></div>'
    + '<div class="status chatbar" style="background:#075e54;color:#fff"><i>9:41</i><i>5G ▮▮▮</i></div>'
    + '<div class="chathead">WhatsApp<small>Chats</small></div><div data-ad="chats"></div></div>';
  Array.prototype.forEach.call(document.querySelectorAll('[data-ad="phone-ad"]'), function (e) { e.innerHTML = AD_SCREEN.replace('{name}', (L.business_name || 'us').replace(/</g, '')); });
  Array.prototype.forEach.call(document.querySelectorAll('[data-ad="phone-chat"]'), function (e) { e.innerHTML = CHAT_SCREEN; });

  var name = L.business_name || 'Your business';
  txt('[data-ad="name"]', name);
  txt('[data-ad="area"]', L.area || 'Nairobi');
  txt('[data-ad="headline"]', fill(A.post_headline));
  txt('[data-ad="badge"]', A.badge || '');
  txt('[data-ad="seal"]', A.seal || '');
  txt('[data-ad="caption"]', fill(A.caption));
  $$('[data-ad="chips"]').forEach(function (e) { (A.chips || []).forEach(function (c) { var b = document.createElement('b'); b.textContent = c; e.appendChild(b); }); });
  $$('[data-ad="avatar"]').forEach(function (e) {
    if (L.logo_data_url) { var i = document.createElement('img'); i.src = L.logo_data_url; e.appendChild(i); }
    else e.textContent = name.replace(/[^A-Za-z]/g, '').slice(0, 2).toUpperCase() || 'B';
  });
  $$('[data-ad="btn"]').forEach(function (e) { e.innerHTML = WA + '<span>Send WhatsApp message</span>'; });
  $$('[data-ad="wa"]').forEach(function (e) { e.innerHTML = WA; });
  $$('.creative').forEach(function (e) { if (L.ad_post_data_url) e.style.backgroundImage = 'url(' + L.ad_post_data_url + ')'; });
  $$('.bg').forEach(function (e) { if (L.ad_bg_data_url) e.style.backgroundImage = 'url(' + L.ad_bg_data_url + ')'; });
  $$('[data-ad="bubbles"]').forEach(function (host) {
    var tpl = host.getAttribute('data-class') || '';
    (A.bubbles || []).forEach(function (t, i) {
      var d = document.createElement('div'); d.className = 'bubble b' + (i + 1) + ' ' + tpl;
      d.innerHTML = '<div class="who">' + WA + '<span>New enquiry</span></div><span class="t"></span><span class="tick">✓✓</span>';
      d.querySelector('.t').textContent = fill(t); host.appendChild(d);
    });
  });
  var cols = ['#128c7e', '#d4a537', '#5b6b7c'];
  var OLDER = [['Joyce W.', 'Asante sana!', '#7b61a8'], ['Daniel K.', 'Sawa, tutaonana kesho.', '#c4623b'], ['Grace M.', 'Thanks, noted.', '#3b7ec4'], ['Peter N.', 'Tumepokea, asante.', '#2f8f5b']];
  $$('[data-ad="chats"]').forEach(function (host) {
    (A.chats || []).forEach(function (c, i) {
      var r = document.createElement('div'); r.className = 'row';
      r.innerHTML = '<div class="av"></div><div class="tx"><div class="nm"><span></span><i>9:4' + (1 - i < 0 ? 0 : 1 - i) + '</i></div><div class="pv"></div></div><div class="dot"></div>';
      r.querySelector('.av').style.background = cols[i % 3]; r.querySelector('.av').textContent = c[0].slice(0, 1);
      r.querySelector('.nm span').textContent = c[0]; r.querySelector('.pv').textContent = fill(c[1]); host.appendChild(r);
    });
    OLDER.forEach(function (o) {
      var r = document.createElement('div'); r.className = 'row';
      r.innerHTML = '<div class="av"></div><div class="tx"><div class="nm"><span></span><i style="color:#8696a0">Yesterday</i></div><div class="pv"></div></div>';
      r.querySelector('.av').style.background = o[2]; r.querySelector('.av').textContent = o[0].slice(0, 1);
      r.querySelector('.nm span').textContent = o[0]; r.querySelector('.pv').textContent = o[1]; host.appendChild(r);
    });
  });
  // fit long names: shrink the footer name until it fits two lines
  $$('[data-fit]').forEach(function (e) {
    var s = parseFloat(getComputedStyle(e).fontSize), max = parseFloat(e.getAttribute('data-fit'));
    var guard = 0; while (e.scrollHeight > max && s > 14 && guard++ < 30) { s -= 1; e.style.fontSize = s + 'px'; }
  });
  // seeded gold dust (direction 2)
  $$('[data-dust]').forEach(function (host) {
    var seed = 7, rnd = function () { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
    for (var i = 0; i < +host.getAttribute('data-dust'); i++) {
      var d = document.createElement('i'), s = 3 + rnd() * 9;
      d.style.cssText = 'position:absolute;border-radius:50%;left:' + (rnd() * 1080) + 'px;top:' + (rnd() * 1350) + 'px;width:' + s + 'px;height:' + s + 'px;background:var(--accent);opacity:' + (.12 + rnd() * .5) + ';filter:blur(' + (rnd() * 2.4) + 'px)';
      host.appendChild(d);
    }
  });
})();
