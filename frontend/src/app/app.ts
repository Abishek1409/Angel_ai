import { Component, OnInit, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { UploadComponent } from './upload/upload.component';
import { ChatComponent } from './chat/chat.component';
import { DocumentListComponent } from './documents/document-list.component';

const SESSION_KEY = 'angelai_session';
const DOCUMENT_KEY = 'angelai_document';

type AppView = 'upload' | 'chat' | 'documents';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, UploadComponent, ChatComponent, DocumentListComponent],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App implements OnInit {
  sessionId: string = '';
  documentId: string | null = null;
  currentView: AppView = 'upload';
  showDocumentList: boolean = false;

  ngOnInit(): void {
    // Restore session from localStorage so refresh keeps state
    this.sessionId = localStorage.getItem(SESSION_KEY) || crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, this.sessionId);

    this.documentId = localStorage.getItem(DOCUMENT_KEY) || null;
    
    // If we have a document, show chat view
    if (this.documentId) {
      this.currentView = 'chat';
      this.showDocumentList = true;
    }
  }

  onDocumentReady(documentId: string): void {
    this.documentId = documentId;
    localStorage.setItem(DOCUMENT_KEY, documentId);
    this.currentView = 'chat';
    this.showDocumentList = true;
  }

  onDocumentSelected(documentId: string | null): void {
    this.documentId = documentId;
    if (documentId) {
      localStorage.setItem(DOCUMENT_KEY, documentId);
    } else {
      localStorage.removeItem(DOCUMENT_KEY);
    }
    this.currentView = 'chat';
  }

  onNewDocument(): void {
    this.currentView = 'upload';
  }

  onUploadNew(): void {
    this.currentView = 'upload';
  }
}
