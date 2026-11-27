import { Component, ElementRef, Input, Output, EventEmitter, OnInit, OnChanges, OnDestroy, SimpleChanges, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ChatService, SteeringValues } from '../shared/services/chat.service';
import { MessageComponent } from './message/message.component';
import { MascotComponent } from '../shared/mascot/mascot.component';
import { SteerDialComponent, STEER_AXES, describeAxis, neutralSteering } from './steer/steer-dial.component';
import { FlashcardsComponent } from '../flashcards/flashcards.component';
import { RoadmapComponent } from '../roadmap/roadmap.component';

type ChatTab = 'chat' | 'flashcards' | 'flowchart';

export interface Message {
  question: string;
  answer: string;
  sources?: string[];
  citations?: Array<{
    source: string;
    doc_id?: string;
    chunk_id?: string;
    chunk_index?: number;
  }>;
  cached?: boolean;
  segments?: AnswerSegment[];
  streaming?: boolean;
  notSaved?: boolean;
}

export interface AnswerSegment {
  text: string;
  /** Set when this segment began because a dial moved. */
  label?: string;
}

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule, MessageComponent, SteerDialComponent, MascotComponent, FlashcardsComponent, RoadmapComponent],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.scss'
})
export class ChatComponent implements OnInit, OnChanges, OnDestroy {
  @Input() documentId: string | null = null;
  @Input() sessionId: string = '';
  @Output() newDocument = new EventEmitter<void>();

  question: string = '';
  conversation: Message[] = [];
  isLoading: boolean = false;
  errorMessage: string = '';
  activeTab: ChatTab = 'chat';
  steering: SteeringValues = neutralSteering();
  steerOpen = false;
  liveMessage: Message | null = null;
  readonly suggestions = [
    'Summarize this in 5 bullet points',
    "Explain the key ideas like I'm new to this",
    'What are the main takeaways?',
    'Quiz me with 3 questions',
  ];
  readonly greeting = ChatComponent.pickGreeting();

  @ViewChild('scroller') private scroller?: ElementRef<HTMLElement>;
  @ViewChild('input') private inputEl?: ElementRef<HTMLTextAreaElement>;
  /** Follow new text only while the reader is already at the bottom. */
  private stickToBottom = true;
  private scrollQueued = false;

  get steeredCount(): number {
    return STEER_AXES.filter((a) => Math.abs((this.steering[a.key] ?? 50) - 50) >= 12).length;
  }

  private static pickGreeting(): string {
    const hour = new Date().getHours();
    const time = hour < 5 ? 'Up late' : hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
    const lines = [`${time}. What are we learning?`, 'Press start. What should we dig into?', `${time}! Ready when you are.`];
    return lines[Math.floor(Math.random() * lines.length)];
  }

  ask(text: string): void {
    this.question = text;
    this.onSubmit();
  }

  onEnter(event: Event): void {
    const e = event as KeyboardEvent;
    if (e.shiftKey || e.isComposing) return; // Shift+Enter: new line
    e.preventDefault();
    this.onSubmit();
  }

  autoGrow(el: HTMLTextAreaElement): void {
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 220)}px`;
  }

  onScroll(): void {
    const el = this.scroller?.nativeElement;
    if (!el) return;
    this.stickToBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  }

  private scrollToBottom(force = false): void {
    if (force) this.stickToBottom = true;
    if (!this.stickToBottom || this.scrollQueued) return;
    this.scrollQueued = true;
    requestAnimationFrame(() => {
      this.scrollQueued = false;
      const el = this.scroller?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
    });
  }
  private runSteering: SteeringValues | null = null;
  private abortController: AbortController | null = null;
  private runId = 0;

  constructor(private chatService: ChatService) {}

  ngOnDestroy(): void {
    this.runId++;
    this.abortController?.abort();
  }

  ngOnInit(): void {
    this.loadHistory();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['sessionId'] && changes['sessionId'].firstChange) {
      return;
    }

    if (changes['sessionId'] || changes['documentId']) {
      this.stopStreaming();
      if (changes['documentId'] && !this.documentId) {
        this.activeTab = 'chat';
      }
      if (!this.sessionId) {
        this.conversation = [];
        this.question = '';
        this.errorMessage = '';
        return;
      }
      this.loadHistory();
    }
  }

  private loadHistory(): void {
    this.chatService.getHistory(this.documentId, this.sessionId).subscribe({
      next: (res) => {
        const messages = res.messages;
        this.conversation = [];
        for (let index = 0; index < messages.length; index += 2) {
          const question = messages[index];
          const answer = messages[index + 1];
          if (question?.role === 'user' && answer?.role === 'assistant') {
            this.conversation.push({ question: question.content, answer: answer.content });
          }
        }
        this.scrollToBottom(true);
      },
      error: () => {
        // History load failure is non-critical, start fresh
        this.conversation = [];
      }
    });
  }

  get isDisabled(): boolean {
    return this.isLoading || !this.question.trim();
  }

  get isThinking(): boolean {
    // A streaming message shows its own caret
    return this.isLoading && !this.liveMessage;
  }

  onSubmit(): void {
    const q = this.question.trim();
    if (!q || this.isLoading) return;

    this.isLoading = true;
    this.errorMessage = '';
    this.question = '';

    const message: Message = { question: q, answer: '', segments: [{ text: '' }], streaming: true };
    this.conversation.push(message);
    this.liveMessage = message;
    if (this.inputEl) this.inputEl.nativeElement.style.height = 'auto';
    this.scrollToBottom(true);
    this.runSegment(message, '');
  }

  /** Dial released. While an answer streams, cut it at the last whole word and continue under the new steering. */
  onSteer(values: SteeringValues): void {
    const message = this.liveMessage;
    const previous = this.runSteering;
    this.steering = { ...values };
    if (!message || !previous) return;

    const label = STEER_AXES
      .filter((a) => Math.abs((values[a.key] ?? 50) - (previous[a.key] ?? 50)) >= 3)
      .map((a) => describeAxis(a, values[a.key]))
      .join(' · ');
    if (!label) return;

    const match = message.answer.match(/^[\s\S]*\s/);
    const partial = match ? match[0].trimEnd() : '';
    this.trimSegmentsTo(message, partial.length);

    const segments = message.segments!;
    const last = segments[segments.length - 1];
    if (!partial) {
      // Nothing written yet: just start over with the new settings
      message.segments = [{ text: '' }];
    } else if (!last.text && last.label) {
      last.label = label; // moved again before any new text arrived
    } else {
      segments.push({ text: '', label });
    }
    this.runSegment(message, partial);
  }

  stopStreaming(): void {
    if (!this.liveMessage) return;
    this.runId++;
    this.abortController?.abort();
    this.liveMessage.notSaved = true;
    this.finish(this.liveMessage);
  }

  private async runSegment(message: Message, partial: string): Promise<void> {
    const id = ++this.runId;
    this.abortController?.abort();
    const controller = new AbortController();
    this.abortController = controller;
    this.runSteering = { ...this.steering };

    try {
      const handle = await this.chatService.streamAnswer(
        {
          documentId: this.documentId || null,
          sessionId: this.sessionId,
          question: message.question,
          steering: this.runSteering,
          partialAnswer: partial,
        },
        controller.signal,
      );
      if (id !== this.runId) return;
      message.sources = handle.sources;

      let joining = !!partial;
      for await (let text of handle.chunks) {
        if (id !== this.runId) return;
        if (joining) {
          text = text.replace(/^\s+/, '');
          if (!text) continue;
          // partial ends on a whole word; add a space unless the continuation starts with punctuation
          if (/^[\p{L}\p{N}"'(“‘]/u.test(text)) text = ' ' + text;
          joining = false;
        }
        const segments = message.segments!;
        segments[segments.length - 1].text += text;
        message.answer += text;
        this.scrollToBottom();
      }
      if (id === this.runId) this.finish(message);
    } catch (err: any) {
      if (id !== this.runId || err?.name === 'AbortError') return;
      this.errorMessage = err?.message || 'Failed to get an answer. Please try again.';
      if (!message.answer) {
        this.conversation = this.conversation.filter((m) => m !== message);
        this.question = message.question;
      } else {
        message.notSaved = true;
      }
      this.finish(message);
    }
  }

  private finish(message: Message): void {
    message.streaming = false;
    if (this.liveMessage === message) {
      this.liveMessage = null;
      this.runSteering = null;
      this.abortController = null;
      this.isLoading = false;
    }
  }

  /** Drop text past `length` characters, removing segments emptied by the cut. */
  private trimSegmentsTo(message: Message, length: number): void {
    message.answer = message.answer.slice(0, length);
    let remaining = length;
    const kept: AnswerSegment[] = [];
    for (const seg of message.segments!) {
      if (remaining <= 0 && kept.length) break;
      kept.push({ ...seg, text: seg.text.slice(0, Math.max(0, remaining)) });
      remaining -= seg.text.length;
    }
    message.segments = kept;
  }

  onNewDocument(): void {
    this.newDocument.emit();
  }

  selectTab(tab: ChatTab): void {
    this.activeTab = tab;
  }
}
