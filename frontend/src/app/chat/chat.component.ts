import { Component, Input, Output, EventEmitter, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ChatService } from '../shared/services/chat.service';
import { MessageComponent } from './message/message.component';

export interface Message {
  question: string;
  answer: string;
}

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule, MessageComponent],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.scss'
})
export class ChatComponent implements OnInit {
  @Input() documentId: string = '';
  @Input() sessionId: string = '';
  @Output() newDocument = new EventEmitter<void>();

  question: string = '';
  conversation: Message[] = [];
  isLoading: boolean = false;
  errorMessage: string = '';

  constructor(private chatService: ChatService) {}

  ngOnInit(): void {
    // Load history from server
    this.chatService.getHistory(this.documentId, this.sessionId).subscribe({
      next: (res) => {
        this.conversation = res.messages.map(m => ({
          question: m.question,
          answer: m.answer,
        }));
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

    this.chatService.sendQuestion(this.documentId, this.sessionId, q).subscribe({
      next: (res) => {
        this.conversation.push({ question: q, answer: res.answer });
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
