import { Component, Input, OnDestroy, signal } from '@angular/core';

const QUIPS = [
  'Yo! Drop a PDF, I got you.',
  "Halo? More like hello.",
  'Ask me anything. I read the boring parts.',
  'Certified heavenly study buddy.',
  'Too cool for unread notes.',
  'Wings out, knowledge in.',
  'I skimmed it so you don’t have to.',
  'Blessed by RAG. Literally.',
];

/**
 * AngelAI's mascot: a retro, slightly too-cool angel. Pure SVG + CSS animation.
 * Idle: bobs, flaps, halo wobbles, shades glint. Click: shades slide down for a
 * wink and it drops a one-liner.
 */
@Component({
  selector: 'app-mascot',
  standalone: true,
  template: `
    <button
      type="button"
      class="mascot"
      [class.mascot--peek]="peeking()"
      [class.mascot--still]="still"
      [style.width.px]="size"
      [attr.aria-label]="talk ? 'AngelAI mascot. Click for a one-liner' : 'AngelAI mascot'"
      [attr.tabindex]="talk ? 0 : -1"
      (click)="poke()"
    >
      @if (talk && quip()) {
        <span class="mascot__bubble" role="status">{{ quip() }}</span>
      }
      <svg viewBox="0 0 200 240" aria-hidden="true">
        <defs>
          <clipPath [attr.id]="uid + '-lens'">
            <rect x="73" y="69" width="24" height="15" rx="5" />
            <rect x="103" y="69" width="24" height="15" rx="5" />
          </clipPath>
        </defs>

        <ellipse class="m-ground" cx="100" cy="229" rx="46" ry="6" />

        <g class="m-figure">
          <!-- wings -->
          <g class="m-wing m-wing--l">
            <path class="m-wing-fill" d="M74 124 C46 98 14 108 22 128 C10 136 20 152 36 147 C34 162 56 164 64 150 C70 146 74 136 74 124 Z" />
            <path class="m-line-thin" d="M30 130 C40 132 50 130 60 126 M40 146 C48 144 56 140 64 134" />
          </g>
          <g class="m-wing m-wing--r">
            <path class="m-wing-fill" d="M126 124 C154 98 186 108 178 128 C190 136 180 152 164 147 C166 162 144 164 136 150 C130 146 126 136 126 124 Z" />
            <path class="m-line-thin" d="M170 130 C160 132 150 130 140 126 M160 146 C152 144 144 140 136 134" />
          </g>

          <g class="m-body">
            <!-- legs + high-tops -->
            <rect class="m-skin" x="84" y="194" width="11" height="16" />
            <rect class="m-skin" x="105" y="194" width="11" height="16" />
            <g class="m-shoe">
              <path class="m-shoe-top" d="M76 206 h22 v12 h-26 c-2 0 -3 -2 -2 -4 z" />
              <rect class="m-sole" x="68" y="216" width="32" height="7" rx="3.5" />
              <path class="m-lace" d="M82 209 h12 M82 213 h12" />
            </g>
            <g class="m-shoe">
              <path class="m-shoe-top" d="M102 206 h22 l6 8 c1 2 0 4 -2 4 h-26 z" />
              <rect class="m-sole" x="100" y="216" width="32" height="7" rx="3.5" />
              <path class="m-lace" d="M106 209 h12 M106 213 h12" />
            </g>

            <!-- robe -->
            <path class="m-robe" d="M74 118 Q100 108 126 118 L140 200 Q100 210 60 200 Z" />
            <path class="m-stripe-a" d="M63 182 Q100 191 137 182 L138.6 190 Q100 199 61.4 190 Z" />
            <path class="m-stripe-b" d="M61.4 190 Q100 199 138.6 190 L140 200 Q100 210 60 200 Z" />
            <path class="m-line-thin" d="M84 150 L80 176 M116 150 L120 176" />

            <!-- left arm on hip -->
            <path class="m-arm-line" d="M80 126 C62 136 56 152 74 162" />
            <path class="m-arm-fill" d="M80 126 C62 136 56 152 74 162" />
            <circle class="m-skin" cx="77" cy="162" r="6.5" />

            <!-- right arm: finger guns -->
            <g class="m-gun-arm">
              <path class="m-arm-line" d="M122 128 C140 134 150 142 156 132" />
              <path class="m-arm-fill" d="M122 128 C140 134 150 142 156 132" />
              <path class="m-hand" d="M152 124 h16 a3.5 3.5 0 0 1 0 7 h-8 v6 a4 4 0 0 1 -8 0 z" />
              <path class="m-hand" d="M154 124 l2 -8 a3 3 0 0 1 5.5 1.5 l-1.5 6.5" />
            </g>

            <!-- gold chain -->
            <path class="m-chain" d="M86 120 Q100 142 114 120" />
            <circle class="m-medal" cx="100" cy="140" r="8" />
            <text class="m-medal-text" x="100" y="143.6" text-anchor="middle">A</text>
          </g>

          <g class="m-head">
            <circle class="m-skin" cx="67" cy="82" r="7.5" />
            <circle class="m-skin" cx="133" cy="82" r="7.5" />
            <circle class="m-skin" cx="100" cy="80" r="34" />

            <!-- pompadour -->
            <path class="m-hair" d="M67 74 C62 46 86 32 102 40 C118 30 142 44 134 70 C126 58 112 58 102 62 C92 54 76 58 67 74 Z" />
            <path class="m-hair" d="M90 44 C88 22 118 14 126 30 C118 26 106 28 102 40 Z" />

            <circle class="m-blush" cx="78" cy="96" r="5" />
            <circle class="m-blush" cx="123" cy="94" r="5" />

            <!-- eyes (seen when the shades drop) -->
            <path class="m-line" d="M78 80 q7 -6 14 0" />
            <circle class="m-eye" cx="115" cy="78" r="3.4" />

            <!-- raised brow -->
            <path class="m-brow" d="M105 63 q10 -7 20 -2" />

            <path class="m-line" d="M100 86 q5 3 0 7" />
            <!-- smirk -->
            <path class="m-line m-smirk" d="M88 101 Q104 109 117 96" />
            <path class="m-tooth" d="M101 104.6 l1.5 4 l3 -1.2 l-0.4 -3.5 z" />

            <!-- shades -->
            <g class="m-shades">
              <path class="m-line" d="M73 74 L66 78 M127 74 L134 78" />
              <rect class="m-lens" x="73" y="69" width="24" height="15" rx="5" />
              <rect class="m-lens" x="103" y="69" width="24" height="15" rx="5" />
              <path class="m-line" d="M97 74 h6" />
              <g [attr.clip-path]="'url(#' + uid + '-lens)'">
                <rect class="m-glint" x="60" y="60" width="7" height="34" transform="skewX(-25)" />
              </g>
            </g>
          </g>

          <!-- halo -->
          <g class="m-halo">
            <ellipse class="m-halo-line" cx="104" cy="22" rx="30" ry="8" />
            <ellipse class="m-halo-ring" cx="104" cy="22" rx="30" ry="8" />
          </g>
          <path class="m-spark m-spark--1" d="M150 30 l2 6 l6 2 l-6 2 l-2 6 l-2 -6 l-6 -2 l6 -2 z" />
          <path class="m-spark m-spark--2" d="M54 22 l1.5 4 l4 1.5 l-4 1.5 l-1.5 4 l-1.5 -4 l-4 -1.5 l4 -1.5 z" />
        </g>
      </svg>
    </button>
  `,
  styles: [`
    :host { display: inline-block; --ink: #1d1a16; --skin: #f7c3a0; --robe: #fff4dc; --gold: #f2b63c; --stripe: #e5825c; --shoe: #d9433b; }
    .mascot {
      position: relative;
      display: block;
      padding: 0;
      border: 0;
      background: none;
      cursor: pointer;
      -webkit-tap-highlight-color: transparent;
    }
    .mascot:focus-visible { outline: 2px solid var(--border-focus); outline-offset: 4px; border-radius: 12px; }
    svg { display: block; width: 100%; height: auto; overflow: visible; }

    .m-figure { filter: drop-shadow(4px 4px 0 var(--accent)); }
    .m-ground { fill: var(--text); opacity: .12; }
    .m-skin, .m-hand { fill: var(--skin); stroke: var(--ink); stroke-width: 3; stroke-linejoin: round; }
    .m-hair { fill: var(--gold); stroke: var(--ink); stroke-width: 3; stroke-linejoin: round; }
    .m-robe { fill: var(--robe); stroke: var(--ink); stroke-width: 3.2; stroke-linejoin: round; }
    .m-stripe-a { fill: var(--gold); }
    .m-stripe-b { fill: var(--stripe); stroke: var(--ink); stroke-width: 3.2; stroke-linejoin: round; }
    .m-wing-fill { fill: #ffffff; stroke: var(--ink); stroke-width: 3; stroke-linejoin: round; }
    .m-line, .m-line-thin, .m-brow { fill: none; stroke: var(--ink); stroke-linecap: round; stroke-linejoin: round; }
    .m-line { stroke-width: 3; }
    .m-line-thin { stroke-width: 2; opacity: .55; }
    .m-brow { stroke-width: 3.4; }
    .m-eye { fill: var(--ink); }
    .m-blush { fill: var(--stripe); opacity: .35; }
    .m-tooth { fill: #fff; stroke: var(--ink); stroke-width: 1.2; stroke-linejoin: round; }
    .m-arm-line { fill: none; stroke: var(--ink); stroke-width: 15; stroke-linecap: round; }
    .m-arm-fill { fill: none; stroke: var(--robe); stroke-width: 9; stroke-linecap: round; }
    .m-shoe-top { fill: var(--shoe); stroke: var(--ink); stroke-width: 3; stroke-linejoin: round; }
    .m-sole { fill: #fff; stroke: var(--ink); stroke-width: 3; }
    .m-lace { stroke: #fff; stroke-width: 2; stroke-linecap: round; }
    .m-chain { fill: none; stroke: var(--gold); stroke-width: 3.2; stroke-dasharray: 3.2 2.2; stroke-linecap: round; }
    .m-medal { fill: var(--gold); stroke: var(--ink); stroke-width: 2.5; }
    .m-medal-text { fill: var(--ink); font: 800 10px/1 'Inter', system-ui, sans-serif; }
    .m-lens { fill: var(--ink); stroke: var(--ink); stroke-width: 3; }
    .m-glint { fill: #fff; opacity: .85; }
    .m-halo-line { fill: none; stroke: var(--ink); stroke-width: 9; }
    .m-halo-ring { fill: none; stroke: var(--gold); stroke-width: 4.5; }
    .m-spark { fill: var(--gold); stroke: var(--ink); stroke-width: 1.4; stroke-linejoin: round; }

    /* ── idle motion ── */
    .m-body, .m-head, .m-wing, .m-halo, .m-shades, .m-glint, .m-spark, .m-gun-arm, .m-ground {
      transform-box: fill-box;
    }
    .m-figure { animation: m-bob 2.4s ease-in-out infinite; }
    .m-ground { transform-origin: center; animation: m-ground 2.4s ease-in-out infinite; }
    .m-head { transform-origin: 50% 90%; animation: m-groove 2.4s ease-in-out infinite; }
    .m-wing--l { transform-origin: 100% 40%; animation: m-flap-l 1.2s ease-in-out infinite; }
    .m-wing--r { transform-origin: 0% 40%; animation: m-flap-r 1.2s ease-in-out infinite; }
    .m-halo { transform-origin: center; animation: m-halo 3.2s ease-in-out infinite; }
    .m-gun-arm { transform-origin: 0% 60%; animation: m-gun 4.8s ease-in-out infinite; }
    .m-glint { animation: m-glint 4s ease-in-out infinite; }
    .m-shades { transition: transform .35s cubic-bezier(.3, 1.6, .5, 1); }
    .m-spark { transform-origin: center; animation: m-twinkle 2s ease-in-out infinite; }
    .m-spark--2 { animation-delay: -1s; }

    .mascot:hover .m-figure { animation-duration: 1.1s; }
    .mascot:hover .m-head { animation-duration: 1.1s; }
    .mascot--peek .m-shades { transform: translateY(13px); }

    @keyframes m-bob { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-6px); } }
    @keyframes m-ground { 0%, 100% { transform: scaleX(1); opacity: .12; } 50% { transform: scaleX(.85); opacity: .08; } }
    @keyframes m-groove { 0%, 100% { transform: rotate(-3deg); } 50% { transform: rotate(4deg); } }
    @keyframes m-flap-l { 0%, 100% { transform: rotate(0); } 50% { transform: rotate(14deg); } }
    @keyframes m-flap-r { 0%, 100% { transform: rotate(0); } 50% { transform: rotate(-14deg); } }
    @keyframes m-halo { 0%, 100% { transform: rotate(-10deg) translateY(0); } 50% { transform: rotate(-4deg) translateY(-3px); } }
    @keyframes m-gun { 0%, 70%, 100% { transform: rotate(0); } 76% { transform: rotate(-12deg); } 82% { transform: rotate(4deg); } 88% { transform: rotate(-8deg); } }
    @keyframes m-glint { 0%, 55% { transform: skewX(-25deg) translateX(0); } 75%, 100% { transform: skewX(-25deg) translateX(90px); } }
    @keyframes m-twinkle { 0%, 100% { transform: scale(.6) rotate(0); opacity: .5; } 50% { transform: scale(1.1) rotate(45deg); opacity: 1; } }

    .mascot--still .m-figure, .mascot--still .m-head, .mascot--still .m-wing,
    .mascot--still .m-ground, .mascot--still .m-gun-arm { animation: none; }

    @media (prefers-reduced-motion: reduce) {
      .m-figure, .m-head, .m-wing, .m-halo, .m-gun-arm, .m-glint, .m-spark, .m-ground { animation: none; }
    }

    /* ── speech bubble ── */
    .mascot__bubble {
      position: absolute;
      bottom: calc(100% - 6px);
      left: 50%;
      z-index: 2;
      width: max-content;
      max-width: 210px;
      padding: .45rem .7rem;
      border: 2px solid var(--ink);
      border-radius: 12px;
      background: var(--robe);
      color: var(--ink);
      font-size: .8rem;
      font-weight: 600;
      line-height: 1.3;
      text-align: center;
      box-shadow: 3px 3px 0 var(--accent);
      transform: translateX(-50%);
      animation: m-pop .3s cubic-bezier(.3, 1.6, .5, 1);
      pointer-events: none;
    }
    .mascot__bubble::after {
      content: '';
      position: absolute;
      top: 100%;
      left: 50%;
      width: 10px;
      height: 10px;
      margin-top: -5px;
      border-right: 2px solid var(--ink);
      border-bottom: 2px solid var(--ink);
      background: var(--robe);
      transform: translateX(-50%) rotate(45deg);
    }
    @keyframes m-pop { from { transform: translateX(-50%) scale(.6); opacity: 0; } }
  `],
})
export class MascotComponent implements OnDestroy {
  /** Rendered width in px (height follows the 5:6 artwork). */
  @Input() size = 120;
  /** Show a one-liner when clicked. */
  @Input() talk = true;
  /** Turn off body motion (for tiny placements such as the header). */
  @Input() still = false;

  readonly uid = `mascot-${Math.random().toString(36).slice(2, 9)}`;
  readonly peeking = signal(false);
  readonly quip = signal('');
  private lastQuip = -1;
  private timer: ReturnType<typeof setTimeout> | null = null;

  poke(): void {
    this.peeking.set(true);
    if (this.talk) {
      let i = Math.floor(Math.random() * QUIPS.length);
      if (i === this.lastQuip) i = (i + 1) % QUIPS.length;
      this.lastQuip = i;
      this.quip.set(QUIPS[i]);
    }
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => {
      this.peeking.set(false);
      this.quip.set('');
    }, 2200);
  }

  ngOnDestroy(): void {
    if (this.timer) clearTimeout(this.timer);
  }
}
