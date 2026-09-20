import { Component, OnInit, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { UploadComponent } from './upload/upload.component';
import { ChatComponent } from './chat/chat.component';
import { DocumentListComponent } from './documents/document-list.component';
import { AuthComponent } from './auth/auth.component';
import { AuthService } from './auth/auth.service';
import { SessionHistoryComponent } from './sessions/session-history.component';
import { ChatSession } from './shared/services/chat.service';

const SESSION_KEY = 'angelai_session';
const DOCUMENT_KEY = 'angelai_document';

type AppView = 'upload' | 'chat' | 'documents';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, UploadComponent, ChatComponent, DocumentListComponent, AuthComponent, SessionHistoryComponent],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App implements OnInit {
  sessionId: string = '';
  documentId: string | null = null;
  currentView: AppView = 'upload';
  showDocumentList: boolean = false;
  documentListRefresh: number = 0;
  sessionHistoryRefresh = 0;
  isReady = false;

  constructor(public auth: AuthService) {}

  ngOnInit(): void {
    this.auth.refresh().subscribe({
      next: () => this.initializeWorkspace(),
      error: () => {
        this.auth.clearSession();
        this.isReady = true;
      }
    });
  }

  logout(): void {
    this.auth.logout().subscribe({ error: () => this.auth.clearSession() });
  }

  private initializeWorkspace(): void {
    // Restore session from localStorage so refresh keeps state
    this.sessionId = localStorage.getItem(SESSION_KEY) || crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, this.sessionId);

    this.documentId = localStorage.getItem(DOCUMENT_KEY) || null;
    
    // Check if sidebar should be shown (stored in localStorage)
    const shouldShowSidebar = localStorage.getItem('angelai_show_sidebar');
    if (shouldShowSidebar === 'true') {
      this.showDocumentList = true;
    }
    
    // If we have a document, show chat view and sidebar
    if (this.documentId) {
      this.currentView = 'chat';
      this.showDocumentList = true;
      localStorage.setItem('angelai_show_sidebar', 'true');
    }
    this.isReady = true;
  }

  onDocumentReady(documentId: string): void {
    this.documentId = documentId;
    this.documentListRefresh += 1;
    localStorage.setItem(DOCUMENT_KEY, documentId);
    this.currentView = 'chat';
    this.showDocumentList = true;
    this.sessionHistoryRefresh += 1;
    localStorage.setItem('angelai_show_sidebar', 'true');
  }

  onSessionSelected(session: ChatSession): void {
    this.sessionId = session.id;
    this.documentId = session.document_id ?? null;
    localStorage.setItem(SESSION_KEY, session.id);
    if (this.documentId) {
      localStorage.setItem(DOCUMENT_KEY, this.documentId);
    } else {
      localStorage.removeItem(DOCUMENT_KEY);
    }
    this.currentView = 'chat';
    this.showDocumentList = true;
  }

  onSessionDeleted(): void {
    this.sessionId = crypto.randomUUID();
    this.documentId = null;
    localStorage.setItem(SESSION_KEY, this.sessionId);
    localStorage.removeItem(DOCUMENT_KEY);
    this.currentView = 'upload';
    this.showDocumentList = false;
    this.sessionHistoryRefresh += 1;
    this.documentListRefresh += 1;
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
    // Keep sidebar visible if we already have documents
  }

  onUploadNew(): void {
    this.currentView = 'upload';
    // Sidebar stays visible (showDocumentList remains true)
  }
}
