import { Component, Input, OnChanges, OnDestroy, SimpleChanges, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MascotComponent, MascotMood } from '../../shared/mascot/mascot.component';

const THINKING_LINES = [
  'Thinking',
  'Reading your document',
  'Flipping through pages',
  'Connecting the dots',
  'Consulting the clouds',
  'Polishing the halo',
];

@Component({
  selector: 'app-message',
  standalone: true,
  imports: [CommonModule, MascotComponent],
  templateUrl: './message.component.html',
  styleUrl: './message.component.scss'
})
export class MessageComponent implements OnChanges, OnDestroy {
  @Input() question: string = '';
  @Input() answer: string = '';
  @Input() sources: string[] = [];
  @Input() citations: Array<{
    source: string;
    doc_id?: string;
    chunk_id?: string;
    chunk_index?: number;
  }> = [];
  @Input() cached: boolean = false;
  /** Parts of a live-steered answer; each part after the first starts where a dial moved. */
  @Input() segments: Array<{ text: string; label?: string }> = [];
  @Input() streaming: boolean = false;
  @Input() notSaved: boolean = false;
  /** Only the newest message animates its mascot, so old ones don't run timers. */
  @Input() animate: boolean = false;

  readonly thinkingLine = signal(THINKING_LINES[0]);
  readonly copied = signal(false);
  private lineTimer: ReturnType<typeof setInterval> | null = null;

  get thinking(): boolean {
    return this.streaming && !this.answer;
  }

  get mood(): MascotMood {
    if (this.thinking) return 'thinking';
    if (this.streaming) return 'talking';
    return 'idle';
  }

  ngOnChanges(_: SimpleChanges): void {
    if (this.thinking && !this.lineTimer) {
      let i = 0;
      this.thinkingLine.set(THINKING_LINES[0]);
      this.lineTimer = setInterval(() => {
        i = (i + 1) % THINKING_LINES.length;
        this.thinkingLine.set(THINKING_LINES[i]);
      }, 1800);
    } else if (!this.thinking && this.lineTimer) {
      clearInterval(this.lineTimer);
      this.lineTimer = null;
    }
  }

  async copy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(this.answer);
      this.copied.set(true);
      setTimeout(() => this.copied.set(false), 1500);
    } catch {
      /* clipboard blocked: nothing to do */
    }
  }

  ngOnDestroy(): void {
    if (this.lineTimer) clearInterval(this.lineTimer);
  }
}
