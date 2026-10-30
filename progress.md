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
| **Synthesis API** | [`querry.py`](querry.py) | `http://127.0.0.1:8001` | 🟢 Active | FastAPI server with Gemini 3.5 Flash primary, multi-tier fallback, and 15s timeout. |
| **Vector DB** | [`local_persistent_vector_store/`](local_persistent_vector_store/) | Local Disk (FAISS) | 🟢 Active | 1,367 embedded vectors indexed via local Ollama `nomic-embed-text` (768-dim). |
| **Ingestion Engine**| [`main.py`](main.py) | Local CLI / Module | 🟢 Blazing Fast (4-8s) | Direct Gemini Flash-Lite fast path (`gemini-3.5-flash-lite`), sanitized Colab fallback, and retry-guarded FAISS persistence. |
| **Colab Extractor** | Colab Notebook `2ZZKWkd_MzVj` | FastAPI + Cloudflare/Ngrok | 🟢 Live & Autonomous | Dual-tunnel (Cloudflare zero-auth + Ngrok), non-blocking daemon thread, `/health` route, 4x parallel async inference. |
| **Colab Automator** | [`colab_automator.py`](colab_automator.py) | Local CLI / Module | 🟢 Active | Zero-touch MCP orchestrator: automatically triggers Cell 0, captures tunnel endpoint, syncs `.env`, and validates health. |
| **Paper Hunter** | [`paper_hunter.py`](paper_hunter.py) | Local CLI | 🟢 Live Visual Progress | Real-time terminal progress (download %, page parsing, rule extraction preview), strict `%PDF-` validation, and HTML paywall rejection. |
| **Paper Ledger** | [`paper_ledger.json`](paper_ledger.json) | Local Disk (JSON) | 🟢 Active | Normalized Jaccard + slug duplicate detector prevents duplicate paper extraction across sessions (12+ papers tracked). |

---

## 📚 Ingested Literature & Vector Index State

- **Current Vector Count**: 1,367 embedded causal rules.
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

---

## 🕒 Recent Session Log (2026-10-31)
1. **Gemini API & Hanging Fix**:
   - Diagnosed 503 high-demand spike on `gemini-3.8-flash` causing infinite SDK backoff retry loop.
   - Migrated primary model to `gemini-3.5-flash` with candidate fallbacks and 15s deadline.
2. **Autonomous Colab Execution & Zero-Touch URL Sync**:
   - Re-architected Colab Cell 0 into non-blocking daemon server (`threading.Thread`) with `/health` endpoint.
   - Implemented dual-tunnel engine: Ngrok (if token present) + Cloudflare zero-auth tunnel fallback.
   - Built [`colab_automator.py`](colab_automator.py) using stdio MCP to trigger Cell 0 and save `COLAB_API_URL` to `.env`.
3. **5-Second Extraction Acceleration & HTML Error Fix**:
   - Diagnosed root causes of HTML errors: non-PDF publisher paywall landing pages and Cloudflare 524 timeouts during slow 150-second Ollama runs.
   - Resolved Gemini Free Tier 429 quota exhaustion by upgrading to **`gemini-3.5-flash-lite`** (with candidate fallbacks: `gemini-3.1-flash-lite`, `gemini-3.8-flash`).
   - Cut per-paper extraction time from **~2.5 minutes down to ~4–8 seconds**!
   - Implemented strict `%PDF-` magic-byte verification and HTML rejection in `download_paper_pdf()`.
   - Built real-time 4-step terminal progress display with live streaming download percentage and rule preview.
   - Sanitized all Colab HTTP error codes (never dumps raw HTML into console).

---

## 🎯 Next Tasks & Milestones
- [x] Implement `paper_ledger.json` tracking papers and avoiding duplicates.
- [x] Modularize `main.py` and build `paper_hunter.py`.
- [x] Implement non-blocking Colab Cell 0 with Cloudflare zero-auth tunnel and health checks.
- [x] Implement `colab_automator.py` for autonomous cell trigger and `.env` URL synchronization.
- [x] Implement direct Gemini Flash-Lite fast path (4-8s extraction).
- [x] Implement HTML paywall rejection and sanitize error reporting.
- [x] Implement live 4-step real-time terminal progress indicators.
- [x] Push all fixes to GitHub repository.
