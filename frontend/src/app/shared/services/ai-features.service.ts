import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
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

  // Flashcard endpoints
  getFlashcards(documentId: string): Observable<FlashcardsResponse> {
    return this.http.get<FlashcardsResponse>(
      `${this.baseUrl}/${documentId}/flashcards/`
    );
  }

  generateFlashcards(documentId: string): Observable<FlashcardsResponse> {
    return this.http.post<FlashcardsResponse>(
      `${this.baseUrl}/${documentId}/flashcards/generate/`,
      {}
    );
  }

  deleteFlashcards(documentId: string): Observable<{message: string}> {
    return this.http.delete<{message: string}>(
      `${this.baseUrl}/${documentId}/flashcards/delete/`
    );
  }

  // Roadmap endpoints
  getRoadmap(documentId: string): Observable<RoadmapResponse> {
    return this.http.get<RoadmapResponse>(
      `${this.baseUrl}/${documentId}/roadmap/`
    );
  }

  generateRoadmap(documentId: string): Observable<RoadmapResponse> {
    return this.http.post<RoadmapResponse>(
      `${this.baseUrl}/${documentId}/roadmap/generate/`,
      {}
    );
  }

  deleteRoadmap(documentId: string): Observable<{message: string}> {
    return this.http.delete<{message: string}>(
      `${this.baseUrl}/${documentId}/roadmap/delete/`
    );
  }
}
