# 📊 Project Progress & Context State Log

> **Note for Subsequent Agents**: This file is maintained per [`AGENT_RULES.md`](AGENT_RULES.md). Please update this document whenever you implement changes, ingest new papers, or modify pipeline architecture.

---

## 📌 Project Overview
- **Repository**: [https://github.com/oolalabravo/health-rules-extractor-rag](https://github.com/oolalabravo/health-rules-extractor-rag)
- **Purpose**: Peer-reviewed Clinical Intelligence & Retrieval-Augmented Generation (RAG) system. Extracts causal biomedical relations from literature PDFs and synthesizes physiological risk reports for wearable sensor queries with verified scientific citations.
- **Colab Pipeline**: [https://colab.research.google.com/drive/1lmXZjH49KE6-8EeNyUAFmHm2gQ8LzW6V](https://colab.research.google.com/drive/1lmXZjH49KE6-8EeNyUAFmHm2gQ8LzW6V)

---

## 🏗️ Architecture & Component Status

| Component | File / Path | Runtime / Port | Status | Details |
| :--- | :--- | :--- | :--- | :--- |
| **Synthesis & RBAC API** | [`querry.py`](querry.py) | `http://127.0.0.1:8001` | 🟢 Active (17 Routes) | FastAPI server with Google OAuth2, JWT RBAC (`user` vs `admin`), baseline-aware risk synthesis, and Admin Paper Hunter endpoints. |
| **Google Health Engine** | [`google_health_service.py`](google_health_service.py) | Local Module | 🟢 Active | Google Fitness REST API sync (180 days history: sleep, resting HR, steps) + 15-day physiological baselining algorithm. |
| **Relational Database** | [`database.py`](database.py) | `clinical_health.db` (SQLite) | 🟢 Active | SQLAlchemy persistent schema: `users`, `oauth_tokens`, `daily_health_metrics`, and `user_baselines`. |
| **Vector DB** | [`local_persistent_vector_store/`](local_persistent_vector_store/) | Local Disk (FAISS) | 🟢 Active | 1,378 embedded vectors indexed via local Ollama `nomic-embed-text` (768-dim) with offline ledger fallback. |
| **Ingestion Engine**| [`main.py`](main.py) | Local CLI / Module | 🟢 Blazing Fast (3-8s) | Direct Gemini Flash-Lite fast path (`gemini-3.5-flash-lite`), handles both PDFs and XML text transcripts, sanitized Colab fallback. |
| **Angular Frontend** | [`frontend/`](frontend/) | `http://localhost:4200` | 🟢 Built & Ready | Angular 18 standalone app: Google Sign-In, 15-day baseline tracker, wearable timeline, and Admin Paper Hunter Studio GUI. |
| **System Launcher** | [`start.cmd`](start.cmd) | Windows Batch | 🟢 Live Hot-Reload | One-click launcher that starts both FastAPI (`--reload`) and Angular (`live-reload`) in separate windows and opens browser. |
| **Paper Hunter** | [`paper_hunter.py`](paper_hunter.py) | Local CLI / API | 🟢 Zero-Skip Multi-Source Resolver | 5-Tier waterfall resolver (Europe PMC fullTextXML REST API, direct binary PDF stream with `%PDF-` validation, Unpaywall, abstract fallback). |
| **Paper Ledger** | [`paper_ledger.json`](paper_ledger.json) | Local Disk (JSON) | 🟢 Active | Normalized Jaccard + slug duplicate detector prevents duplicate paper extraction across sessions (16 papers tracked). |

---

## 📚 Ingested Literature & Vector Index State

- **Current Vector Count**: 1401,378 embedded causal rules.
- **Embedded Literature**:
  - *The association between sleep deprivation and arterial pressure variations: a systematic literature review.pdf* (38 rules)
  - *Fetal Sleep: A Cross-Species Review of Physiology, Measurement, and Classification* (4 rules)
  - *Sleep Staging from Electrocardiography and Respiration with Deep Learning* (4 rules)
  - *A Large Collection of Real-world Pediatric Sleep Studies* (2 rules)
  - *Sleep and its relation to cognition and behaviour in preschool-aged children* (6 rules)
  - *Dynamic gNodeB Sleep Control for Energy-Conserving 5G Radio Access Network* (11 rules)
  - *Quantified Sleep: Machine learning techniques for observational n-of-1 studies* (3 rules)
  - *Quantum Anti-Zeno Treatment of Zeno-type Sleep Disorders* (3 rules)
  - *Evaluation of the LEP Centre-of-Mass Energy Above the W-Pair Production Threshold* (16 rules)
  - *Permutation time irreversibility in sleep electroencephalograms* (22 rules)
  - *Daily step-count and sleep metrics across pregnancy: an observational analysis of the LEAP cluster randomized clinical trial* (9 rules)
  - *Joint associations of device-measured step count and sleep duration with incident major adverse cardiovascular events: prospective analysis of the UK Biobank* (2 rules)

---
  - *Shesop Healthcare: Android application to monitor heart rate variance, display influenza and stress condition using Polar H7* (Ingested 2026-11-01 01:15, +0 rules, total: 0)
  - *Shesop Healthcare: Android application to monitor heart rate variance, display influenza and stress condition using Polar H7* (Ingested 2026-11-01 01:15, +0 rules, total: 0)
  - *Frequency Structure of Heart Rate Variability* (Ingested 2026-11-01 01:15, +1 rules, total: 1389)
  - *VitalLens 2.0: High-Fidelity rPPG for Heart Rate Variability Estimation from Face Video* (Ingested 2026-11-01 01:15, +2 rules, total: 1391)
  - *Measuring long-term physical activity in patients with heart failure and its relation to health-related outcomes* (Ingested 2026-11-01 01:16, +7 rules, total: 1398)
  - *Real-World Health Monitoring Using Wrist-Worn Wearables in Community-Dwelling Older Adults in China: Mixed Methods Feasibility Study* (Ingested 2026-11-01 01:16, +4 rules, total: 1402)
  - *Estimating Heart Failure Health Status From Multimodal Wearables: Implementation of a Feature-Engineering Framework for KCCQ-12 Prediction* (Ingested 2026-11-01 01:16, +4 rules, total: 1395)
  - *A Web-Based, Pedometer-Mediated Intervention Increases Amount and Intensity of Physical Activity in COPD: A Randomized Controlled Trial* (Ingested 2026-11-01 01:18, +3 rules, total: 1398)
  - *Feasibility and Clinical Outcomes of a 6-Month Home-Based Telerehabilitation Program in Patients with Peripheral Arterial Disease: A Prospective Single-Arm Study* (Ingested 2026-11-01 01:18, +6 rules, total: 1401)

## 🕒 Recent Session Log (2026-11-01)
1. **Google Health & Google Fitness OAuth 2.0 Integration**:
   - Integrated client ID `1059027165335-m2h68ikq9uremd83bk07bvmkprmn3ede.apps.googleusercontent.com` and credentials in `.env`.
   - Built [`google_health_service.py`](google_health_service.py) with OAuth2 authorization code exchange, dynamic redirect URI matching, automatic token refresh, and Google Fitness REST API aggregate ingestion (`com.google.step_count.delta`, `com.google.sleep.segment`, `com.google.heart_rate.bpm`).
   - Sliced 180-day historical data synchronization into **6 safe 30-day sequential rolling windows** to eliminate Google's `400 Bad Request: "aggregate duration too large"` restriction.
2. **15-Day Physiological Baselining Engine**:
   - Engineered baseline engine calculating personal normal distributions ($\mu \pm 1.5\sigma$) for daily sleep, resting HR, and step volume.
   - **Baseline Ready (>= 15 days)**: Compares acute biometrics against established personal baseline for high-confidence clinical risk deduction.
   - **Baseline In Progress (< 15 days)**: Formulates tentative, non-alarmist lifestyle guidance while displaying remaining calibration days (X/15).
3. **FastAPI Backend RBAC Expansion**:
   - Upgraded [`querry.py`](querry.py) with 17 registered endpoints:
     - Auth: `/api/auth/google/url`, `/api/auth/google/callback`, `/api/auth/google/token`, `/api/auth/me`, `/api/auth/demo-login`.
     - Health: `/api/health/sync`, `/api/health/summary`.
     - Prediction: `/api/predict-personalized` with baseline context injection.
     - Admin: `/api/admin/overview`, `/api/admin/papers/search`, `/api/admin/papers/extract`, `/api/admin/papers/ledger`.
4. **Angular 18 Frontend Application**:
   - Scaffolded standalone Angular 18 app in [`frontend/`](frontend/) with Tailwind CSS styling.
   - Implemented `LoginComponent` with Google Sign-In and instant demo access (Admin/Patient).
   - Implemented `UserDashboardComponent` with 15-day calibration meter, 6-month metric timeline, and personalized risk evaluator.
   - Implemented `AdminDashboardComponent` featuring platform analytics and the **Research Paper Hunter Studio GUI**, allowing admins to hunt and extract academic papers directly from the browser!
   - Successfully verified compilation via `npm run build` (0 errors, 0 warnings).

---

## 🎯 Next Tasks & Milestones
- [x] Configure Google Cloud Project credentials and `.env`.
- [x] Implement SQLite database models (`database.py`).
- [x] Implement Google Fitness REST API sync & 15-day baselining algorithm (`google_health_service.py`).
- [x] Upgrade FastAPI backend with RBAC and Admin Paper Hunter endpoints (`querry.py`).
- [x] Scaffold and build Angular 18 frontend dashboard (`frontend/`).
- [x] Push all full-stack updates to GitHub repository.
