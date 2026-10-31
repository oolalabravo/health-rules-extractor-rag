import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ApiService, UserProfile, UserBaseline, HealthMetric } from '../../services/api.service';

@Component({
  selector: 'app-user-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <!-- Top Navigation Bar -->
      <nav class="bg-slate-900/80 border-b border-slate-800 backdrop-blur-md sticky top-0 z-50 px-6 py-3.5 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-gradient-to-tr from-emerald-500 to-cyan-500 rounded-xl flex items-center justify-center shadow-md shadow-emerald-500/20">
            <span class="text-xl">🧬</span>
          </div>
          <div>
            <h1 class="text-base font-bold text-white leading-tight">Clinical Health Intelligence</h1>
            <p class="text-xs text-slate-400">15-Day Physiological Baselining & RAG</p>
          </div>
        </div>

        <div class="flex items-center gap-4">
          <!-- Sync Google Health Button -->
          <button
            (click)="syncGoogleHealth()"
            [disabled]="syncing"
            class="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-emerald-400 border border-emerald-500/30 text-xs font-semibold px-3 py-2 rounded-lg transition duration-150 cursor-pointer disabled:opacity-50"
          >
            <svg [class.animate-spin]="syncing" class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
            </svg>
            <span *ngIf="!syncing">Sync Google Health</span>
            <span *ngIf="syncing">Syncing 180 Days...</span>
          </button>

          <!-- User Role / Admin Switch -->
          <button
            *ngIf="user?.role === 'admin'"
            (click)="goToAdmin()"
            class="bg-purple-950/60 hover:bg-purple-900/60 text-purple-300 border border-purple-500/30 text-xs font-semibold px-3 py-2 rounded-lg transition duration-150 cursor-pointer flex items-center gap-1.5"
          >
            <span>🛡️</span> Admin Console
          </button>

          <!-- User Avatar & Profile -->
          <div class="flex items-center gap-2.5 pl-3 border-l border-slate-800">
            <img
              [src]="user?.avatar_url || 'https://lh3.googleusercontent.com/a/default-user'"
              alt="Avatar"
              class="w-8 h-8 rounded-full border border-slate-700 object-cover"
            />
            <div class="hidden sm:block text-left">
              <div class="text-xs font-semibold text-white leading-none">{{ user?.name || 'Patient' }}</div>
              <div class="text-[10px] text-slate-400 leading-tight mt-0.5">{{ user?.email }}</div>
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

      <!-- Main Dashboard Grid -->
      <main class="flex-grow p-6 max-w-7xl mx-auto w-full space-y-6">

        <!-- 1. 15-DAY BASELINE STATUS HERO CARD -->
        <section class="bg-gradient-to-br from-slate-900 to-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-xl relative overflow-hidden">
          <div class="flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div class="space-y-2 max-w-2xl">
              <div class="flex items-center gap-2.5">
                <span
                  class="inline-flex items-center gap-1.5 text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider"
                  [ngClass]="baseline?.is_ready ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'"
                >
                  <span class="w-2 h-2 rounded-full" [ngClass]="baseline?.is_ready ? 'bg-emerald-500' : 'bg-amber-500 animate-ping'"></span>
                  {{ baseline?.is_ready ? '15-Day Baseline Established' : '15-Day Baseline In Progress' }}
                </span>
                <span class="text-xs text-slate-400">
                  {{ baseline?.days_collected || 0 }} / 15 Days Collected
                </span>
              </div>

              <h2 class="text-xl font-bold text-white">Personalized Physiological Calibration</h2>
              <p class="text-sm text-slate-400 leading-relaxed" *ngIf="baseline?.is_ready">
                Your biological baseline is complete. Acute biometric deviations (sleep debt, elevated resting HR, circadian shifts) are dynamically tested against your personal normal distributions and grounded in peer-reviewed clinical literature.
              </p>
              <p class="text-sm text-amber-300/90 leading-relaxed" *ngIf="!baseline?.is_ready">
                You have collected <strong>{{ baseline?.days_collected || 0 }} of 15 days</strong>. While your baseline is building, the system generates cautious, preliminary lifestyle guidance without premature diagnostic risk classifications.
              </p>
            </div>

            <!-- Progress Meter / Readiness Gauge -->
            <div class="flex flex-col items-center justify-center bg-slate-950/60 border border-slate-800/80 rounded-xl p-5 min-w-[200px]">
              <div class="text-3xl font-extrabold" [ngClass]="baseline?.is_ready ? 'text-emerald-400' : 'text-amber-400'">
                {{ baseline?.days_collected || 0 }}<span class="text-slate-400 text-lg">/15</span>
              </div>
              <div class="text-xs text-slate-400 uppercase tracking-wider font-semibold mt-1">Calibration Days</div>
              <!-- Progress Bar -->
              <div class="w-full bg-slate-800 rounded-full h-2.5 mt-3 overflow-hidden">
                <div
                  class="h-2.5 rounded-full transition-all duration-500"
                  [ngClass]="baseline?.is_ready ? 'bg-emerald-500' : 'bg-gradient-to-r from-amber-500 to-cyan-500'"
                  [style.width.%]="getBaselineProgressPct()"
                ></div>
              </div>
              <div class="text-[11px] text-slate-400 mt-2">
                {{ baseline?.is_ready ? '✓ Full Calibration Active' : (15 - (baseline?.days_collected || 0)) + ' days remaining' }}
              </div>
            </div>
          </div>

          <!-- Baseline Biometric Stat Grid -->
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6 pt-6 border-t border-slate-800/80">
            <div class="bg-slate-950/40 rounded-xl p-3 border border-slate-800/60">
              <span class="text-xs text-slate-400">Baseline Sleep</span>
              <div class="text-lg font-bold text-white mt-1">{{ baseline?.avg_sleep_hours || '--' }} <span class="text-xs font-normal text-slate-400">hrs/night</span></div>
            </div>

            <div class="bg-slate-950/40 rounded-xl p-3 border border-slate-800/60">
              <span class="text-xs text-slate-400">Resting Heart Rate</span>
              <div class="text-lg font-bold text-white mt-1">{{ baseline?.avg_resting_hr || '--' }} <span class="text-xs font-normal text-slate-400">bpm</span></div>
            </div>

            <div class="bg-slate-950/40 rounded-xl p-3 border border-slate-800/60">
              <span class="text-xs text-slate-400">HR Variance</span>
              <div class="text-lg font-bold text-white mt-1">± {{ baseline?.hr_variance || '0.0' }} <span class="text-xs font-normal text-slate-400">bpm</span></div>
            </div>

            <div class="bg-slate-950/40 rounded-xl p-3 border border-slate-800/60">
              <span class="text-xs text-slate-400">Baseline Step Volume</span>
              <div class="text-lg font-bold text-white mt-1">{{ baseline?.avg_steps || '--' }} <span class="text-xs font-normal text-slate-400">steps/day</span></div>
            </div>
          </div>
        </section>

        <!-- 2. CLINICAL RISK SYNTHESIS CONSOLE (GEMINI + FAISS RAG) -->
        <section class="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <!-- Left: Biometric Input / State Adjuster -->
          <div class="lg:col-span-5 bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col justify-between">
            <div class="space-y-4">
              <div class="flex items-center justify-between">
                <h3 class="text-base font-bold text-white flex items-center gap-2">
                  <span>⌚</span> Wearable State Query
                </h3>
                <span class="text-[11px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                  Auto-populated
                </span>
              </div>

              <p class="text-xs text-slate-400">
                Test acute sensor values against your 15-day baseline and our 1,378 embedded clinical rules.
              </p>

              <!-- Sleep Input -->
              <div>
                <label class="flex justify-between text-xs font-semibold text-slate-300 mb-1">
                  <span>Last Night Sleep</span>
                  <span class="text-emerald-400">{{ evalSleepHours }} hrs</span>
                </label>
                <input
                  type="range"
                  min="2"
                  max="12"
                  step="0.5"
                  [(ngModel)]="evalSleepHours"
                  class="w-full accent-emerald-500 cursor-pointer"
                />
              </div>

              <!-- Resting Heart Rate -->
              <div>
                <label class="flex justify-between text-xs font-semibold text-slate-300 mb-1">
                  <span>Resting Heart Rate</span>
                  <span class="text-rose-400">{{ evalRestingHr }} bpm</span>
                </label>
                <input
                  type="range"
                  min="45"
                  max="130"
                  step="1"
                  [(ngModel)]="evalRestingHr"
                  class="w-full accent-rose-500 cursor-pointer"
                />
              </div>

              <!-- Daily Steps -->
              <div>
                <label class="flex justify-between text-xs font-semibold text-slate-300 mb-1">
                  <span>Today's Step Count</span>
                  <span class="text-cyan-400">{{ evalStepCount }} steps</span>
                </label>
                <input
                  type="range"
                  min="500"
                  max="20000"
                  step="500"
                  [(ngModel)]="evalStepCount"
                  class="w-full accent-cyan-500 cursor-pointer"
                />
              </div>

              <!-- Optional Symptom Notes -->
              <div>
                <label class="text-xs font-semibold text-slate-300 mb-1 block">Context / Acute Symptoms</label>
                <textarea
                  [(ngModel)]="evalNote"
                  rows="2"
                  placeholder="e.g. Slept poorly due to travel, feeling fatigued with palpitations..."
                  class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
                ></textarea>
              </div>
            </div>

            <!-- Evaluate Button -->
            <button
              (click)="runPersonalizedEvaluation()"
              [disabled]="evaluating"
              class="w-full mt-6 bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-600 hover:to-cyan-600 text-slate-950 font-bold py-3 px-4 rounded-xl shadow-lg shadow-emerald-500/20 transition duration-150 cursor-pointer disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <svg *ngIf="evaluating" class="animate-spin w-4 h-4 text-slate-950" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
              </svg>
              <span>{{ evaluating ? 'Analyzing Literature Rules...' : 'Run Clinical Risk Evaluation' }}</span>
            </button>
          </div>

          <!-- Right: Report & Grounded Output -->
          <div class="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col justify-between">
            <div class="space-y-4">
              <div class="flex items-center justify-between pb-3 border-b border-slate-800">
                <h3 class="text-base font-bold text-white flex items-center gap-2">
                  <span>📋</span> Literature-Grounded Clinical Report
                </h3>
                <span
                  class="text-[11px] font-semibold px-2.5 py-0.5 rounded-full"
                  [ngClass]="predictionResult?.baseline_ready ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'"
                >
                  {{ predictionResult?.baseline_ready ? 'Personalized Baseline Active' : 'Tentative Advisory Mode' }}
                </span>
              </div>

              <!-- Report Body -->
              <div *ngIf="!predictionResult && !evaluating" class="text-center py-12 text-slate-400 text-sm">
                <span class="text-4xl block mb-2">🩺</span>
                Adjust your wearable readings on the left and click <strong>"Run Clinical Risk Evaluation"</strong> to generate a literature-grounded risk report.
              </div>

              <div *ngIf="evaluating" class="text-center py-12 text-slate-400 text-sm">
                <div class="w-8 h-8 border-3 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
                Retrieving nearest causal relations from FAISS and prompting Gemini Flash...
              </div>

              <div *ngIf="predictionResult && !evaluating" class="space-y-4">
                <div class="prose prose-invert max-w-none text-xs sm:text-sm text-slate-300 leading-relaxed whitespace-pre-line bg-slate-950/70 p-4 rounded-xl border border-slate-800/80 font-sans max-h-96 overflow-y-auto">
                  {{ predictionResult.report }}
                </div>

                <!-- Retrieved FAISS Rules Badges -->
                <div *ngIf="predictionResult.retrieved_rules?.length" class="pt-2">
                  <span class="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-2">
                    Grounded Peer-Reviewed Evidence Rules ({{ predictionResult.retrieved_rules.length }} matched):
                  </span>
                  <div class="space-y-2">
                    <div
                      *ngFor="let rule of predictionResult.retrieved_rules"
                      class="text-[11px] bg-slate-950/80 border border-slate-800 p-2.5 rounded-lg text-slate-300 flex items-start gap-2"
                    >
                      <span class="text-emerald-400 font-bold">•</span>
                      <span>{{ rule.content }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="text-[11px] text-slate-400 mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between">
              <span>Grounding: 1,378 FAISS Vectors</span>
              <span>Model: Google Gemini 3.5 Flash</span>
            </div>
          </div>
        </section>

        <!-- 3. WEARABLE HISTORY (RECENT 14 DAYS) -->
        <section class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h3 class="text-base font-bold text-white">Wearable Sync Timeline (Last 14 Days)</h3>
              <p class="text-xs text-slate-400">Directly synchronized from Google Fitness REST API</p>
            </div>
            <span class="text-xs text-slate-400">Total Recorded: {{ timeline.length }} days</span>
          </div>

          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs">
              <thead class="bg-slate-950/80 text-slate-400 font-semibold border-b border-slate-800">
                <tr>
                  <th class="py-2.5 px-3">Date</th>
                  <th class="py-2.5 px-3">Sleep Duration</th>
                  <th class="py-2.5 px-3">Deep / REM Sleep</th>
                  <th class="py-2.5 px-3">Resting HR</th>
                  <th class="py-2.5 px-3">Average HR</th>
                  <th class="py-2.5 px-3">Daily Steps</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-800/60 text-slate-300">
                <tr *ngFor="let row of getRecentTimeline()" class="hover:bg-slate-800/40 transition">
                  <td class="py-2.5 px-3 font-mono text-slate-400">{{ row.date }}</td>
                  <td class="py-2.5 px-3 font-semibold text-white">{{ row.sleep_hours }} hrs</td>
                  <td class="py-2.5 px-3 text-slate-400">{{ row.deep_sleep_minutes }}m / {{ row.rem_sleep_minutes }}m</td>
                  <td class="py-2.5 px-3 text-rose-400 font-semibold">{{ row.resting_heart_rate }} bpm</td>
                  <td class="py-2.5 px-3 text-slate-400">{{ row.avg_heart_rate }} bpm</td>
                  <td class="py-2.5 px-3 text-cyan-400 font-semibold">{{ row.step_count.toLocaleString() }}</td>
                </tr>
                <tr *ngIf="!timeline?.length">
                  <td colspan="6" class="py-8 text-center text-slate-400">
                    No wearable days recorded yet. Click "Sync Google Health" above to pull your last 6 months of data!
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

      </main>
    </div>
  `
})
export class UserDashboardComponent implements OnInit {
  user: UserProfile | null = null;
  baseline: UserBaseline | null = null;
  timeline: HealthMetric[] = [];
  syncing = false;

  // Evaluation form state
  evalSleepHours = 6.5;
  evalRestingHr = 74;
  evalStepCount = 8200;
  evalNote = '';
  evaluating = false;
  predictionResult: any = null;

  constructor(private api: ApiService, private router: Router) {}

  ngOnInit(): void {
    this.loadUserData();
    this.loadHealthSummary();
  }

  loadUserData(): void {
    this.api.getMe().subscribe({
      next: (res) => {
        this.user = res.user;
        this.baseline = res.baseline;
      },
      error: () => {
        this.api.logout();
        this.router.navigate(['/login']);
      }
    });
  }

  loadHealthSummary(): void {
    this.api.getHealthSummary().subscribe({
      next: (res) => {
        this.baseline = res.baseline;
        this.timeline = res.timeline;
        if (this.timeline.length > 0) {
          const latest = this.timeline[this.timeline.length - 1];
          if (latest.sleep_hours > 0) this.evalSleepHours = latest.sleep_hours;
          if (latest.resting_heart_rate > 0) this.evalRestingHr = Math.round(latest.resting_heart_rate);
          if (latest.step_count > 0) this.evalStepCount = latest.step_count;
        }
      }
    });
  }

  syncGoogleHealth(): void {
    this.syncing = true;
    this.api.syncHealth(180).subscribe({
      next: (res) => {
        this.syncing = false;
        alert(`Successfully synced ${res.days_synced || 0} days of wearable data!`);
        this.loadHealthSummary();
      },
      error: (err) => {
        this.syncing = false;
        alert('Sync notice: ' + (err.error?.detail || err.message));
      }
    });
  }

  runPersonalizedEvaluation(): void {
    this.evaluating = true;
    this.api.predictPersonalized({
      query_description: this.evalNote || undefined,
      override_sleep_hours: this.evalSleepHours,
      override_resting_hr: this.evalRestingHr,
      override_step_count: this.evalStepCount
    }).subscribe({
      next: (res) => {
        this.evaluating = false;
        this.predictionResult = res;
      },
      error: (err) => {
        this.evaluating = false;
        alert('Evaluation error: ' + (err.error?.detail || err.message));
      }
    });
  }

  getBaselineProgressPct(): number {
    const days = this.baseline?.days_collected || 0;
    return Math.min(100, Math.round((days / 15) * 100));
  }

  getRecentTimeline(): HealthMetric[] {
    return [...this.timeline].reverse().slice(0, 14);
  }

  goToAdmin(): void {
    this.router.navigate(['/admin']);
  }

  logout(): void {
    this.api.logout();
    this.router.navigate(['/login']);
  }
}
