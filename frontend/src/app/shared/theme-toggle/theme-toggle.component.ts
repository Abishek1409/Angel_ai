import { Component, computed, inject, signal } from '@angular/core';
import { ThemeService } from '../services/theme.service';

@Component({
  selector: 'app-theme-toggle',
  standalone: true,
  template: `
    <button
      type="button"
      class="yy"
      [attr.aria-label]="label()"
      [attr.title]="label()"
      [attr.aria-pressed]="theme.theme() === 'dark'"
      (click)="onClick($event)"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true" [style.transform]="'rotate(' + turns() * 180 + 'deg)'">
        <circle class="yy__light" cx="12" cy="12" r="11" />
        <path class="yy__dark" d="M12 1a11 11 0 0 1 0 22a5.5 5.5 0 0 1 0-11a5.5 5.5 0 0 0 0-11z" />
        <circle class="yy__dark" cx="12" cy="6.5" r="1.9" />
        <circle class="yy__light" cx="12" cy="17.5" r="1.9" />
        <circle class="yy__rim" cx="12" cy="12" r="11" />
      </svg>
    </button>
  `,
  styles: [`
    :host { display: inline-flex; }
    .yy {
      width: 36px;
      height: 36px;
      display: grid;
      place-items: center;
      padding: 0;
      border: 1px solid var(--border);
      border-radius: 50%;
      background: var(--bg-card);
      cursor: pointer;
      transition: border-color .2s, box-shadow .2s, transform .2s;
    }
    .yy:hover { border-color: var(--border-focus); box-shadow: var(--shadow-md); }
    .yy:hover svg { filter: drop-shadow(0 0 3px var(--accent-border)); }
    .yy:active { transform: scale(.92); }
    .yy:focus-visible { outline: 2px solid var(--border-focus); outline-offset: 2px; }
    svg {
      width: 24px;
      height: 24px;
      transition: transform 1.1s cubic-bezier(.55, .05, .25, 1);
    }
    .yy__dark { fill: var(--text); }
    .yy__light { fill: var(--bg-card); }
    .yy__rim { fill: none; stroke: var(--text); stroke-width: 1; }
    @media (prefers-reduced-motion: reduce) { svg { transition: none; } }
  `],
})
export class ThemeToggleComponent {
  readonly theme = inject(ThemeService);
  readonly turns = signal(0);
  readonly label = computed(() => (this.theme.theme() === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'));

  onClick(event: MouseEvent): void {
    const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
    this.turns.update((t) => t + 1);
    this.theme.toggle({ x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 });
  }
}
