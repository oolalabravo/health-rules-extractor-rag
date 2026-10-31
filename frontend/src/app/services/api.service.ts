import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface UserProfile {
  id: number;
  google_id: string;
  email: string;
  name: string;
  avatar_url: string;
  role: 'user' | 'admin';
  created_at: string;
}

export interface UserBaseline {
  is_ready: boolean;
  days_collected: number;
  days_required: number;
  days_remaining: number;
  avg_steps: number;
  avg_sleep_hours: number;
  avg_resting_hr: number;
  hr_variance: number;
  updated_at?: string;
}

export interface HealthMetric {
  date: string;
  step_count: number;
  sleep_minutes: number;
  sleep_hours: number;
  deep_sleep_minutes: number;
  rem_sleep_minutes: number;
  resting_heart_rate: number;
  avg_heart_rate: number;
}

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private readonly baseUrl = 'http://127.0.0.1:8001';
  private readonly tokenKey = 'health_jwt_token';

  constructor(private http: HttpClient) {}

  getToken(): string | null {
    if (typeof window !== 'undefined' && window.localStorage) {
      return localStorage.getItem(this.tokenKey);
    }
    return null;
  }

  setToken(token: string): void {
    if (typeof window !== 'undefined' && window.localStorage) {
      localStorage.setItem(this.tokenKey, token);
    }
  }

  logout(): void {
    if (typeof window !== 'undefined' && window.localStorage) {
      localStorage.removeItem(this.tokenKey);
    }
  }

  isLoggedIn(): boolean {
    return !!this.getToken();
  }

  private getHeaders(): HttpHeaders {
    const token = this.getToken();
    let headers = new HttpHeaders({ 'Content-Type': 'application/json' });
    if (token) {
      headers = headers.set('Authorization', `Bearer ${token}`);
    }
    return headers;
  }

  // --- Auth Endpoints ---

  getGoogleAuthUrl(): Observable<{ status: string; auth_url: string }> {
    return this.http.get<{ status: string; auth_url: string }>(`${this.baseUrl}/api/auth/google/url`);
  }

  exchangeGoogleToken(code: string, redirectUri?: string): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}/api/auth/google/token`, {
      code,
      redirect_uri: redirectUri
    });
  }

  demoLogin(role: 'admin' | 'user' = 'admin', daysData: number = 18): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}/api/auth/demo-login`, {
      role,
      days_data: daysData
    });
  }

  getMe(): Observable<{ status: string; user: UserProfile; baseline: UserBaseline }> {
    return this.http.get<{ status: string; user: UserProfile; baseline: UserBaseline }>(
      `${this.baseUrl}/api/auth/me`,
      { headers: this.getHeaders() }
    );
  }

  // --- Health & Baselining Endpoints ---

  getHealthSummary(): Observable<{ status: string; baseline: UserBaseline; total_days_recorded: number; timeline: HealthMetric[] }> {
    return this.http.get<any>(`${this.baseUrl}/api/health/summary`, { headers: this.getHeaders() });
  }

  syncHealth(days: number = 180): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}/api/health/sync?days=${days}`, {}, { headers: this.getHeaders() });
  }

  predictPersonalized(params: {
    query_description?: string;
    override_sleep_hours?: number;
    override_resting_hr?: number;
    override_step_count?: number;
  }): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}/api/predict-personalized`, params, { headers: this.getHeaders() });
  }

  // --- Admin Endpoints ---

  getAdminOverview(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/api/admin/overview`, { headers: this.getHeaders() });
  }

  searchCandidatePapers(query: string, maxResults: number = 5): Observable<any> {
    const encoded = encodeURIComponent(query);
    return this.http.get<any>(`${this.baseUrl}/api/admin/papers/search?query=${encoded}&max_results=${maxResults}`, {
      headers: this.getHeaders()
    });
  }

  extractPaper(paper: any): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}/api/admin/papers/extract`, { paper }, {
      headers: this.getHeaders()
    });
  }

  getPaperLedger(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/api/admin/papers/ledger`, { headers: this.getHeaders() });
  }
}
