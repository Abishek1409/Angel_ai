import { Component, Input, Output, EventEmitter, OnInit, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ChatService } from '../shared/services/chat.service';
import { MessageComponent } from './message/message.component';

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
}

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule, MessageComponent],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.scss'
})
export class ChatComponent implements OnInit, OnChanges {
  @Input() documentId: string | null = null;
  @Input() sessionId: string = '';
  @Output() newDocument = new EventEmitter<void>();

  question: string = '';
  conversation: Message[] = [];
  isLoading: boolean = false;
  errorMessage: string = '';

  constructor(private chatService: ChatService) {}

  ngOnInit(): void {
    this.loadHistory();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['sessionId'] && changes['sessionId'].firstChange) {
      return;
    }

    if (changes['sessionId'] || changes['documentId']) {
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

  onSubmit(): void {
    const q = this.question.trim();
    if (!q || this.isLoading) return;

    this.isLoading = true;
    this.errorMessage = '';

    this.chatService.sendQuestion(this.documentId || null, this.sessionId, q).subscribe({
      next: (res) => {
        this.conversation.push({
          question: q,
          answer: res.answer,
          sources: res.sources,
          citations: res.citations,
          cached: res.cached,
        });
        this.question = '';
        this.isLoading = false;
      },
      error: (err) => {
        this.errorMessage = err?.error?.error || 'Failed to get an answer. Please try again.';
        this.isLoading = false;
      }
    });
  }

  onNewDocument(): void {
    this.newDocument.emit();
  }
}
