import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuthService } from '../../auth/auth.service';

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
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

export interface ChatSession {
  id: string;
  title: string;
  document_id: string | null;
  created_at: string;
}

export type SteeringValues = Record<string, number>;

export interface StreamRequest {
  documentId: string | null;
  sessionId: string;
  question: string;
  steering: SteeringValues;
  partialAnswer?: string;
}

export interface StreamHandle {
  sources: string[];
  chunks: AsyncGenerator<string>;
}

@Injectable({ providedIn: 'root' })
export class ChatService {
  private apiUrl = `${environment.apiUrl}/api/chat`;

  constructor(private http: HttpClient, private auth: AuthService) {}

  /**
   * Open a streamed, steerable answer. Uses fetch (not HttpClient) so text can be
   * read as it arrives and the request can be aborted when a dial moves.
   */
  async streamAnswer(req: StreamRequest, signal: AbortSignal): Promise<StreamHandle> {
    const body: any = {
      session_id: req.sessionId,
      question: req.question,
      steering: req.steering,
      partial_answer: req.partialAnswer || '',
    };
    if (req.documentId) {
      body.document_id = req.documentId;
    }

    const send = () => fetch(`${this.apiUrl}/stream/`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...(this.auth.token ? { Authorization: `Bearer ${this.auth.token}` } : {}),
      },
      body: JSON.stringify(body),
      signal,
    });

    let response = await send();
    if (response.status === 401) {
      await firstValueFrom(this.auth.refresh());
      response = await send();
    }
    if (!response.ok || !response.body) {
      let message = 'Failed to get an answer. Please try again.';
      try {
        message = (await response.json()).error || message;
      } catch { /* non-JSON error body */ }
      throw new Error(message);
    }

    let sources: string[] = [];
    try {
      sources = JSON.parse(response.headers.get('X-Sources') || '[]');
    } catch { /* missing header */ }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    async function* chunks(): AsyncGenerator<string> {
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const text = decoder.decode(value, { stream: true });
          if (text) yield text;
        }
      } finally {
        reader.releaseLock();
      }
    }
    return { sources, chunks: chunks() };
  }

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

  getHistory(documentId: string | null, sessionId: string): Observable<{ messages: HistoryMessage[] }> {
    const historyDocumentId = documentId || 'multi';
    return this.http.get<{ messages: HistoryMessage[] }>(
      `${this.apiUrl}/history/${historyDocumentId}/?session_id=${sessionId}`
    );
  }

  getSessions(): Observable<{ sessions: ChatSession[] }> {
    return this.http.get<{ sessions: ChatSession[] }>(`${environment.apiUrl}/api/sessions/`);
  }

  getOrCreateDocumentSession(documentId: string): Observable<ChatSession> {
    return this.http.post<ChatSession>(
      `${environment.apiUrl}/api/sessions/document/${documentId}/`,
      {}
    );
  }

  getSessionMessages(sessionId: string): Observable<{ messages: HistoryMessage[] }> {
    return this.http.get<{ messages: HistoryMessage[] }>(`${environment.apiUrl}/api/sessions/${sessionId}/messages/`);
  }

  deleteSession(sessionId: string): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${environment.apiUrl}/api/sessions/${sessionId}/`);
  }
}
