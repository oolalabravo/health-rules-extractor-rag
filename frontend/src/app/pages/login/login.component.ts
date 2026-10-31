import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="min-h-screen bg-slate-950 flex flex-col justify-center items-center px-4 py-12 relative overflow-hidden">
      <!-- Ambient Glow Effects -->
      <div class="absolute -top-40 -left-40 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none"></div>
      <div class="absolute -bottom-40 -right-40 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none"></div>

      <!-- Main Login Container -->
      <div class="w-full max-w-md bg-slate-900/90 border border-slate-800 rounded-2xl p-8 shadow-2xl backdrop-blur-xl relative z-10">
        <!-- Logo & Branding -->
        <div class="flex flex-col items-center text-center mb-8">
          <div class="w-16 h-16 bg-gradient-to-tr from-emerald-500 to-cyan-400 rounded-2xl flex items-center justify-center shadow-lg shadow-emerald-500/20 mb-4">
            <span class="text-3xl">🧬</span>
          </div>
          <h1 class="text-2xl font-bold tracking-tight text-white">Biomedical Health Intelligence</h1>
          <p class="text-sm text-slate-400 mt-1">Peer-Reviewed Wearable RAG & Baselining Engine</p>
        </div>

        <!-- Google Sign-In Action -->
        <div class="space-y-4">
          <button
            (click)="signInWithGoogle()"
            [disabled]="loading"
            class="w-full flex items-center justify-center gap-3 bg-white hover:bg-slate-100 text-slate-900 font-medium py-3.5 px-4 rounded-xl shadow-md transition-all duration-200 hover:shadow-lg disabled:opacity-60 cursor-pointer"
          >
            <!-- Google SVG Icon -->
            <svg class="w-5 h-5" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
            </svg>
            <span *ngIf="!loading">Sign in with Google Health</span>
            <span *ngIf="loading">Redirecting to Google...</span>
          </button>

          <p class="text-xs text-center text-slate-400 leading-relaxed px-2">
            Grants read-only access to last 6 months of Google Fitness metrics (sleep stages, resting heart rate, step count) for 15-day baseline tracking.
          </p>

          <!-- Divider -->
          <div class="relative my-6 flex items-center">
            <div class="flex-grow border-t border-slate-800"></div>
            <span class="flex-shrink mx-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Or Instant Demo Access</span>
            <div class="flex-grow border-t border-slate-800"></div>
          </div>

          <!-- Quick Test Demo Buttons -->
          <div class="grid grid-cols-2 gap-3">
            <button
              (click)="loginDemo('admin')"
              [disabled]="demoLoading"
              class="w-full bg-slate-800 hover:bg-slate-700 text-emerald-400 border border-emerald-500/30 font-medium py-2.5 px-3 rounded-xl text-xs transition duration-150 flex flex-col items-center justify-center gap-1 cursor-pointer"
            >
              <span class="font-semibold text-white">Demo Admin</span>
              <span class="text-[10px] text-slate-400">Paper Hunter & System GUI</span>
            </button>

            <button
              (click)="loginDemo('user')"
              [disabled]="demoLoading"
              class="w-full bg-slate-800 hover:bg-slate-700 text-cyan-400 border border-cyan-500/30 font-medium py-2.5 px-3 rounded-xl text-xs transition duration-150 flex flex-col items-center justify-center gap-1 cursor-pointer"
            >
              <span class="font-semibold text-white">Demo Patient</span>
              <span class="text-[10px] text-slate-400">Baseline & Wearable Trends</span>
            </button>
          </div>
        </div>

        <!-- Security & Architecture Footer -->
        <div class="mt-8 pt-6 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
          <span class="flex items-center gap-1.5">
            <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            1,378 FAISS Vectors
          </span>
          <span class="flex items-center gap-1">
            <span>🛡️</span> RBAC Protected
          </span>
          <span>⚡ Gemini 3.5 Flash-Lite</span>
        </div>
      </div>
    </div>
  `
})
export class LoginComponent implements OnInit {
  loading = false;
  demoLoading = false;

  constructor(private api: ApiService, private router: Router) {}

  ngOnInit(): void {
    if (this.api.isLoggedIn()) {
      this.api.getMe().subscribe({
        next: (res) => {
          if (res.user.role === 'admin') {
            this.router.navigate(['/admin']);
          } else {
            this.router.navigate(['/dashboard']);
          }
        },
        error: () => this.api.logout()
      });
    }
  }

  signInWithGoogle(): void {
    this.loading = true;
    this.api.getGoogleAuthUrl().subscribe({
      next: (res) => {
        if (res.auth_url) {
          window.location.href = res.auth_url;
        } else {
          alert('Could not retrieve Google Auth URL.');
          this.loading = false;
        }
      },
      error: (err) => {
        alert('Backend connection error: ' + (err.error?.detail || err.message));
        this.loading = false;
      }
    });
  }

  loginDemo(role: 'admin' | 'user'): void {
    this.demoLoading = true;
    this.api.demoLogin(role, 18).subscribe({
      next: (res) => {
        this.api.setToken(res.token);
        if (role === 'admin') {
          this.router.navigate(['/admin']);
        } else {
          this.router.navigate(['/dashboard']);
        }
      },
      error: (err) => {
        alert('Demo login failed: ' + (err.error?.detail || err.message));
        this.demoLoading = false;
      }
    });
  }
}
