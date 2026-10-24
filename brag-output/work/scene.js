// Every frame is a pure function of time: renderAt(t) sets all visual state from t alone.
// 120 BPM -> one beat = 0.5s. All scene changes land on beats.
const $ = (s) => document.querySelector(s);
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lin = (t, a, b) => clamp((t - a) / (b - a));
const easeOut = (x) => 1 - Math.pow(1 - x, 3);
const easeInOut = (x) => (x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
const back = (x) => { const c = 1.6; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); };
const mix = (a, b, k) => a + (b - a) * k;
// visible window with fade in/out
const win = (t, a, b, f = .2) => Math.min(lin(t, a, a + f), 1 - lin(t, b - f, b));

const QUESTION = 'Why are mitochondria called the powerhouse of the cell?';
const ANSWER = "They make most of the cell's ATP through cellular respiration, turning glucose and oxygen into usable energy.";

const FLOW = `flowchart TD
  A[Cell Biology] --> B[Cell Structure]
  A --> C[Energy]
  B --> D[Membrane]
  B --> E[Nucleus]
  C --> F[Mitochondria]
  C --> H[Photosynthesis]
  F --> G[ATP Synthesis]`;
const NODE_STEP = { A: 0, B: 1, C: 1, D: 2, E: 2, F: 2, H: 2, G: 3 };
let flowNodes = [], flowEdges = [];

// Timeline (seconds)
const T = { hookEnd: 2.5, revealEnd: 6.0, upload: 6.0, chat: 9.0, flash: 13.0, flow: 15.5, outro: 18.0, end: 21.0 };

function setOp(el, o) { el.style.opacity = o; el.style.visibility = o <= 0.001 ? 'hidden' : 'visible'; }

// Element center in stage coordinates (stage is 1920x1080 at 0,0)
function center(sel, dx = 0, dy = 0) {
  const r = $(sel).getBoundingClientRect();
  return [r.left + r.width / 2 + dx, r.top + r.height / 2 + dy];
}

// Cursor path: list of [time, selector|point]; moves with ease between keys
function cursorAt(t, keys) {
  let p = null;
  for (let i = 0; i < keys.length; i++) {
    const [kt, target] = keys[i];
    const pt = typeof target === 'string' ? center(target) : target;
    if (t < kt) {
      if (!p) return pt;
      const [pt0, pp] = p;
      const k = easeInOut(lin(t, pt0, kt));
      return [mix(pp[0], pt[0], k), mix(pp[1], pt[1], k)];
    }
    p = [kt, pt];
  }
  return p[1];
}

function ripple(t, clicks) {
  document.querySelectorAll('.ripple').forEach((r) => r.remove());
  for (const [ct, pt] of clicks) {
    const k = lin(t, ct, ct + .4);
    if (k <= 0 || k >= 1) continue;
    const r = document.createElement('div');
    r.className = 'ripple';
    r.style.left = pt[0] + 'px'; r.style.top = pt[1] + 'px';
    r.style.transform = `scale(${.3 + k})`; r.style.opacity = 1 - k;
    $('#stage').appendChild(r);
  }
}

// ---------- Scene renderers ----------
function renderHook(t) {
  const o = 1 - lin(t, 2.25, 2.5);
  setOp($('#hook'), t < 2.5 ? o : 0);
  const k = back(lin(t, 0, .35));
  $('#hook-icon').style.transform = `translateY(${(1 - k) * -60}px) rotate(${(1 - k) * -12}deg)`;
  $('#hook-icon').style.opacity = lin(t, 0, .15);
  document.querySelectorAll('#hook .w').forEach((w, i) => {
    const s = i * .5; // one word per beat
    const e = easeOut(lin(t, s, s + .25));
    w.style.opacity = e;
    w.style.transform = `translateY(${(1 - e) * 40}px) scale(${mix(.92, 1, e)})`;
  });
}

function renderBrand(t) {
  const reveal = t >= 2.5 && t < 6.0, outro = t >= 18.5;
  const base = reveal ? 2.5 : 18.5;
  const o = reveal ? win(t, 2.5, 6.0, .25) : outro ? lin(t, 18.5, 18.75) : 0;
  setOp($('#brand'), o);
  if (!o) return;
  $('#brand-logo .draw').style.strokeDashoffset = 1 - easeInOut(lin(t, base, base + .9));
  const ls = back(lin(t, base, base + .5));
  $('#brand-logo').style.transform = `scale(${mix(.6, 1, ls)})`;
  const n = easeOut(lin(t, base + .5, base + .8));
  $('#brand-name').style.opacity = n;
  $('#brand-name').style.transform = `translateY(${(1 - n) * 30}px)`;
  const sub = easeOut(lin(t, base + .75, base + 1.05));
  const lede = $('#brand-lede'), tag = $('#brand-tag');
  setOp(lede, reveal ? sub : 0); setOp(tag, outro ? sub : 0);
  (reveal ? lede : tag).style.transform = `translateY(${(1 - sub) * 20}px)`;
  // gentle settle-in of whole block
  $('#brand').style.transform = `translateY(${outro ? -40 : -40}px) scale(${mix(1.04, 1, easeOut(lin(t, base, base + 1.5)))})`;
}

function renderCaptions(t) {
  const caps = [['#cap-upload', 6.0, 9.0], ['#cap-chat', 9.0, 13.0], ['#cap-flash', 13.0, 16.0], ['#cap-flow', 16.0, 18.5]];
  for (const [sel, a, b] of caps) {
    // staggered: previous out in the last 0.2s, next in over the first 0.25s
    const inK = easeOut(lin(t, a, a + .25)), outK = lin(t, b - .2, b);
    const o = t >= a && t < b ? Math.min(inK, 1 - outK) : 0;
    setOp($(sel), o);
    $(sel).style.transform = `translateY(${(1 - inK) * 24 - outK * 16}px)`;
  }
}

function renderWindow(t) {
  const o = t >= 6.0 && t < 18.5 ? Math.min(lin(t, 6.0, 6.3), 1 - lin(t, 18.25, 18.5)) : 0;
  setOp($('#window'), o);
  if (!o) return;
  const k = easeOut(lin(t, 6.0, 6.5));
  // slow push-in during the whole demo for life
  const s = 1.2 * mix(.96, 1, k) * mix(1, 1.02, lin(t, 6.5, 18.5));
  $('#window').style.transform = `translateY(${(1 - k) * 80}px) scale(${s})`;
}

function renderUpload(t) {
  const picked = t >= 6.75, submitted = t >= 7.25;
  const ready = t >= 8.25;
  $('#drop').classList.toggle('drop-zone--active', picked);
  $('#drop').classList.toggle('drop-zone--busy', submitted && !ready);
  $('#ico-file').style.display = picked ? 'none' : 'inline';
  $('#ico-check').style.display = picked ? 'inline' : 'none';
  $('#drop-text').textContent = picked ? '1 file selected' : 'Click to choose files';

  const busy = submitted && !ready;
  $('#upspin').style.display = busy ? 'inline-block' : 'none';
  $('#upspin').style.transform = `rotate(${t * 514}deg)`;
  const pct = Math.round(easeInOut(lin(t, 7.25, 7.85)) * 100);
  const uploading = submitted && t < 7.9;
  $('#uplabel').textContent = !submitted ? (picked ? 'Analyze 1 document' : 'Analyze document')
    : uploading ? 'Uploading…' : !ready ? 'Processing…' : 'Analyze 1 document';
  $('#upbtn').style.opacity = !picked ? .35 : busy ? .35 : 1;

  const q = easeOut(lin(t, 7.25, 7.5));
  setOp($('#queue'), q);
  $('#queue').style.display = submitted ? 'grid' : 'none';
  $('#qitem').classList.toggle('queue-item--ready', ready);
  $('#qstatus').textContent = uploading ? `Uploading ${pct}%` : !ready ? 'Analyzing…' : 'Ready';
  $('#qprog').style.display = uploading ? 'block' : 'none';
  $('#qbar').style.width = pct + '%';
  const ok = easeOut(lin(t, 8.25, 8.45));
  $('#upok').style.display = ready ? 'flex' : 'none';
  $('#upok').style.opacity = ok;
}

function renderChat(t) {
  const n = Math.floor(lin(t, 9.2, 10.3) * QUESTION.length);
  const sent = t >= 10.5;
  const typed = sent ? '' : QUESTION.slice(0, n);
  $('#m-typed').textContent = typed;
  $('#m-ph').style.display = typed ? 'none' : 'inline';
  $('#m-caret').style.display = !sent && t >= 9.1 && (typed.length < QUESTION.length || Math.floor(t * 4) % 2 === 0) ? 'inline-block' : 'none';
  $('#m-send').style.opacity = typed ? 1 : .25;

  const u = easeOut(lin(t, 10.5, 10.75));
  setOp($('#m-user'), u);
  $('#m-user').style.transform = `translateY(${(1 - u) * 8}px)`;

  const thinking = t >= 10.6 && t < 11.0;
  $('#m-think').style.display = thinking ? 'flex' : 'none';
  $('#m-think').querySelectorAll('span').forEach((s, i) => {
    const ph = ((t - i * .2) % 1.2) / 1.2;
    const y = ph < .3 ? Math.sin(ph / .3 * Math.PI / 2) : ph < .6 ? Math.cos((ph - .3) / .3 * Math.PI / 2) : 0;
    s.style.transform = `translateY(${-5 * y}px)`; s.style.opacity = .4 + .6 * y;
  });

  const a = easeOut(lin(t, 11.0, 11.25));
  $('#m-ai').style.display = t >= 11.0 ? 'flex' : 'none';
  $('#m-ai').style.opacity = a;
  $('#m-ai').style.transform = `translateY(${(1 - a) * 8}px)`;
  const words = ANSWER.split(' ');
  const w = Math.ceil(lin(t, 11.0, 11.9) * words.length);
  $('#m-answer').textContent = words.slice(0, w).join(' ');
  const src = lin(t, 11.9, 12.15);
  $('#m-src').style.display = src > 0 ? 'block' : 'none';
  $('#m-src').style.opacity = src;
}

function renderTabs(t) {
  const work = t >= 9.0;
  const up = $('#view-upload'), wk = $('#view-work');
  setOp(up, work ? 0 : 1 - lin(t, 8.8, 9.0));
  setOp(wk, work ? easeOut(lin(t, 9.0, 9.2)) : 0);
  const active = t < 13.0 ? 'chat' : t < 16.0 ? 'flash' : 'flow';
  const start = { chat: 9.0, flash: 13.0, flow: 16.0 }[active];
  document.querySelectorAll('.chat-toolbar__tab').forEach((b) => b.classList.toggle('chat-toolbar__tab--active', b.dataset.tab === active));
  for (const id of ['chat', 'flash', 'flow']) {
    const el = $('#tab-' + id);
    const k = id === active ? easeOut(lin(t, start, start + .25)) : 0;
    setOp(el, k);
    el.style.transform = `translateY(${(1 - k) * 10}px)`;
  }
}

function renderFlash(t) {
  const f = easeInOut(lin(t, 14.0, 14.6));
  $('#card-inner').style.transform = `rotateY(${f * 180}deg)`;
  const lift = Math.sin(f * Math.PI);
  $('#card').style.transform = `scale(${1 + lift * .04})`;
}

function renderFlow(t) {
  for (const [el, step] of flowNodes) {
    const k = back(lin(t, 16.0 + step * .25, 16.0 + step * .25 + .3));
    el.style.opacity = clamp(k * 1.5);
    el.style.transformBox = 'fill-box'; el.style.transformOrigin = 'center';
    el.style.scale = String(Math.max(0, mix(.4, 1, k)));
  }
  for (const [el, step] of flowEdges) {
    const len = el.getTotalLength();
    const k = easeOut(lin(t, 16.0 + step * .25 - .1, 16.0 + step * .25 + .15));
    el.style.strokeDasharray = len; el.style.strokeDashoffset = len * (1 - k);
    el.style.opacity = k > 0 ? 1 : 0;
    const m = el.getAttribute('marker-end');
    if (m) el.style.markerEnd = k >= 1 ? '' : 'none';
  }
}

function renderCursor(t) {
  const keys = [
    [6.0, [1500, 1150]], [6.65, '#drop'], [6.9, '#drop'], [7.2, '#upbtn'], [8.6, '#upbtn'],
    [9.15, '#m-input'], [10.1, '#m-input'], [10.45, '#m-send'], [12.4, '#m-send'],
    [12.95, '[data-tab=flash]'], [13.3, '[data-tab=flash]'], [13.95, '#card'], [15.4, '#card'],
    [15.95, '[data-tab=flow]'], [16.3, '[data-tab=flow]'], [17.2, [1750, 1010]],
  ];
  const [x, y] = cursorAt(t, keys);
  setOp($('#cursor'), t >= 6.0 && t < 18.5 ? Math.min(lin(t, 6.2, 6.5), 1 - lin(t, 18.2, 18.5)) : 0);
  // tip of the arrow is ~ (5,3) in the 34px svg
  const clicks = [[6.75, '#drop'], [7.25, '#upbtn'], [10.5, '#m-send'], [13.0, '[data-tab=flash]'], [14.0, '#card'], [16.0, '[data-tab=flow]']];
  const press = clicks.some(([c]) => t >= c - .05 && t < c + .1);
  $('#cursor').style.transform = `translate(${x - 6}px, ${y - 4}px) scale(${press ? .85 : 1})`;
  ripple(t, clicks.map(([c, s]) => [c, center(s)]));
}

window.renderAt = function (t) {
  renderHook(t); renderBrand(t); renderCaptions(t); renderWindow(t);
  renderTabs(t); renderUpload(t); renderChat(t); renderFlash(t); renderFlow(t);
  renderCursor(t);
};

window.ready = (async () => {
  await document.fonts.ready;
  await document.fonts.load('600 64px Inter');
  mermaid.initialize({ startOnLoad: false, theme: 'base', securityLevel: 'strict',
    themeVariables: { fontFamily: 'Inter', fontSize: '18px', primaryColor: '#f8f9fa', primaryBorderColor: '#4a90e2', lineColor: '#666', primaryTextColor: '#333' },
    flowchart: { htmlLabels: false, nodeSpacing: 40, rankSpacing: 46, padding: 14 } });
  // Render the flowchart while its tab is visible so mermaid can measure text.
  setOp($('#view-work'), 1); setOp($('#tab-flow'), 1);
  const { svg } = await mermaid.render('flow-svg', FLOW);
  $('#diagram').innerHTML = svg;
  const s = $('#diagram svg');
  s.style.height = '430px'; s.style.width = 'auto'; s.style.maxWidth = '100%';
  flowNodes = [...s.querySelectorAll('g.node')].map((g) => {
    const m = g.id.match(/flowchart-(\w+?)-\d+$/);
    return [g, NODE_STEP[m ? m[1] : 'A'] ?? 0];
  });
  flowEdges = [...s.querySelectorAll('path.flowchart-link')].map((p) => {
    const m = (p.id || '').match(/^L[_-]([A-Z])[_-]([A-Z])/);
    return [p, m ? NODE_STEP[m[2]] : 1];
  });
  window.renderAt(0);
  return { nodes: flowNodes.length, edges: flowEdges.length };
})();
