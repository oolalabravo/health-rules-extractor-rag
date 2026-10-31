import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-auth-callback',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="min-h-screen bg-slate-950 flex flex-col justify-center items-center px-4">
      <div class="bg-slate-900 border border-slate-800 p-8 rounded-2xl max-w-sm w-full text-center shadow-xl">
        <div class="w-12 h-12 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
        <h2 class="text-lg font-semibold text-white">Completing Google Authentication</h2>
        <p class="text-sm text-slate-400 mt-2">Connecting Google Fitness & Synchronizing 6-Month Baseline...</p>
      </div>
    </div>
  `
})
export class AuthCallbackComponent implements OnInit {
  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private api: ApiService
  ) {}

  ngOnInit(): void {
    this.route.queryParams.subscribe(params => {
      const token = params['token'];
      const code = params['code'];
      const error = params['error'];

      if (error) {
        alert('Google Authentication Error: ' + error);
        this.router.navigate(['/login']);
        return;
      }

      if (token) {
        // Direct JWT passed back from backend redirect
        this.api.setToken(token);
        this.routeUser();
      } else if (code) {
        // Code exchange via POST
        const redirectUri = window.location.origin + '/auth/callback';
        this.api.exchangeGoogleToken(code, redirectUri).subscribe({
          next: (res) => {
            this.api.setToken(res.token);
            this.routeUser();
          },
          error: (err) => {
            alert('Failed to exchange Google authorization code: ' + (err.error?.detail || err.message));
            this.router.navigate(['/login']);
          }
        });
      } else {
        this.router.navigate(['/login']);
      }
    });
  }

  private routeUser(): void {
    this.api.getMe().subscribe({
      next: (res) => {
        if (res.user.role === 'admin') {
          this.router.navigate(['/admin']);
        } else {
          this.router.navigate(['/dashboard']);
        }
      },
      error: () => {
        this.router.navigate(['/dashboard']);
      }
    });
  }
}
