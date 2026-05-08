import { Component, Input, Output, EventEmitter, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DocumentService } from '../shared/services/document.service';
import { Subscription, interval } from 'rxjs';
import { switchMap, takeWhile } from 'rxjs/operators';

const MAX_FILE_SIZE_MB = 20;
const ACCEPTED_TYPES = ['application/pdf', 'text/plain'];
const ACCEPTED_EXTENSIONS = ['.pdf', '.txt'];
const POLL_INTERVAL_MS = 2000;

@Component({
  selector: 'app-upload',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './upload.component.html',
  styleUrl: './upload.component.scss'
})
export class UploadComponent implements OnDestroy {
  @Input() sessionId: string = '';
  @Output() documentReady = new EventEmitter<string>();

  selectedFile: File | null = null;
  status: 'idle' | 'uploading' | 'processing' | 'ready' | 'error' = 'idle';
  errorMessage: string = '';
  uploadedFilename: string = '';

  private pollSub: Subscription | null = null;

  constructor(private documentService: DocumentService) {}

  get isBusy(): boolean {
    return this.status === 'uploading' || this.status === 'processing';
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.validateAndSetFile(input.files[0]);
    }
  }

  validateAndSetFile(file: File): void {
    this.errorMessage = '';
    this.selectedFile = null;

    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    const isValidType = ACCEPTED_TYPES.includes(file.type) || ACCEPTED_EXTENSIONS.includes(ext);
    if (!isValidType) {
      this.errorMessage = 'Unsupported file type. Accepted formats: PDF, TXT.';
      return;
    }

    const sizeMB = file.size / (1024 * 1024);
    if (sizeMB > MAX_FILE_SIZE_MB) {
      this.errorMessage = `File exceeds the 20 MB size limit (${sizeMB.toFixed(1)} MB).`;
      return;
    }

    this.selectedFile = file;
  }

  onSubmit(): void {
    if (!this.selectedFile || this.isBusy) return;

    this.status = 'uploading';
    this.errorMessage = '';

    this.documentService.uploadFile(this.selectedFile, this.sessionId).subscribe({
      next: (res) => {
        this.uploadedFilename = res.filename;
        this.status = 'processing';
        this.startPolling(res.document_id);
      },
      error: (err) => {
        this.status = 'error';
        this.errorMessage = err?.error?.error || 'Upload failed. Please try again.';
      }
    });
  }

  private startPolling(documentId: string): void {
    this.pollSub = interval(POLL_INTERVAL_MS).pipe(
      switchMap(() => this.documentService.getStatus(documentId)),
      takeWhile((res) => res.status === 'pending', true)
    ).subscribe({
      next: (res) => {
        if (res.status === 'ready') {
          this.status = 'ready';
          this.documentReady.emit(documentId);
        } else if (res.status === 'error') {
          this.status = 'error';
          this.errorMessage = res.error_message || 'Document processing failed.';
        }
      },
      error: () => {
        this.status = 'error';
        this.errorMessage = 'Failed to retrieve document status.';
      }
    });
  }

  ngOnDestroy(): void {
    this.pollSub?.unsubscribe();
  }
}
