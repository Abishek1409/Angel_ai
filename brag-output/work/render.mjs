// Usage: node render.mjs stills 0.5,1.2,...   -> work/stills/t_<t>.png
//        node render.mjs frames                -> work/frames/f_00000.jpg ... (30fps, 21s)
import { createServer } from 'node:http';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { join, extname, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const DIR = dirname(fileURLToPath(import.meta.url));
const FPS = 30, DURATION = 21;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9333, HTTP = 8765;
const [mode = 'stills', list = ''] = process.argv.slice(2);

// Static server bound to localhost only, serving just this work folder.
const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css' };
const server = createServer(async (req, res) => {
  const p = join(DIR, decodeURIComponent(new URL(req.url, 'http://x').pathname));
  if (!p.startsWith(DIR)) { res.writeHead(403).end(); return; }
  let body;
  try { body = await readFile(p); } catch { res.writeHead(404).end(); return; }
  res.writeHead(200, { 'Content-Type': types[extname(p)] || 'application/octet-stream' }).end(body);
}).listen(HTTP, '127.0.0.1');

const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--window-size=1920,1080',
  '--hide-scrollbars', '--force-device-scale-factor=1', '--no-first-run', '--no-default-browser-check',
  `--user-data-dir=${join(DIR, 'chrome-profile')}`, 'about:blank'], { stdio: 'ignore' });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let wsUrl;
for (let i = 0; i < 50 && !wsUrl; i++) {
  try { const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); wsUrl = list.find((x) => x.type === 'page')?.webSocketDebuggerUrl; } catch {}
  if (!wsUrl) await sleep(200);
}
const ws = new WebSocket(wsUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0; const pending = new Map(); const events = [];
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); } else events.push(d); };
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const evalJs = async (expr) => { const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true }); if (r.result.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails)); return r.result.result.value; };

await send('Page.enable'); await send('Runtime.enable');
await send('Emulation.setDeviceMetricsOverride', { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });
await send('Page.navigate', { url: `http://127.0.0.1:${HTTP}/index.html` });
for (let i = 0; i < 100; i++) { if (await evalJs('typeof window.ready').catch(() => '') === 'object') break; await sleep(100); }
for (const e of events) {
  if (e.method === 'Runtime.exceptionThrown') console.log('PAGE ERROR:', e.params.exceptionDetails.exception?.description || e.params.exceptionDetails.text);
  if (e.method === 'Runtime.consoleAPICalled' && e.params.type === 'error') console.log('CONSOLE:', e.params.args.map((a) => a.value ?? a.description).join(' '));
}
if (await evalJs('typeof window.ready') !== 'object') { console.log('scene not ready'); ws.close(); chrome.kill(); server.close(); process.exit(1); }
console.log('ready:', JSON.stringify(await evalJs('window.ready')));

const shot = async (t, format) => {
  await evalJs(`window.renderAt(${t}); new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))`);
  const r = await send('Page.captureScreenshot', { format, quality: format === 'jpeg' ? 95 : undefined, clip: { x: 0, y: 0, width: 1920, height: 1080, scale: 1 } });
  return Buffer.from(r.result.data, 'base64');
};

try {
  if (mode === 'audit') {
    for (const t of list.split(',').map(Number)) console.log(t, JSON.stringify(await evalJs(`window.audit(${t})`)));
  } else if (mode === 'stills') {
    await mkdir(join(DIR, 'stills'), { recursive: true });
    for (const t of list.split(',').map(Number)) await writeFile(join(DIR, 'stills', `t_${t.toFixed(2)}.png`), await shot(t, 'png'));
  } else {
    await mkdir(join(DIR, 'frames'), { recursive: true });
    const n = FPS * DURATION;
    for (let f = 0; f < n; f++) {
      await writeFile(join(DIR, 'frames', `f_${String(f).padStart(5, '0')}.jpg`), await shot(f / FPS, 'jpeg'));
      if (f % 60 === 0) console.log(`frame ${f}/${n}`);
    }
  }
} finally {
  ws.close(); chrome.kill(); server.close();
}
