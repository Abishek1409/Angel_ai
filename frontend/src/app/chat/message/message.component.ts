import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-message',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './message.component.html',
  styleUrl: './message.component.scss'
})
export class MessageComponent {
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
}
