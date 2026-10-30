# 📊 Project Progress & Context State Log

> **Note for Subsequent Agents**: This file is maintained per [`AGENT_RULES.md`](AGENT_RULES.md). Please update this document whenever you implement changes, ingest new papers, or modify pipeline architecture.

---

## 📌 Project Overview
- **Repository**: [https://github.com/oolalabravo/health-rules-extractor-rag](https://github.com/oolalabravo/health-rules-extractor-rag) (Latest commit: `966d617`)
- **Purpose**: Peer-reviewed Clinical Intelligence & Retrieval-Augmented Generation (RAG) system. Extracts causal biomedical relations from literature PDFs and synthesizes physiological risk reports for wearable sensor queries with verified scientific citations.
- **Colab Pipeline**: [https://colab.research.google.com/drive/1lmXZjH49KE6-8EeNyUAFmHm2gQ8LzW6V](https://colab.research.google.com/drive/1lmXZjH49KE6-8EeNyUAFmHm2gQ8LzW6V)

---

## 🏗️ Architecture & Component Status

| Component | File / Path | Runtime / Port | Status | Details |
| :--- | :--- | :--- | :--- | :--- |
| **Synthesis API** | [`querry.py`](querry.py) | `http://127.0.0.1:8001` | 🟢 Active | FastAPI server with Gemini 3.5 Flash primary, multi-tier fallback, and 15s timeout. |
| **Vector DB** | [`local_persistent_vector_store/`](local_persistent_vector_store/) | Local Disk (FAISS) | 🟢 Active | 38 embedded vectors indexed via local Ollama `nomic-embed-text` (768-dim). |
| **Ingestion Engine**| [`main.py`](main.py) | Local CLI / Module | 🟢 Active | Uploads PDF to Colab extraction server, receives JSON rules, and cumulatively merges to FAISS. |
| **Colab Extractor** | Colab Notebook `2ZZKWkd_MzVj` | FastAPI + ngrok (:8000) | 🟢 Accelerated | Updated via `colab-mcp` with smart bibliography filtering, 2.5k chunk size, async 4x semaphore parallelism, and Gemini fast-path. |
| **Paper Hunter** | [`paper_hunter.py`](paper_hunter.py) | Local CLI | 🟢 Active | Automated academic search (arXiv + Europe PMC), fuzzy deduplication ledger, interactive CLI, and extraction trigger. |
| **Paper Ledger** | [`paper_ledger.json`](paper_ledger.json) | Local Disk (JSON) | 🟢 Active | Normalized Jaccard + slug duplicate detector prevents duplicate paper extraction. |

---

## 📚 Ingested Literature & Vector Index State

- **Current Vector Count**: 38 embedded causal rules.
- **Embedded Literature**:
  1. *The association between sleep deprivation and arterial pressure variations: a systematic literature review.pdf*
     - Authors: Alécio Vinícius Sá Gomes e Farias, Mariana Peixoto de Lima Cavalcanti, Marcelo Alcântara de Passos Junior, Bruna del Vechio Koike (2022)
     - Extracted Rules: 38

---

## 🕒 Recent Session Log (2026-10-31)
1. **Gemini API & Hanging Fix**:
   - Diagnosed 503 high-demand spike on `gemini-3.8-flash` causing infinite SDK backoff retry loop.
   - Migrated primary model to `gemini-3.5-flash` with candidate fallbacks and 15s deadline.
   - Relocated FAISS database from foreign VS Code path to project directory.
2. **GitHub Deployment**:
   - Created public repository `oolalabravo/health-rules-extractor-rag`.
   - Isolated API keys into `.env` (gitignored) with clean `.env.example`.
   - Authored comprehensive `README.md` with full architectural diagrams and relation schemas.
3. **Colab MCP Connection**:
   - Resolved browser/port mismatch (Microsoft Edge vs Google Chrome default handler).
   - Patched `colab_mcp` to support direct notebook URL hash injection and optimized `mcp_config.json`.
   - Connected live Colab notebook session and verified via `get_cells`.
4. **Agent Rules & Progress Tracking**:
   - Implemented `AGENT_RULES.md` in root workspace and sub-workspace.
   - Rule 1 enforces mandatory `progress.md` persistence for inter-agent continuity.
5. **Colab Extraction Optimization**:
   - Directly updated Cell 0 in Colab via `colab-mcp`.
   - Chunk size enlarged to 2,500 chars (cutting chunk count by ~50%).
   - Pre-filtering discards references, bibliographies, acknowledgments, and non-informative text (~30% chunk reduction).
   - `asyncio.Semaphore(4)` parallel extraction using `AsyncClient`.
   - Added `x-gemini-api-key` fast-path for sub-5-second extraction.
6. **Automated Paper Hunter & Deduplication**:
   - Built `paper_hunter.py` with multi-engine search across arXiv API and Europe PMC API.
   - Built fuzzy title matching + token overlap + slug deduplication via `paper_ledger.json`.
   - Interactive CLI lets user input topic, choose count, select paper(s), download PDF, and trigger sync.
   - All changes committed and pushed to `main` (`966d617`).

---

## 🎯 Next Tasks & Milestones
- [x] Implement `paper_ledger.json` tracking initial paper.
- [x] Modularize `main.py` for headless invocation by `paper_hunter.py`.
- [x] Build `paper_hunter.py` with multi-engine academic search, deduplication, and user interactive selection.
- [x] Accelerate Colab Notebook Cell 0 via `colab-mcp` (async parallel chunks, smart bibliography filtering).
- [x] Verify search, deduplication logic, and git synchronization.
- [ ] Run Cell 0 in Colab to launch the optimized FastAPI server and obtain fresh ngrok URL.
- [ ] Run `python paper_hunter.py` to ingest a new paper end-to-end.
