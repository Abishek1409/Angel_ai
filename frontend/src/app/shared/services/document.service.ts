import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface UploadResponse {
  document_id: string;
  filename: string;
  status: string;
}

export interface StatusResponse {
  status: string;
  error_message?: string;
}

@Injectable({ providedIn: 'root' })
export class DocumentService {
  private apiUrl = `${environment.apiUrl}/api/documents`;

  constructor(private http: HttpClient) {}

  uploadFile(file: File, sessionId: string): Observable<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('session_id', sessionId);
    return this.http.post<UploadResponse>(`${this.apiUrl}/upload/`, formData);
  }

  getStatus(documentId: string): Observable<StatusResponse> {
    return this.http.get<StatusResponse>(`${this.apiUrl}/${documentId}/status/`);
  }
}
