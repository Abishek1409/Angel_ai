import { Injectable } from '@angular/core';
import { HttpClient, HttpEvent } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface UploadResponse {
  document_id: string;
  filename: string;
  status: string;
}

export interface StatusResponse {
  status: string;
  error_message?: string;
}

export interface Document {
  id: string;
  filename: string;
  status: string;
  created_at: string;
  error_message?: string;
}

export interface ListResponse {
  documents: Document[];
}

@Injectable({ providedIn: 'root' })
export class DocumentService {
  private apiUrl = `${environment.apiUrl}/api/documents`;

  constructor(private http: HttpClient) {}

  uploadFile(file: File, sessionId: string): Observable<HttpEvent<UploadResponse>> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('session_id', sessionId);
    return this.http.post<UploadResponse>(`${this.apiUrl}/upload/`, formData, {
      observe: 'events',
      reportProgress: true,
    });
  }

  getStatus(documentId: string): Observable<StatusResponse> {
    return this.http.get<StatusResponse>(`${this.apiUrl}/${documentId}/status/`);
  }

  listDocuments(): Observable<ListResponse> {
    return this.http.get<ListResponse>(`${this.apiUrl}/list/`);
  }

  deleteDocument(documentId: string): Observable<{message: string}> {
    return this.http.delete<{message: string}>(`${this.apiUrl}/${documentId}/delete/`);
  }
}
