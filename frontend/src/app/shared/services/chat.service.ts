import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface QueryResponse {
  answer: string;
  sources: string[];
}

export interface HistoryMessage {
  id: string;
  question: string;
  answer: string;
  created_at: string;
}

@Injectable({ providedIn: 'root' })
export class ChatService {
  private apiUrl = 'https://angelai-production.up.railway.app/api/chat';

  constructor(private http: HttpClient) {}

  sendQuestion(documentId: string, sessionId: string, question: string): Observable<QueryResponse> {
    return this.http.post<QueryResponse>(`${this.apiUrl}/query/`, {
      document_id: documentId,
      session_id: sessionId,
      question
    });
  }

  getHistory(documentId: string, sessionId: string): Observable<{ messages: HistoryMessage[] }> {
    return this.http.get<{ messages: HistoryMessage[] }>(
      `${this.apiUrl}/history/${documentId}/?session_id=${sessionId}`
    );
  }
}
