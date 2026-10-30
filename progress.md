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
| **Vector DB** | [`local_persistent_vector_store/`](local_persistent_vector_store/) | Local Disk (FAISS) | 🟢 Active | 38 embedded vectors indexed via local Ollama `nomic-embed-text` (768-dim). |
| **Ingestion Engine**| [`main.py`](main.py) | Local CLI | 🟢 Active | Uploads PDF to Colab extraction server, receives JSON rules, and cumulatively merges to FAISS. |
| **Colab Extractor** | Colab Notebook `2ZZKWkd_MzVj` | FastAPI + ngrok (:8000) | 🟢 Connected | Connected via `colab-mcp`. Accelerating with async parallel chunk extraction. |
| **Paper Hunter** | [`paper_hunter.py`](paper_hunter.py) | Local CLI | 🟡 In Development | Automated academic search (arXiv + Europe PMC), deduplication ledger, and extraction trigger. |
| **Paper Ledger** | [`paper_ledger.json`](paper_ledger.json) | Local Disk (JSON) | 🟢 Initialized | Prevents duplicate paper extraction across sessions. |

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
   - Implemented `AGENT_RULES.md` with Rule 1 requiring `progress.md`.

---

## 🎯 Next Tasks & Milestones
- [ ] Implement `paper_ledger.json` tracking initial paper.
- [ ] Modularize `main.py` for headless invocation by `paper_hunter.py`.
- [ ] Build `paper_hunter.py` with multi-engine academic search, deduplication, and user interactive selection.
- [ ] Accelerate Colab Notebook Cell 0 via `colab-mcp` (async parallel chunks, smart bibliography filtering).
- [ ] Test end-to-end paper search, download, extraction, and FAISS indexing.
