# 🤖 AGENT RULES & COLLABORATION GUIDELINES

This file defines the mandatory operational rules for all AI coding agents working on this project. Every agent must read and adhere to these guidelines before making any changes.

---

## 📌 Rule 1: Maintain `progress.md` (Mandatory Context Persistence)
* **Always maintain and update [`progress.md`](progress.md) in the project root.**
* Before concluding your turn or starting a new phase, record:
  1. What was accomplished during the session.
  2. The current architecture and active runtime state (ports, endpoints, models, vector counts).
  3. All newly ingested papers, rules, or schemas.
  4. Immediate next steps and pending tasks.
* **Why**: This ensures that any subsequent agent or conversation session can pick up immediately with full context without repeating investigations or guessing previous state.

---

## 🔒 Rule 2: Strict Secret & Credential Isolation
* **NEVER hardcode API keys, tokens, or credentials in any tracked repository file.**
* Keep all keys inside `.env` (which must strictly remain in `.gitignore`).
* Maintain [`requirements.txt`](requirements.txt) and [`.env.example`](.env.example) with clear instructions for any required environment variables.
* Dynamically resolve keys: `os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")`.

---

## 🪟 Rule 3: Windows Shell & Console Compatibility
* Always reconfigure `sys.stdout` and `sys.stderr` to UTF-8 with error replacement on Windows consoles to prevent `UnicodeEncodeError` with academic PDF ligatures or symbols:
  ```python
  if hasattr(sys.stdout, "reconfigure"):
      sys.stdout.reconfigure(encoding="utf-8", errors="replace")
  ```
* Use `os.path.dirname(os.path.abspath(__file__))` for all vector store, data, and cache paths rather than relative paths that break when scripts are executed from foreign working directories.

---

## 🧬 Rule 4: Causal Relation Schema Uniformity
* All extracted biomedical rules must strictly conform to the 8-property relational schema:
  - `metric_a`: Primary observed biomarker / lifestyle condition (e.g., `sleep duration`).
  - `change_a`: Direction (`increases`, `decreases`, `stays_stable`).
  - `metric_b`: Secondary physiological mediator (e.g., `heart rate`, `cortisol`).
  - `change_b`: Direction (`increases`, `decreases`, `stays_stable`).
  - `predicted_outcome`: Clinical hazard or routine indication (e.g., `acute hypertension`).
  - `confidence_rationale`: Scientific excerpt explaining biological mechanism.
  - `author_name` & `publication_date`: Academic attribution.
  - `source_pdf`: Origin PDF filename.

---

## 💾 Rule 5: Vector Store Cumulative Persistence
* The FAISS vector database stored in `local_persistent_vector_store/` must **never be deleted or overwritten** without explicit user instruction.
* Always use cumulative merging (`vector_store.add_texts`) when new papers are ingested so that previously indexed research rules are preserved.
* Keep the deduplication ledger in `paper_ledger.json` updated so no paper is ever processed or embedded twice.

---

## ⚡ Rule 6: Model Fallbacks & Deadlines
* External AI calls (Gemini, Colab) must always have explicit timeout deadlines (e.g., 15-30s) and multi-tier model fallbacks (`gemini-3.5-flash` -> `gemini-3-flash-preview` -> `gemini-3.8-flash` -> local deterministic synthesis) to guarantee endpoints never hang indefinitely.
