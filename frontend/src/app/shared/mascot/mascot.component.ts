import { Component, Input, OnDestroy, OnInit, signal } from '@angular/core';

export type MascotMood = 'idle' | 'thinking' | 'talking' | 'happy';

const QUIPS = [
  'YO! DROP A PDF.',
  'HALO? MORE LIKE HELLO.',
  'I READ THE BORING PARTS.',
  'HEAVENLY STUDY BUDDY.',
  '+1 UP: KNOWLEDGE',
  'TOO COOL FOR NOTES.',
  'PRESS START TO LEARN',
  'BLESSED BY RAG.',
];

/** Palette for the sprite. Outline stays dark in both themes, like an old cartridge sprite. */
const PALETTE: Record<string, string> = {
  K: '#1d1a16', // outline
  Y: '#ffd24a', // halo / gold
  y: '#fff4b8', // halo glow
  D: '#c98a12', // halo underside
  H: '#f0a92e', // hair
  S: '#f7c3a0', // skin
  B: '#ef8f73', // blush
  G: '#262a33', // lens
  L: '#ffffff', // glint
  W: '#ffffff', // wing
  w: '#cfd8e6', // wing shade
  R: '#fff2d6', // robe
  O: '#e5825c', // stripe
  E: '#e0413a', // high-tops
  M: '#7a2a20', // open mouth
};

const W = 24;

// Left halves (12 px), mirrored into 24-px rows. Row comments name the part.
const BASE_LEFT = [
  '........yYYY', //  0 halo ring (top)
  '......YY....', //  1 (sides)
  '........DDDD', //  2 (underside)
  '............', //  3 (halo float gap)
  '.........KKK', //  4 hair
  '.......KKHHH', //  5
  '......KHHHHH', //  6
  '......KHHSSS', //  7
  '.....KKKKKKK', //  8 shades frame
  '.....KSKGLGK', //  9 lenses
  '......KSKGGK', // 10
  '......KBSSSS', // 11 cheeks
  '......KSSSSS', // 12
  '.......KSSSS', // 13 mouth row
  '........KKKK', // 14 chin
  '..KKK....KRR', // 15 wings / collar
  '.KWWWK..KRRR', // 16
  'KWWWwWKKRRRR', // 17
  'KWWwwKSKRRRY', // 18 chain medal
  '.KWwwKSKRRRR', // 19
  '..KKKKSKRRRR', // 20
  '......KKOOOO', // 21 stripe
  '......KYYYYY', // 22
  '......KKKKKK', // 23 hem
  '........KSK.', // 24 legs
  '......KEEEK.', // 25 high-tops
  '......KWWWK.', // 26 soles
  '.......KKK..', // 27
];

type Grid = string[][];

function mirror(rows: string[]): Grid {
  return rows.map((r) => (r + [...r].reverse().join('')).split(''));
}

function put(g: Grid, row: number, col: number, s: string): void {
  [...s].forEach((ch, i) => (g[row][col + i] = ch));
}

function base(): Grid {
  const g = mirror(BASE_LEFT);
  put(g, 12, 10, 'KKK'); // smirk...
  put(g, 11, 13, 'K'); // ...rising on the right
  put(g, 7, 13, 'KK'); // raised brow
  return g;
}

/** Move the wing pixels (cols 0-5 and 18-23, rows 15-20) up one row: a flap. */
function flap(g: Grid): Grid {
  const out = g.map((r) => [...r]);
  for (const [from, to] of [[0, 6], [18, 24]]) {
    for (let r = 14; r <= 20; r++) {
      for (let c = from; c < to; c++) out[r][c] = r + 1 <= 20 ? g[r + 1][c] : '.';
    }
  }
  return out;
}

/** Shift the halo (rows 0-2) down by one into the float gap. */
function haloDown(g: Grid): Grid {
  const out = g.map((r) => [...r]);
  for (let c = 0; c < W; c++) {
    out[3][c] = g[2][c];
    out[2][c] = g[1][c];
    out[1][c] = g[0][c];
    out[0][c] = '.';
  }
  return out;
}

function glowHalo(g: Grid): Grid {
  // Halo sits in rows 0-3 (it bobs); brighten every gold pixel there
  const glow: Record<string, string> = { Y: 'y', D: 'Y' };
  return g.map((row, y) => (y <= 3 ? row.map((ch) => glow[ch] ?? ch) : [...row]));
}

function openMouth(g: Grid): Grid {
  const out = g.map((r) => [...r]);
  put(out, 11, 13, 'S');
  put(out, 12, 10, 'KKKK');
  put(out, 13, 10, 'KMMK');
  return out;
}

/** Shades pushed up onto the hair, eyes looking up: thinking face. */
function thinkingFace(g: Grid, lookRight: boolean): Grid {
  const out = g.map((r) => [...r]);
  put(out, 6, 5, 'KKKKKKKKKKKKKK');
  put(out, 7, 5, 'KKGLGGKKGLGGKK');
  put(out, 8, 5, '.KSSSSSSSSSSK.');
  put(out, 9, 5, '.KSSSSSSSSSSK.');
  put(out, 10, 6, 'KSSSSSSSSSSK');
  const e = lookRight ? 1 : 0;
  put(out, 9, 8 + e, 'K');
  put(out, 9, 14 + e, 'K');
  put(out, 11, 13, 'S'); // little "hmm" mouth
  put(out, 12, 10, 'SKKS');
  // hand on chin
  put(out, 14, 7, 'KSSK');
  put(out, 15, 7, 'KSK');
  return out;
}

/** Shades slide down, ^^ eyes, arms up. */
function happyFace(g: Grid, armsUp: boolean): Grid {
  const out = g.map((r) => [...r]);
  put(out, 6, 5, 'KKKKKKKKKKKKKK');
  put(out, 7, 5, 'KKGLGGKKGLGGKK');
  put(out, 8, 5, '.KSSSSSSSSSSK.');
  put(out, 9, 5, '.KSSKSSSSKSSK.');
  put(out, 10, 6, 'KSKSKSSKSKSK');
  put(out, 11, 6, 'KBSKSSSSKSBK');
  put(out, 12, 6, 'KSSSKKKKSSSK'); // grin
  if (armsUp) {
    for (const c of [5, 18]) {
      put(out, 13, c, 'K');
      put(out, 14, c, 'S');
      put(out, 15, c, 'S');
      put(out, 16, c, 'K');
    }
  }
  return out;
}

const FRAMES: Record<MascotMood, { frames: Grid[]; ms: number }> = (() => {
  const b = base();
  return {
    idle: { frames: [b, haloDown(flap(b)), b, flap(b)], ms: 420 },
    talking: { frames: [openMouth(b), flap(b), openMouth(flap(b)), b], ms: 150 },
    thinking: {
      frames: [
        thinkingFace(b, false),
        glowHalo(haloDown(thinkingFace(b, false))),
        thinkingFace(b, true),
        glowHalo(haloDown(thinkingFace(b, true))),
      ],
      ms: 380,
    },
    happy: { frames: [happyFace(b, true), happyFace(flap(b), false)], ms: 180 },
  };
})();

interface Run { x: number; y: number; w: number; fill: string; }

/** Merge same-colour neighbours in a row into one rect: ~4x fewer elements. */
function toRuns(g: Grid): Run[] {
  const runs: Run[] = [];
  g.forEach((row, y) => {
    let x = 0;
    while (x < row.length) {
      const ch = row[x];
      if (ch === '.') { x++; continue; }
      let end = x + 1;
      while (end < row.length && row[end] === ch) end++;
      runs.push({ x, y, w: end - x, fill: PALETTE[ch] });
      x = end;
    }
  });
  return runs;
}

const RUNS: Record<MascotMood, Run[][]> = Object.fromEntries(
  Object.entries(FRAMES).map(([mood, { frames }]) => [mood, frames.map(toRuns)]),
) as Record<MascotMood, Run[][]>;

/**
 * AngelAI's mascot: a 24x28 pixel-art angel in a 90s-game style, with frame
 * animations per mood. Click (when `talk`) for a jump, a wink and a quip.
 */
@Component({
  selector: 'app-mascot',
  standalone: true,
  template: `
    <button
      type="button"
      class="sprite"
      [class.sprite--jump]="mood() === 'happy'"
      [style.width.px]="size"
      [style.--px]="size / 24 + 'px'"
      [attr.aria-label]="label"
      [attr.tabindex]="talk ? 0 : -1"
      [disabled]="!talk"
      (click)="poke()"
    >
      @if (quip()) {
        <span class="sprite__bubble" role="status">{{ quip() }}</span>
      }
      @if (mood() === 'thinking') {
        <svg class="sprite__think" viewBox="0 0 12 9" shape-rendering="crispEdges" aria-hidden="true">
          <rect x="1" y="0" width="10" height="1" fill="#1d1a16" />
          <rect x="0" y="1" width="1" height="4" fill="#1d1a16" />
          <rect x="11" y="1" width="1" height="4" fill="#1d1a16" />
          <rect x="1" y="5" width="10" height="1" fill="#1d1a16" />
          <rect x="1" y="1" width="10" height="4" fill="#fffdf6" />
          @for (d of [0, 1, 2]; track d) {
            @if (dots() > d) {
              <rect [attr.x]="2 + d * 3" y="2" width="2" height="2" fill="#1d1a16" />
            }
          }
          <rect x="2" y="6" width="2" height="1" fill="#1d1a16" />
          <rect x="0" y="8" width="1" height="1" fill="#1d1a16" />
        </svg>
      }
      <svg class="sprite__img" [attr.viewBox]="'0 0 24 28'" shape-rendering="crispEdges" aria-hidden="true">
        @for (r of runs(); track $index) {
          <rect [attr.x]="r.x" [attr.y]="r.y" [attr.width]="r.w" height="1" [attr.fill]="r.fill" />
        }
      </svg>
    </button>
  `,
  styles: [`
    :host { display: inline-block; line-height: 0; }
    .sprite {
      position: relative;
      display: block;
      padding: 0;
      border: 0;
      background: none;
      cursor: pointer;
      image-rendering: pixelated;
      -webkit-tap-highlight-color: transparent;
    }
    .sprite:disabled { cursor: default; }
    .sprite:focus-visible { outline: 2px solid var(--border-focus); outline-offset: 3px; border-radius: 4px; }
    .sprite__img {
      display: block;
      width: 100%;
      height: auto;
      overflow: visible;
      /* one-sprite-pixel sticker rim (visible on dark themes), then a retro offset shadow */
      filter:
        drop-shadow(var(--px) 0 0 var(--sprite-rim, transparent))
        drop-shadow(calc(var(--px) * -1) 0 0 var(--sprite-rim, transparent))
        drop-shadow(0 var(--px) 0 var(--sprite-rim, transparent))
        drop-shadow(0 calc(var(--px) * -1) 0 var(--sprite-rim, transparent))
        drop-shadow(var(--px) var(--px) 0 var(--sprite-shadow, rgba(201, 100, 66, .45)));
    }
    .sprite--jump .sprite__img { animation: sprite-jump .36s steps(3) 2; }
    @keyframes sprite-jump { 50% { transform: translateY(-14%); } }

    .sprite__think {
      position: absolute;
      left: 72%;
      bottom: 84%;
      width: 60%;
      height: auto;
      animation: think-float 1.2s steps(2) infinite;
    }
    @keyframes think-float { 50% { transform: translateY(-6%); } }

    .sprite__bubble {
      position: absolute;
      bottom: calc(100% + 6px);
      left: 50%;
      z-index: 3;
      width: max-content;
      max-width: 220px;
      padding: 8px 10px;
      border: 3px solid #1d1a16;
      background: #fffdf6;
      color: #1d1a16;
      font: 9px/1.5 'Press Start 2P', ui-monospace, monospace;
      text-align: center;
      box-shadow: 3px 3px 0 #1d1a16;
      transform: translateX(-50%);
      animation: bubble-in .2s steps(2);
      pointer-events: none;
      white-space: normal;
    }
    @keyframes bubble-in { from { transform: translateX(-50%) scale(.5); } }

    @media (prefers-reduced-motion: reduce) {
      .sprite--jump .sprite__img, .sprite__think { animation: none; }
    }
  `],
})
export class MascotComponent implements OnInit, OnDestroy {
  /** Rendered width in px (height is 28/24 of it). Multiples of 24 stay pixel-perfect. */
  @Input() size = 96;
  /** Clickable: jump + quip. */
  @Input() talk = true;
  /** Hold on the first frame (tiny placements, older chat messages). */
  @Input() set still(value: boolean) {
    const changed = value !== this.isStill;
    this.isStill = value;
    if (changed && this.started) this.restart();
  }
  get still(): boolean {
    return this.isStill;
  }
  private isStill = false;
  private started = false;
  /** Animation set to play. 'happy' is also triggered by clicks. */
  @Input() set state(value: MascotMood) {
    this.requested = value;
    if (!this.happyTimer) this.mood.set(value);
  }

  readonly mood = signal<MascotMood>('idle');
  readonly frame = signal(0);
  readonly quip = signal('');
  readonly dots = signal(1);
  readonly label = 'AngelAI mascot';

  private requested: MascotMood = 'idle';
  private ticker: ReturnType<typeof setTimeout> | null = null;
  private happyTimer: ReturnType<typeof setTimeout> | null = null;
  private lastQuip = -1;

  runs(): Run[] {
    const frames = RUNS[this.mood()];
    return frames[this.still ? 0 : this.frame() % frames.length];
  }

  ngOnInit(): void {
    this.started = true;
    this.tick();
  }

  private restart(): void {
    if (this.ticker) clearTimeout(this.ticker);
    this.ticker = null;
    this.tick();
  }

  poke(): void {
    if (!this.talk) return;
    let i = Math.floor(Math.random() * QUIPS.length);
    if (i === this.lastQuip) i = (i + 1) % QUIPS.length;
    this.lastQuip = i;
    this.quip.set(QUIPS[i]);
    this.mood.set('happy');
    if (this.happyTimer) clearTimeout(this.happyTimer);
    this.happyTimer = setTimeout(() => {
      this.happyTimer = null;
      this.quip.set('');
      this.mood.set(this.requested);
    }, 2000);
  }

  ngOnDestroy(): void {
    if (this.ticker) clearTimeout(this.ticker);
    if (this.happyTimer) clearTimeout(this.happyTimer);
  }

  private tick(): void {
    const reduce = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce || this.isStill) {
      this.frame.set(0);
      this.dots.set(3);
      this.ticker = null;
      return;
    }
    this.frame.update((f) => f + 1);
    this.dots.update((d) => (d % 3) + 1);
    this.ticker = setTimeout(() => this.tick(), FRAMES[this.mood()].ms);
  }
}
