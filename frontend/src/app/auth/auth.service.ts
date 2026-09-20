import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { environment } from '../../environments/environment';

interface AuthResponse {
  access: string;
  username?: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly apiUrl = `${environment.apiUrl}/api/auth`;
  private accessToken: string | null = null;
  readonly username = signal<string | null>(null);

  constructor(private http: HttpClient) {}

  get token(): string | null {
    return this.accessToken;
  }

  register(username: string, password: string): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.apiUrl}/register/`, { username, password }).pipe(
      tap((response) => this.setSession(response))
    );
  }

  login(username: string, password: string): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.apiUrl}/login/`, { username, password }).pipe(
      tap((response) => this.setSession(response))
    );
  }

  refresh(): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.apiUrl}/refresh/`, {}).pipe(
      tap((response) => this.setSession(response))
    );
  }

  logout(): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(`${this.apiUrl}/logout/`, {}).pipe(
      tap(() => this.clearSession())
    );
  }

  clearSession(): void {
    this.accessToken = null;
    this.username.set(null);
  }

  private setSession(response: AuthResponse): void {
    this.accessToken = response.access;
    if (response.username) {
      this.username.set(response.username);
    }
  }
}