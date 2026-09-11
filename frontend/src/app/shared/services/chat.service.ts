import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface QueryResponse {
  answer: string;
  sources: string[];
  citations?: Array<{
    source: string;
    doc_id?: string;
    chunk_id?: string;
    chunk_index?: number;
  }>;
  cached?: boolean;
  cache_details?: {
    embedding_cached: boolean;
    response_cached: boolean;
  };
}

export interface HistoryMessage {
  id: string;
  question: string;
  answer: string;
  created_at: string;
}

@Injectable({ providedIn: 'root' })
export class ChatService {
  private apiUrl = `${environment.apiUrl}/api/chat`;

  constructor(private http: HttpClient) {}

  sendQuestion(documentId: string | null, sessionId: string, question: string): Observable<QueryResponse> {
    const body: any = {
      session_id: sessionId,
      question
    };
    if (documentId) {
      body.document_id = documentId;
    }
    return this.http.post<QueryResponse>(`${this.apiUrl}/query/`, body);
  }

  getHistory(documentId: string, sessionId: string): Observable<{ messages: HistoryMessage[] }> {
    return this.http.get<{ messages: HistoryMessage[] }>(
      `${this.apiUrl}/history/${documentId}/?session_id=${sessionId}`
    );
  }
}
