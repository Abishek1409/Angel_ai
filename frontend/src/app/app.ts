import { Component, OnInit, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { UploadComponent } from './upload/upload.component';
import { ChatComponent } from './chat/chat.component';

const SESSION_KEY = 'angelai_session';
const DOCUMENT_KEY = 'angelai_document';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, UploadComponent, ChatComponent],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App implements OnInit {
  sessionId: string = '';
  documentId: string | null = null;

  ngOnInit(): void {
    // Restore session from localStorage so refresh keeps state
    this.sessionId = localStorage.getItem(SESSION_KEY) || crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, this.sessionId);

    this.documentId = localStorage.getItem(DOCUMENT_KEY) || null;
  }

  onDocumentReady(documentId: string): void {
    this.documentId = documentId;
    localStorage.setItem(DOCUMENT_KEY, documentId);
  }

  onNewDocument(): void {
    this.documentId = null;
    localStorage.removeItem(DOCUMENT_KEY);
    // Keep same sessionId so history context is preserved
  }
}
