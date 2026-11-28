import { Component, Input, Output, EventEmitter, OnInit, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DocumentService, Document } from '../shared/services/document.service';

@Component({
  selector: 'app-document-list',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './document-list.component.html',
  styleUrl: './document-list.component.scss'
})
export class DocumentListComponent implements OnInit, OnChanges {
  @Input() sessionId: string = '';
  @Input() refreshToken: number = 0;
  /** Highlighted document, owned by the app shell; undefined falls back to the last click. */
  @Input() activeDocumentId: string | null | undefined = undefined;
  @Output() documentSelected = new EventEmitter<string | null>();
  @Output() uploadNew = new EventEmitter<void>();

  documents: Document[] = [];
  retentionHours = 48;
  selectedDocId: string | null = null;
  isLoading: boolean = true;
  errorMessage: string = '';

  constructor(private documentService: DocumentService) {}

  ngOnInit(): void {
    this.loadDocuments();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['refreshToken'] && !changes['refreshToken'].firstChange) {
      this.loadDocuments();
    }
  }

  loadDocuments(): void {
    this.isLoading = true;
    this.documentService.listDocuments().subscribe({
      next: (res) => {
        this.documents = res.documents;
        this.retentionHours = res.retention_hours ?? this.retentionHours;
        this.isLoading = false;
      },
      error: () => {
        this.errorMessage = 'Failed to load documents';
        this.isLoading = false;
      }
    });
  }

  selectDocument(docId: string | null): void {
    this.selectedDocId = docId;
    this.documentSelected.emit(docId);
  }

  deleteDocument(docId: string, event: Event): void {
    event.stopPropagation();
    
    if (!confirm('Delete this document? This cannot be undone.')) {
      return;
    }

    this.documentService.deleteDocument(docId).subscribe({
      next: () => {
        this.documents = this.documents.filter(d => d.id !== docId);
        if (this.selectedDocId === docId) {
          this.selectDocument(null);
        }
      },
      error: () => {
        this.errorMessage = 'Failed to delete document';
      }
    });
  }

  onUploadNew(): void {
    this.uploadNew.emit();
  }

  getStatusClass(status: string): string {
    switch (status) {
      case 'ready': return 'status-ready';
      case 'pending': return 'status-pending';
      case 'processing': return 'status-processing';
      case 'processing_ocr': return 'status-processing';
      case 'error': return 'status-error';
      default: return '';
    }
  }

  /** Short "1d 5h left" label for when the server deletes the document. */
  timeLeft(doc: Document): string {
    if (!doc.expires_at) return '';
    const ms = new Date(doc.expires_at).getTime() - Date.now();
    if (ms <= 0) return 'expiring';
    const hours = Math.floor(ms / 3_600_000);
    if (hours >= 24) return `${Math.floor(hours / 24)}d ${hours % 24}h left`;
    if (hours >= 1) return `${hours}h left`;
    return `${Math.max(1, Math.floor(ms / 60_000))}m left`;
  }

  expiryTitle(doc: Document): string {
    return doc.expires_at
      ? `${doc.filename} — kept until ${new Date(doc.expires_at).toLocaleString()}`
      : doc.filename;
  }

  getStatusLabel(status: string): string {
    return status === 'processing_ocr' ? 'Processing (OCR)…' : status;
  }
}
