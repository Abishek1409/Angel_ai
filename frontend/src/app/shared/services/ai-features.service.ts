import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface Flashcard {
  id: string;
  question: string;
  answer: string;
  created_at: string;
}

export interface FlashcardsResponse {
  count: number;
  flashcards: Flashcard[];
  message?: string;
}

export interface Roadmap {
  id: string;
  mermaid_definition: string;
  created_at: string;
  updated_at: string;
}

export interface RoadmapResponse {
  roadmap: Roadmap | null;
  message?: string;
}

@Injectable({
  providedIn: 'root'
})
export class AiFeaturesService {
  private baseUrl = `${environment.apiUrl}/api/documents`;

  constructor(private http: HttpClient) {}

  private getHeaders(): HttpHeaders {
    const token = localStorage.getItem('access_token');
    return new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });
  }

  // Flashcard endpoints
  getFlashcards(documentId: string): Observable<FlashcardsResponse> {
    return this.http.get<FlashcardsResponse>(
      `${this.baseUrl}/${documentId}/flashcards/`,
      { headers: this.getHeaders() }
    );
  }

  generateFlashcards(documentId: string): Observable<FlashcardsResponse> {
    return this.http.post<FlashcardsResponse>(
      `${this.baseUrl}/${documentId}/flashcards/generate/`,
      {},
      { headers: this.getHeaders() }
    );
  }

  deleteFlashcards(documentId: string): Observable<{message: string}> {
    return this.http.delete<{message: string}>(
      `${this.baseUrl}/${documentId}/flashcards/delete/`,
      { headers: this.getHeaders() }
    );
  }

  // Roadmap endpoints
  getRoadmap(documentId: string): Observable<RoadmapResponse> {
    return this.http.get<RoadmapResponse>(
      `${this.baseUrl}/${documentId}/roadmap/`,
      { headers: this.getHeaders() }
    );
  }

  generateRoadmap(documentId: string): Observable<RoadmapResponse> {
    return this.http.post<RoadmapResponse>(
      `${this.baseUrl}/${documentId}/roadmap/generate/`,
      {},
      { headers: this.getHeaders() }
    );
  }

  deleteRoadmap(documentId: string): Observable<{message: string}> {
    return this.http.delete<{message: string}>(
      `${this.baseUrl}/${documentId}/roadmap/delete/`,
      { headers: this.getHeaders() }
    );
  }
}
