import { Component, Input, Output, EventEmitter, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DocumentService, Document } from '../shared/services/document.service';

@Component({
  selector: 'app-document-list',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './document-list.component.html',
  styleUrl: './document-list.component.scss'
})
export class DocumentListComponent implements OnInit {
  @Input() sessionId: string = '';
  @Output() documentSelected = new EventEmitter<string | null>();
  @Output() uploadNew = new EventEmitter<void>();

  documents: Document[] = [];
  selectedDocId: string | null = null;
  isLoading: boolean = true;
  errorMessage: string = '';

  constructor(private documentService: DocumentService) {}

  ngOnInit(): void {
    this.loadDocuments();
  }

  loadDocuments(): void {
    this.isLoading = true;
    this.documentService.listDocuments(this.sessionId).subscribe({
      next: (res) => {
        this.documents = res.documents;
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
      case 'error': return 'status-error';
      default: return '';
    }
  }
}
