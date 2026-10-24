// Layout audit run in-page: returns problems at time t.
window.audit = function (t) {
  window.renderAt(t);
  const out = [];
  const vis = (el) => { for (let e = el; e && e !== document.body; e = e.parentElement) { const s = getComputedStyle(e); if (s.display === 'none' || s.visibility === 'hidden' || +s.opacity === 0) return false; } return true; };
  const sel = '.big, #brand-name, #brand-lede, #brand-tag, .cap, #window, .msg__bubble, .card-content, .flashcard, #diagram svg, .upload-card, .chat-input, .session-title, .doc-item__name, .chat-messages';
  for (const el of document.querySelectorAll(sel)) {
    if (!vis(el)) continue;
    const r = el.getBoundingClientRect();
    const name = el.id || el.className.baseVal || el.className;
    if (r.left < -1 || r.top < -1 || r.right > 1921 || r.bottom > 1081) out.push(`${name} offscreen ${r.left|0},${r.top|0},${r.right|0},${r.bottom|0}`);
    if (el.scrollWidth > el.clientWidth + 2 && !el.matches('.session-title,.doc-item__name')) out.push(`${name} h-overflow ${el.scrollWidth}>${el.clientWidth}`);
    if (el.scrollHeight > el.clientHeight + 2 && !el.matches('.big,#brand-name,.cap')) out.push(`${name} v-overflow ${el.scrollHeight}>${el.clientHeight}`);
  }
  // caption vs window collision
  const cap = [...document.querySelectorAll('.cap')].find(vis), w = document.querySelector('#window');
  if (cap && vis(w)) { const a = cap.querySelector('*') ? cap.getBoundingClientRect() : null; const range = document.createRange(); range.selectNodeContents(cap); const cr = range.getBoundingClientRect(); const wr = w.getBoundingClientRect(); if (cr.bottom > wr.top) out.push(`caption overlaps window ${cr.bottom|0}>${wr.top|0}`); }
  // messages contained in their scroll area
  const cm = document.querySelector('#tab-chat .chat-messages'), ai = document.querySelector('#m-ai');
  if (vis(ai)) { const a = ai.getBoundingClientRect(), c = cm.getBoundingClientRect(); if (a.bottom > c.bottom) out.push(`answer clipped ${a.bottom|0}>${c.bottom|0}`); }
  const d = document.querySelector('#diagram svg');
  if (d && vis(d)) { const a = d.getBoundingClientRect(), c = document.querySelector('#window').getBoundingClientRect(); if (a.bottom > c.bottom - 4 || a.right > c.right) out.push(`diagram clipped ${a.bottom|0}>${c.bottom|0}`); }
  return out;
};
