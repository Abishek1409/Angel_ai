import { Component, ElementRef, EventEmitter, Input, Output, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { SteeringValues } from '../../shared/services/chat.service';

export interface SteerAxis {
  key: string;
  label: string;
  low: string;
  high: string;
}

// Keep in sync with AXES in backend/chat/steering.py
export const STEER_AXES: SteerAxis[] = [
  { key: 'depth', label: 'Depth', low: 'brief', high: 'thorough' },
  { key: 'level', label: 'Level', low: 'beginner', high: 'expert' },
  { key: 'tone', label: 'Tone', low: 'friendly', high: 'formal' },
  { key: 'format', label: 'Format', low: 'prose', high: 'steps' },
  { key: 'grounding', label: 'Grounding', low: 'strict', high: 'broad' },
];

export function neutralSteering(): SteeringValues {
  return Object.fromEntries(STEER_AXES.map((a) => [a.key, 50]));
}

/** Short human label for one axis value, e.g. "tone: formal 80%". */
export function describeAxis(axis: SteerAxis, value: number): string {
  if (Math.abs(value - 50) < 12) return `${axis.label.toLowerCase()}: balanced`;
  const pole = value < 50 ? axis.low : axis.high;
  const strength = Math.round(Math.abs(value - 50) * 2);
  return `${axis.label.toLowerCase()}: ${pole} ${strength}%`;
}

const CX = 120;
const CY = 118;
const R = 92;

@Component({
  selector: 'app-steer-dial',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './steer-dial.component.html',
  styleUrl: './steer-dial.component.scss',
})
export class SteerDialComponent {
  /** Current dial values (0-100 per axis). Mutated in place while dragging. */
  @Input() values: SteeringValues = neutralSteering();
  /** True while an answer is streaming, so changes steer it live. */
  @Input() live = false;
  /** Fires when the user settles on a new value (release, key press, reset). */
  @Output() commit = new EventEmitter<SteeringValues>();

  @ViewChild('svg', { static: true }) svgRef!: ElementRef<SVGSVGElement>;

  readonly axes = STEER_AXES;
  readonly ticks = [0, 25, 50, 75, 100];
  readonly trackPath = `M ${CX - R} ${CY} A ${R} ${R} 0 0 1 ${CX + R} ${CY}`;
  activeKey = 'depth';
  dragging = false;
  private startValue = 50;
  private keyTimer: ReturnType<typeof setTimeout> | null = null;

  get axis(): SteerAxis {
    return this.axes.find((a) => a.key === this.activeKey)!;
  }

  get value(): number {
    return this.values[this.activeKey] ?? 50;
  }

  get readout(): string {
    return describeAxis(this.axis, this.value);
  }

  get changedCount(): number {
    return this.axes.filter((a) => Math.abs((this.values[a.key] ?? 50) - 50) >= 12).length;
  }

  isSteered(key: string): boolean {
    return Math.abs((this.values[key] ?? 50) - 50) >= 12;
  }

  point(value: number, radius = R): { x: number; y: number } {
    const angle = Math.PI * (1 - value / 100);
    return { x: CX + radius * Math.cos(angle), y: CY - radius * Math.sin(angle) };
  }

  /** Accent arc from neutral (top) to the knob, showing how hard the dial pushes. */
  get activePath(): string {
    const from = this.point(50);
    const to = this.point(this.value);
    const sweep = this.value > 50 ? 1 : 0;
    return `M ${from.x} ${from.y} A ${R} ${R} 0 0 ${sweep} ${to.x} ${to.y}`;
  }

  get knob() {
    return this.point(this.value);
  }

  get center() {
    return { x: CX, y: CY };
  }

  selectAxis(key: string): void {
    this.activeKey = key;
  }

  onPointerDown(event: PointerEvent): void {
    event.preventDefault();
    this.dragging = true;
    this.startValue = this.value;
    (event.currentTarget as Element).setPointerCapture(event.pointerId);
    this.updateFromPointer(event);
  }

  onPointerMove(event: PointerEvent): void {
    if (this.dragging) this.updateFromPointer(event);
  }

  onPointerUp(): void {
    if (!this.dragging) return;
    this.dragging = false;
    if (this.value !== this.startValue) this.emitCommit();
  }

  onKeyDown(event: KeyboardEvent): void {
    const step = event.shiftKey ? 10 : 5;
    let next = this.value;
    if (event.key === 'ArrowRight' || event.key === 'ArrowUp') next += step;
    else if (event.key === 'ArrowLeft' || event.key === 'ArrowDown') next -= step;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = 100;
    else return;
    event.preventDefault();
    this.values[this.activeKey] = Math.max(0, Math.min(100, next));
    // Wait for the user to stop pressing before restarting the stream
    if (this.keyTimer) clearTimeout(this.keyTimer);
    this.keyTimer = setTimeout(() => this.emitCommit(), 350);
  }

  reset(): void {
    for (const a of this.axes) this.values[a.key] = 50;
    this.emitCommit();
  }

  private emitCommit(): void {
    this.commit.emit({ ...this.values });
  }

  private updateFromPointer(event: PointerEvent): void {
    const svg = this.svgRef.nativeElement;
    const matrix = svg.getScreenCTM();
    if (!matrix) return;
    const p = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
    let angle = Math.atan2(CY - p.y, p.x - CX);
    // Below the dial's baseline: snap to the nearer end
    if (angle < 0) angle = p.x < CX ? Math.PI : 0;
    this.values[this.activeKey] = Math.round((1 - angle / Math.PI) * 100);
  }
}
