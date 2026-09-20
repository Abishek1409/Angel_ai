import { Component, EventEmitter, Input, OnChanges, Output, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ChatService, ChatSession } from '../shared/services/chat.service';

@Component({
  selector: 'app-session-history',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './session-history.component.html',
  styleUrl: './session-history.component.scss'
})
export class SessionHistoryComponent implements OnChanges {
  @Input() refreshToken = 0;
  @Output() sessionSelected = new EventEmitter<ChatSession>();
  @Output() sessionDeleted = new EventEmitter<void>();
  sessions: ChatSession[] = [];
  selectedId: string | null = null;

  constructor(private chatService: ChatService) {}

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['refreshToken']) this.loadSessions();
  }

  loadSessions(): void {
    this.chatService.getSessions().subscribe({ next: (response) => this.sessions = response.sessions });
  }

  select(session: ChatSession): void {
    this.selectedId = session.id;
    this.sessionSelected.emit(session);
  }

  delete(session: ChatSession, event: Event): void {
    event.stopPropagation();
    this.chatService.deleteSession(session.id).subscribe({
      next: () => {
        const wasSelected = this.selectedId === session.id;
        this.sessions = this.sessions.filter(item => item.id !== session.id);
        if (wasSelected) {
          this.selectedId = null;
        }
        this.sessionDeleted.emit();
      }
    });
  }
}