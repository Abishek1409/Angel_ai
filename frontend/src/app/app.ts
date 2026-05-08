import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { UploadComponent } from './upload/upload.component';
import { ChatComponent } from './chat/chat.component';

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
    this.sessionId = crypto.randomUUID();
  }

  onDocumentReady(documentId: string): void {
    this.documentId = documentId;
  }
}
