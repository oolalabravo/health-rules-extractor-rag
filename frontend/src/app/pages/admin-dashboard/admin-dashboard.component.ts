import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ApiService, UserProfile } from '../../services/api.service';

@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <!-- Top Admin Navigation Bar -->
      <nav class="bg-slate-900/90 border-b border-purple-900/40 backdrop-blur-md sticky top-0 z-50 px-6 py-3.5 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-gradient-to-tr from-purple-600 to-indigo-500 rounded-xl flex items-center justify-center shadow-md shadow-purple-500/20">
            <span class="text-xl">🛡️</span>
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h1 class="text-base font-bold text-white leading-tight">Admin Intelligence Console</h1>
              <span class="text-[10px] bg-purple-500/20 text-purple-300 border border-purple-500/40 px-2 py-0.5 rounded font-bold uppercase tracking-wider">
                RBAC Level 1
              </span>
            </div>
            <p class="text-xs text-slate-400">System Metrics & Research Paper Hunter Studio</p>
          </div>
        </div>

        <div class="flex items-center gap-4">
          <!-- Switch to User / Patient View -->
          <button
            (click)="goToUserDashboard()"
            class="bg-slate-800 hover:bg-slate-700 text-cyan-400 border border-cyan-500/30 text-xs font-semibold px-3 py-2 rounded-lg transition duration-150 cursor-pointer flex items-center gap-1.5"
          >
            <span>👤</span> Patient Dashboard
          </button>

          <!-- Admin Avatar & Profile -->
          <div class="flex items-center gap-2.5 pl-3 border-l border-slate-800">
            <img
              [src]="user?.avatar_url || 'https://lh3.googleusercontent.com/a/default-user'"
              alt="Avatar"
              class="w-8 h-8 rounded-full border border-purple-500/50 object-cover"
            />
            <div class="hidden sm:block text-left">
              <div class="text-xs font-semibold text-white leading-none">{{ user?.name || 'Admin User' }}</div>
              <div class="text-[10px] text-purple-400 leading-tight mt-0.5">{{ user?.email }}</div>
            </div>
          </div>

          <!-- Logout Button -->
          <button
            (click)="logout()"
            class="text-slate-400 hover:text-rose-400 text-xs p-1.5 transition duration-150 cursor-pointer"
            title="Sign Out"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path>
            </svg>
          </button>
        </div>
      </nav>

      <!-- Main Admin Content Container -->
      <main class="flex-grow p-6 max-w-7xl mx-auto w-full space-y-6">

        <!-- 1. PLATFORM ANALYTICS GRID -->
        <section class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <!-- Stat Card 1: Active Users -->
          <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg relative overflow-hidden">
            <div class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Active User Accounts</div>
            <div class="text-3xl font-extrabold text-white mt-2">{{ overview?.total_users || 0 }}</div>
            <div class="text-[11px] text-emerald-400 mt-2 flex items-center gap-1">
              <span>●</span> {{ overview?.active_baselines || 0 }} Established Baselines
            </div>
          </div>

          <!-- Stat Card 2: Biometric Datapoints -->
          <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg relative overflow-hidden">
            <div class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Ingested Datapoints</div>
            <div class="text-3xl font-extrabold text-cyan-400 mt-2">{{ overview?.total_datapoints || 0 }}</div>
            <div class="text-[11px] text-slate-400 mt-2">Daily Google Fitness Logs</div>
          </div>

          <!-- Stat Card 3: FAISS Vectors -->
          <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg relative overflow-hidden">
            <div class="text-xs font-semibold text-slate-400 uppercase tracking-wider">FAISS Causal Vectors</div>
            <div class="text-3xl font-extrabold text-purple-400 mt-2">{{ overview?.total_vectors || 1378 }}</div>
            <div class="text-[11px] text-purple-300 mt-2">768-dim nomic-embed-text</div>
          </div>

          <!-- Stat Card 4: Indexed Studies -->
          <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg relative overflow-hidden">
            <div class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Indexed Research Papers</div>
            <div class="text-3xl font-extrabold text-emerald-400 mt-2">{{ overview?.indexed_papers_count || 14 }}</div>
            <div class="text-[11px] text-slate-400 mt-2">In Persistent Ledger</div>
          </div>
        </section>

        <!-- 2. RESEARCH PAPER HUNTER STUDIO (GUI REPLACING THE TERMINAL) -->
        <section class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
          <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
            <div>
              <div class="flex items-center gap-2">
                <span class="text-2xl">🔎</span>
                <h2 class="text-lg font-bold text-white">Research Paper Hunter Studio (Admin GUI)</h2>
              </div>
              <p class="text-xs text-slate-400 mt-0.5">
                Hunt peer-reviewed papers on Europe PMC & arXiv, resolve open-access bodies via REST XML, and extract causal rules in 3–8 seconds.
              </p>
            </div>
            <span class="text-xs text-slate-400 bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800">
              ⚡ Engine: Gemini 3.5 Flash-Lite (Fast Path)
            </span>
          </div>

          <!-- Search Input Bar -->
          <div class="flex flex-col sm:flex-row gap-3">
            <input
              type="text"
              [(ngModel)]="searchQuery"
              (keyup.enter)="searchPapers()"
              placeholder="Enter health / lifestyle research idea (e.g. intermittent fasting, circadian rhythm, step count)..."
              class="flex-grow bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
            />
            <button
              (click)="searchPapers()"
              [disabled]="searching || !searchQuery.trim()"
              class="bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white font-bold px-6 py-3 rounded-xl transition duration-150 cursor-pointer disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <svg *ngIf="searching" class="animate-spin w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
              </svg>
              <span>{{ searching ? 'Searching Academic APIs...' : 'Search Papers' }}</span>
            </button>
          </div>

          <!-- Recently Discovered Rules Live Card -->
          <div *ngIf="lastExtractionResult" class="bg-emerald-950/40 border border-emerald-500/40 rounded-xl p-5 space-y-3">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2 text-emerald-400 font-bold text-sm">
                <span>🎉</span>
                <span>Successfully Ingested: {{ lastExtractionResult.title }}</span>
              </div>
              <span class="text-xs bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded font-mono">
                +{{ lastExtractionResult.new_rules_extracted }} Rules in {{ lastExtractionResult.elapsed_seconds }}s
              </span>
            </div>
            <p class="text-xs text-slate-300">
              Total vector database size expanded to <strong>{{ lastExtractionResult.total_vectors }}</strong> vectors.
            </p>
            <!-- Rules Preview -->
            <div class="space-y-2 mt-2">
              <div
                *ngFor="let r of lastExtractionResult.rules"
                class="bg-slate-950/80 border border-emerald-500/20 p-2.5 rounded-lg text-xs text-slate-300 flex items-start gap-2"
              >
                <span class="text-emerald-400 font-bold">➔</span>
                <div>
                  <strong class="text-white">{{ r.metric_a }}</strong> ({{ r.change_a }}) +
                  <strong class="text-white">{{ r.metric_b }}</strong> ({{ r.change_b }}) leads to
                  <span class="text-emerald-300 font-semibold">{{ r.predicted_outcome }}</span>
                  <p class="text-[11px] text-slate-400 mt-1 italic">"{{ r.confidence_rationale }}"</p>
                </div>
              </div>
            </div>
          </div>

          <!-- Candidate Search Results List -->
          <div *ngIf="candidates.length > 0" class="space-y-4">
            <h3 class="text-xs font-bold text-slate-400 uppercase tracking-wider">Candidate Papers Found ({{ candidates.length }}):</h3>

            <div *ngFor="let paper of candidates" class="bg-slate-950 border border-slate-800 rounded-xl p-5 space-y-3 hover:border-slate-700 transition">
              <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                <div class="space-y-1">
                  <div class="flex items-center gap-2 flex-wrap">
                    <span
                      class="text-[10px] font-bold px-2 py-0.5 rounded uppercase"
                      [ngClass]="paper.already_extracted ? 'bg-slate-800 text-slate-400 border border-slate-700' : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'"
                    >
                      {{ paper.already_extracted ? 'In Local Vector Store' : 'New Candidate' }}
                    </span>
                    <span class="text-[10px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded">
                      Source: {{ paper.source }}
                    </span>
                    <span *ngIf="paper.pmcid" class="text-[10px] bg-purple-500/10 text-purple-300 border border-purple-500/20 px-2 py-0.5 rounded">
                      {{ paper.pmcid }}
                    </span>
                  </div>

                  <h4 class="text-sm font-bold text-white leading-snug">{{ paper.title }}</h4>
                  <p class="text-xs text-slate-400">
                    👤 {{ paper.authors.join(', ') }} ({{ paper.year }})
                  </p>
                </div>

                <!-- Extract Action Button -->
                <button
                  (click)="extractPaper(paper)"
                  [disabled]="paper.already_extracted || extractingPaperId === paper.title"
                  class="flex-shrink-0 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs px-4 py-2.5 rounded-lg transition duration-150 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5"
                >
                  <svg *ngIf="extractingPaperId === paper.title" class="animate-spin w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                  </svg>
                  <span>{{ extractingPaperId === paper.title ? 'Extracting Rules...' : (paper.already_extracted ? 'Already Extracted' : 'Extract Causal Rules') }}</span>
                </button>
              </div>

              <!-- Summary Abstract Preview -->
              <p class="text-xs text-slate-400 line-clamp-3 leading-relaxed">
                {{ paper.summary }}
              </p>
            </div>
          </div>
        </section>

        <!-- 3. INDEXED LITERATURE LEDGER TABLE -->
        <section class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h3 class="text-base font-bold text-white">Peer-Reviewed Literature Ledger</h3>
              <p class="text-xs text-slate-400">Persistently tracked in paper_ledger.json to prevent duplicate extractions</p>
            </div>
            <span class="text-xs text-purple-400 font-mono font-bold">{{ ledgerPapers.length }} Ingested Studies</span>
          </div>

          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs">
              <thead class="bg-slate-950/80 text-slate-400 font-semibold border-b border-slate-800">
                <tr>
                  <th class="py-2.5 px-3">Paper Title</th>
                  <th class="py-2.5 px-3">Lead Authors</th>
                  <th class="py-2.5 px-3">Year</th>
                  <th class="py-2.5 px-3">Rules</th>
                  <th class="py-2.5 px-3">Source File</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-800/60 text-slate-300">
                <tr *ngFor="let p of ledgerPapers" class="hover:bg-slate-800/40 transition">
                  <td class="py-2.5 px-3 font-semibold text-white max-w-sm truncate" [title]="p.title">{{ p.title }}</td>
                  <td class="py-2.5 px-3 text-slate-400 max-w-xs truncate">{{ p.authors }}</td>
                  <td class="py-2.5 px-3 text-slate-400">{{ p.year }}</td>
                  <td class="py-2.5 px-3 font-mono font-bold text-emerald-400">+{{ p.rules_count }}</td>
                  <td class="py-2.5 px-3 text-slate-400 font-mono text-[11px] truncate max-w-xs">{{ p.source_pdf }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

      </main>
    </div>
  `
})
export class AdminDashboardComponent implements OnInit {
  user: UserProfile | null = null;
  overview: any = null;
  ledgerPapers: any[] = [];

  searchQuery = '';
  searching = false;
  candidates: any[] = [];

  extractingPaperId: string | null = null;
  lastExtractionResult: any = null;

  constructor(private api: ApiService, private router: Router) {}

  ngOnInit(): void {
    this.loadUserData();
    this.loadOverview();
    this.loadLedger();
  }

  loadUserData(): void {
    this.api.getMe().subscribe({
      next: (res) => {
        this.user = res.user;
      },
      error: () => {
        this.api.logout();
        this.router.navigate(['/login']);
      }
    });
  }

  loadOverview(): void {
    this.api.getAdminOverview().subscribe({
      next: (res) => {
        this.overview = res;
      }
    });
  }

  loadLedger(): void {
    this.api.getPaperLedger().subscribe({
      next: (res) => {
        this.ledgerPapers = (res.extracted_papers || []).reverse();
      }
    });
  }

  searchPapers(): void {
    if (!this.searchQuery.trim()) return;
    this.searching = true;
    this.candidates = [];
    this.lastExtractionResult = null;

    this.api.searchCandidatePapers(this.searchQuery, 6).subscribe({
      next: (res) => {
        this.searching = false;
        this.candidates = res.candidates || [];
      },
      error: (err) => {
        this.searching = false;
        alert('Search notice: ' + (err.error?.detail || err.message));
      }
    });
  }

  extractPaper(paper: any): void {
    this.extractingPaperId = paper.title;
    this.lastExtractionResult = null;

    this.api.extractPaper(paper).subscribe({
      next: (res) => {
        this.extractingPaperId = null;
        this.lastExtractionResult = res;
        paper.already_extracted = true;
        this.loadOverview();
        this.loadLedger();
      },
      error: (err) => {
        this.extractingPaperId = null;
        alert('Extraction error: ' + (err.error?.detail || err.message));
      }
    });
  }

  goToUserDashboard(): void {
    this.router.navigate(['/dashboard']);
  }

  logout(): void {
    this.api.logout();
    this.router.navigate(['/login']);
  }
}
