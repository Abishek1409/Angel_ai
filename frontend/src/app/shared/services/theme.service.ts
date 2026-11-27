import { Injectable, signal } from '@angular/core';

export type Theme = 'light' | 'dark';

const STORAGE_KEY = 'angelai_theme';

// Size of the ink mask's viewBox relative to the splat's base radius (room for droplets)
const MASK_HALF = 1.45;
// Smallest radius the wobbly edge can reach, as a fraction of the base radius
const MIN_EDGE = 0.72;

@Injectable({ providedIn: 'root' })
export class ThemeService {
  readonly theme = signal<Theme>(this.initialTheme());
  private animating = false;

  constructor() {
    this.apply(this.theme());
  }

  /**
   * Switch themes. The new theme spreads out from `origin` (the toggle button)
   * like spilled ink, using a View Transition masked by a random splat shape.
   */
  async toggle(origin?: { x: number; y: number }): Promise<void> {
    if (this.animating) return;
    const next: Theme = this.theme() === 'dark' ? 'light' : 'dark';
    const doc = document as Document & { startViewTransition?: (cb: () => void) => { finished: Promise<void>; ready: Promise<void> } };
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (!doc.startViewTransition || reduceMotion) {
      this.apply(next);
      return;
    }

    const x = origin?.x ?? window.innerWidth - 40;
    const y = origin?.y ?? 32;
    const farthest = Math.max(
      Math.hypot(x, y),
      Math.hypot(window.innerWidth - x, y),
      Math.hypot(x, window.innerHeight - y),
      Math.hypot(window.innerWidth - x, window.innerHeight - y),
    );
    // Grow until even the splat's innermost dent covers the farthest corner
    const endRadius = (farthest / MIN_EDGE) * MASK_HALF;

    const root = document.documentElement;
    root.style.setProperty('--ink-mask', `url("data:image/svg+xml,${encodeURIComponent(inkSplatSvg())}")`);
    root.style.setProperty('--ink-x', `${x}px`);
    root.style.setProperty('--ink-y', `${y}px`);
    root.style.setProperty('--ink-r-end', `${endRadius}px`);
    root.classList.add('ink-transition');
    this.animating = true;

    try {
      const transition = doc.startViewTransition(() => this.apply(next));
      await transition.finished;
    } finally {
      root.classList.remove('ink-transition');
      this.animating = false;
    }
  }

  private apply(theme: Theme): void {
    this.theme.set(theme);
    document.documentElement.dataset['theme'] = theme;
    localStorage.setItem(STORAGE_KEY, theme);
  }

  private initialTheme(): Theme {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'light' || saved === 'dark') return saved;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
}

/**
 * A fresh ink-splat shape for each toggle: a blob with a wobbly, spiky edge,
 * a few tendrils, and droplets flung past the rim. Drawn in a viewBox of
 * ±MASK_HALF around a base radius of 1.
 */
function inkSplatSvg(): string {
  const rand = mulberry32((Math.random() * 2 ** 32) >>> 0);
  // Broad lobes plus progressively finer ripples give the ragged, wet edge
  const waves = [3, 5, 8, 13, 21, 34, 55].map((base, i) => ({
    freq: base + Math.floor(rand() * 3),
    amp: 0.06 / Math.pow(1.7, i),
    phase: rand() * Math.PI * 2,
  }));
  const tendrils = Array.from({ length: 12 + Math.floor(rand() * 8) }, () => ({
    at: rand() * Math.PI * 2,
    width: 0.015 + rand() * 0.05,
    length: 0.08 + rand() * 0.32,
  }));

  const steps = 540;
  const points: string[] = [];
  for (let i = 0; i < steps; i++) {
    const a = (i / steps) * Math.PI * 2;
    let r = 0.9;
    for (const w of waves) r += w.amp * Math.sin(w.freq * a + w.phase);
    for (const t of tendrils) {
      const d = Math.atan2(Math.sin(a - t.at), Math.cos(a - t.at));
      r += t.length * Math.exp(-(d * d) / (2 * t.width * t.width));
    }
    r = Math.max(r, MIN_EDGE);
    points.push(`${(Math.cos(a) * r).toFixed(4)},${(Math.sin(a) * r).toFixed(4)}`);
  }

  const drops: string[] = [];
  for (let i = 0; i < 46; i++) {
    const a = rand() * Math.PI * 2;
    // Most droplets hug the rim; a few fly further out and get smaller
    const dist = 0.98 + Math.pow(rand(), 1.8) * 0.42;
    const size = 0.008 + rand() * 0.05 * (1.42 - dist);
    drops.push(`<circle cx="${(Math.cos(a) * dist).toFixed(4)}" cy="${(Math.sin(a) * dist).toFixed(4)}" r="${size.toFixed(4)}"/>`);
  }

  const h = MASK_HALF;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${-h} ${-h} ${h * 2} ${h * 2}"><g fill="#000"><polygon points="${points.join(' ')}"/>${drops.join('')}</g></svg>`;
}

/** Small seeded PRNG so one splat's numbers are consistent. */
function mulberry32(seed: number): () => number {
  return () => {
    seed = (seed + 0x6d2b79f5) >>> 0;
    let t = seed;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
