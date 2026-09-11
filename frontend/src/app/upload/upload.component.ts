import { Component, Input, Output, EventEmitter, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DocumentService, UploadResponse } from '../shared/services/document.service';
import { Subscription, interval } from 'rxjs';
import { switchMap, takeWhile } from 'rxjs/operators';

const MAX_FILE_SIZE_MB = 20;
const ACCEPTED_TYPES = ['application/pdf', 'text/plain'];
const ACCEPTED_EXTENSIONS = ['.pdf', '.txt'];
const POLL_INTERVAL_MS = 2000;

interface QueuedUpload {
  file: File;
  documentId: string;
  status: 'uploading' | 'processing' | 'ready' | 'error';
  errorMessage: string;
  pollSub: Subscription | null;
}

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

  selectedFiles: File[] = [];
  status: 'idle' | 'uploading' | 'processing' | 'ready' | 'error' = 'idle';
  errorMessage: string = '';
  queue: QueuedUpload[] = [];

  constructor(private documentService: DocumentService) {}

  get isBusy(): boolean {
    return this.status === 'uploading' || this.status === 'processing';
  }

  get readyCount(): number {
    return this.queue.filter((item) => item.status === 'ready').length;
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      const files = Array.from(input.files);
      const validFiles: File[] = [];

      for (const file of files) {
        const ext = '.' + file.name.split('.').pop()?.toLowerCase();
        const isValidType = ACCEPTED_TYPES.includes(file.type) || ACCEPTED_EXTENSIONS.includes(ext);
        if (!isValidType) {
          this.errorMessage = `Unsupported file type: ${file.name}. Accepted formats: PDF, TXT.`;
          continue;
        }
        const sizeMB = file.size / (1024 * 1024);
        if (sizeMB > MAX_FILE_SIZE_MB) {
          this.errorMessage = `${file.name} exceeds the 20 MB size limit (${sizeMB.toFixed(1)} MB).`;
          continue;
        }
        validFiles.push(file);
      }

      if (validFiles.length > 0) {
        this.selectedFiles = [...this.selectedFiles, ...validFiles];
        this.errorMessage = '';
      }
    }
  }

  removeFile(index: number): void {
    this.selectedFiles.splice(index, 1);
  }

  onSubmit(): void {
    if (this.selectedFiles.length === 0 || this.isBusy) return;

    this.status = 'uploading';
    this.errorMessage = '';
    this.queue = [];

    const filesToUpload = [...this.selectedFiles];
    this.selectedFiles = [];

    for (const file of filesToUpload) {
      const queued: QueuedUpload = {
        file,
        documentId: '',
        status: 'uploading',
        errorMessage: '',
        pollSub: null,
      };
      this.queue.push(queued);
      this.uploadNext(queued);
    }
  }

  private uploadNext(queued: QueuedUpload): void {
    queued.status = 'uploading';
    this.documentService.uploadFile(queued.file, this.sessionId).subscribe({
      next: (res: UploadResponse) => {
        queued.documentId = res.document_id;
        queued.status = 'processing';
        this.status = 'processing';
        this.startPolling(queued);
      },
      error: () => {
        queued.status = 'error';
        queued.errorMessage = `Upload failed: ${queued.file.name}`;
        this.checkQueueComplete();
      }
    });
  }

  private startPolling(queued: QueuedUpload): void {
    queued.pollSub = interval(POLL_INTERVAL_MS).pipe(
      switchMap(() => this.documentService.getStatus(queued.documentId)),
      takeWhile((res) => res.status === 'pending' || res.status === 'processing', true)
    ).subscribe({
      next: (res) => {
        if (res.status === 'ready') {
          queued.status = 'ready';
          this.documentReady.emit(queued.documentId);
          this.checkQueueComplete();
        } else if (res.status === 'error') {
          queued.status = 'error';
          queued.errorMessage = res.error_message || `Processing failed: ${queued.file.name}`;
          this.checkQueueComplete();
        }
      },
      error: () => {
        queued.status = 'error';
        queued.errorMessage = `Failed to check status: ${queued.file.name}`;
        this.checkQueueComplete();
      }
    });
  }

  private checkQueueComplete(): void {
    const allDone = this.queue.every(
      (q) => q.status === 'ready' || q.status === 'error'
    );
    if (allDone) {
      const hasReady = this.queue.some((q) => q.status === 'ready');
      const hasError = this.queue.some((q) => q.status === 'error');
      if (hasReady) {
        this.status = 'ready';
      } else if (hasError) {
        this.status = 'error';
        this.errorMessage = 'All uploads failed. Please try again.';
      } else {
        this.status = 'idle';
      }
    }
  }

  ngOnDestroy(): void {
    this.queue.forEach((q) => q.pollSub?.unsubscribe());
  }
}
