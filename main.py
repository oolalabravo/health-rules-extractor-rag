import os
import sys
import json
import time
import re
import warnings
import requests
from typing import Optional, Dict, Any, List, Literal, Callable
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import FAISS

# Suppress PDF font parser warnings
warnings.filterwarnings("ignore")

# Windows UTF-8 output configuration
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VECTOR_DB_PATH = os.path.join(BASE_DIR, "local_persistent_vector_store")

# Load .env if available
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    pass

# Import Colab Automator for zero-touch cell execution fallback
try:
    from colab_automator import ensure_colab_ready, check_colab_health
except ImportError:
    ensure_colab_ready = None
    check_colab_health = None

COLAB_API_URL = os.getenv("COLAB_API_URL", "")

app = FastAPI(title="Persistent Local Health RAG API")

# Local Ollama embedding setup (runs completely on your laptop)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url=OLLAMA_BASE_URL)

# High-speed Gemini Flash models with separate active quota pools
FAST_CANDIDATE_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-3-flash-preview"
]

class HealthRule(BaseModel):
    metric_a: str = Field(description="First metric, e.g., 'sleep duration'")
    change_a: Literal["increases", "decreases", "stays_stable"]
    metric_b: str = Field(description="Second metric, e.g., 'blood pressure'")
    change_b: Literal["increases", "decreases", "stays_stable"]
    relationship_type: Literal["positive_correlation", "inverse_correlation", "causal_risk"]
    predicted_outcome: str = Field(description="Health outcome or physiological risk indicated")
    confidence_rationale: str = Field(description="Brief clinical/biomedical rationale")

def save_rules_to_faiss(rules: List[Dict[str, Any]], pdf_name: str, max_retries: int = 3) -> int:
    """Safely adds extracted rules to the local persistent FAISS store with retry guards."""
    if not rules:
        return 0

    texts, metas = [], []
    for r in rules:
        text_repr = (
            f"A {r.get('change_a', 'changes')} in {r.get('metric_a', 'unknown')} and "
            f"{r.get('change_b', 'changes')} in {r.get('metric_b', 'unknown')} "
            f"leads to {r.get('predicted_outcome', 'unknown')}. "
            f"Rationale: {r.get('confidence_rationale', 'N/A')} "
            f"(Study by {r.get('author_name', 'Unknown')} in {r.get('publication_date', 'Unknown')}, Source: {pdf_name})"
        )
        texts.append(text_repr)
        metas.append({
            "metric_a": r.get("metric_a"),
            "change_a": r.get("change_a"),
            "metric_b": r.get("metric_b"),
            "change_b": r.get("change_b"),
            "predicted_outcome": r.get("predicted_outcome"),
            "author": r.get("author_name", "Unknown"),
            "publication_date": r.get("publication_date", "Unknown"),
            "rationale": r.get("confidence_rationale", "N/A"),
            "source_pdf": pdf_name
        })

    for attempt in range(1, max_retries + 1):
        try:
            if os.path.exists(VECTOR_DB_PATH):
                vector_store = FAISS.load_local(VECTOR_DB_PATH, embeddings, allow_dangerous_deserialization=True)
                vector_store.add_texts(texts=texts, metadatas=metas)
            else:
                vector_store = FAISS.from_texts(texts=texts, embedding=embeddings, metadatas=metas)

            vector_store.save_local(VECTOR_DB_PATH)
            return vector_store.index.ntotal
        except Exception as e:
            if attempt == max_retries:
                raise RuntimeError(f"FAISS indexing failed after {max_retries} attempts: {e}")
            time.sleep(1.0)
    return 0

def extract_rules_direct(
    pdf_path: str,
    progress_cb: Optional[Callable[[str, Optional[float]], None]] = None
) -> Dict[str, Any]:
    """
    Direct ultra-fast extraction (3-5s) using Google GenAI SDK.
    Bypasses Cloudflare tunnel timeouts and network uploads.
    """
    from pypdf import PdfReader
    from google import genai
    from google.genai import types

    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not gemini_key:
        raise ValueError("GEMINI_API_KEY not configured for direct extraction")

    t0 = time.time()
    filename = os.path.basename(pdf_path)

    if progress_cb:
        progress_cb("📖 Reading & parsing PDF document pages...", 0.2)

    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    pages_to_read = min(total_pages, 14)
    extracted_text = []

    for i in range(pages_to_read):
        page_content = reader.pages[i].extract_text() or ""
        if page_content:
            extracted_text.append(page_content)

    full_text = "\n\n".join(extracted_text)
    if len(full_text.strip()) < 100:
        raise ValueError("PDF content is empty or unreadable.")

    # Truncate to first 32,000 characters (covers title, abstract, methodology, results)
    context_text = full_text[:32000]

    client = genai.Client(
        api_key=gemini_key,
        http_options=types.HttpOptions(
            timeout=25000,
            retry_options=types.HttpRetryOptions(attempts=2)
        )
    )

    prompt = f"""
Analyze the following peer-reviewed biomedical research paper and extract all conditional/causal health rules.
Document: {filename} (Total pages: {total_pages})

For every identified relation, extract:
- metric_a, change_a, metric_b, change_b, relationship_type, predicted_outcome, confidence_rationale.

Paper Content Excerpt:
{context_text}
"""

    last_err = None
    parsed_rules = None

    for model_name in FAST_CANDIDATE_MODELS:
        if progress_cb:
            progress_cb(f"🧠 Querying high-speed model ({model_name})...", 0.6)
        try:
            res = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=list[HealthRule]
                )
            )
            parsed_rules = json.loads(res.text)
            break
        except Exception as e:
            last_err = e
            continue

    if parsed_rules is None:
        raise RuntimeError(f"All Gemini models failed: {last_err}")

    # Standardize rule attributes
    standardized_rules = []
    for r in parsed_rules:
        r["author_name"] = "Peer-Reviewed Author"
        r["publication_date"] = "Recent"
        r["source_pdf"] = filename
        standardized_rules.append(r)

    if progress_cb:
        progress_cb("💾 Persisting rules into local FAISS vector store...", 0.85)

    total_vectors = save_rules_to_faiss(standardized_rules, filename)
    elapsed = round(time.time() - t0, 2)

    return {
        "status": "success",
        "filename": filename,
        "new_rules_extracted": len(standardized_rules),
        "total_vectors": total_vectors,
        "rules": standardized_rules,
        "extraction_time_seconds": elapsed,
        "engine": "direct-gemini-fast"
    }

def upload_pdf_and_sync_rules(
    pdf_path: str,
    colab_url: Optional[str] = None,
    prefer_direct: bool = True,
    progress_cb: Optional[Callable[[str, Optional[float]], None]] = None
) -> Dict[str, Any]:
    """
    Unified extraction pipeline:
    1. TIER 1: Ultra-fast local Gemini Flash extraction (<5 seconds, zero tunnel latency).
    2. TIER 2: Colab extraction server fallback (with HTML error sanitization).
    """
    if not os.path.exists(pdf_path):
        err = f"Local PDF file not found at: {pdf_path}"
        print(f"❌ {err}")
        return {"status": "error", "message": err, "rules_added": 0}

    # TIER 1: Ultra-fast local Gemini engine
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if prefer_direct and gemini_key:
        try:
            return extract_rules_direct(pdf_path, progress_cb=progress_cb)
        except Exception as de:
            if progress_cb:
                progress_cb(f"⚠️ Direct fast-path notice ({de}). Falling back to Colab...", None)

    # TIER 2: Colab Server Fallback
    target_url = colab_url or os.getenv("COLAB_API_URL") or COLAB_API_URL
    if check_colab_health and (not target_url or not check_colab_health(target_url)):
        if progress_cb:
            progress_cb("🔍 Colab endpoint offline. Auto-triggering Colab runtime...", None)
        if ensure_colab_ready:
            try:
                target_url = ensure_colab_ready()
            except Exception as e:
                pass

    if progress_cb:
        progress_cb(f"📤 Uploading PDF to Colab ({target_url})...", 0.4)

    headers = {}
    if gemini_key:
        headers["x-gemini-api-key"] = gemini_key

    try:
        with open(pdf_path, "rb") as f:
            files_payload = {"file": (os.path.basename(pdf_path), f, "application/pdf")}
            response = requests.post(target_url, files=files_payload, headers=headers, timeout=120)

        if response.status_code != 200:
            if "<!DOCTYPE" in response.text or "<html" in response.text:
                err = f"Colab Gateway Timeout / Error (HTTP {response.status_code})"
            else:
                err = f"Colab API error ({response.status_code}): {response.text[:200]}"
            print(f"⚠️ {err}")
            return {"status": "error", "message": err, "rules_added": 0}

        data = response.json()
        rules = data.get("all_rules", [])
        new_count = data.get("new_rules_extracted", len(rules))

        if not rules:
            return {"status": "success", "message": "No rules found in document", "rules_added": 0}

        total_vectors = save_rules_to_faiss(rules, os.path.basename(pdf_path))
        return {
            "status": "success",
            "message": "Rules successfully extracted and indexed",
            "rules_added": new_count,
            "total_vectors": total_vectors,
            "rules": rules,
            "engine": "colab-server"
        }

    except requests.exceptions.Timeout:
        err = "Upload timed out (Colab server took too long to respond)."
        print(f"❌ {err}")
        return {"status": "error", "message": err, "rules_added": 0}
    except Exception as e:
        err = f"Connection or processing error: {e}"
        print(f"❌ {err}")
        return {"status": "error", "message": err, "rules_added": 0}

if __name__ == "__main__":
    local_pdf = os.path.join(
        BASE_DIR,
        "RESEARCH PAPERS",
        "The association between sleep deprivation and arterial pressure variations_ a systematic literature review.pdf"
    )
    if os.path.exists(local_pdf):
        def test_cb(msg, pct):
            print(f"  {msg} ({int(pct*100) if pct else 0}%)")
        res = upload_pdf_and_sync_rules(local_pdf, progress_cb=test_cb)
        print("Test Result:", res)
    else:
        print(f"ℹ️ Sample PDF not found at: {local_pdf}")

class WearableInput(BaseModel):
    query_description: str

@app.post("/predict-risk")
def predict_health_risk(data: WearableInput):
    if not os.path.exists(VECTOR_DB_PATH):
        raise HTTPException(status_code=404, detail="Local vector store not initialized yet. Upload a PDF first.")

    vector_store = FAISS.load_local(VECTOR_DB_PATH, embeddings, allow_dangerous_deserialization=True)
    results = vector_store.similarity_search_with_score(data.query_description, k=2)

    predictions = [
        {
            "rule": doc.page_content,
            "metadata": doc.metadata,
            "similarity_distance": float(score)
        }
        for doc, score in results
    ]
    return {"status": "success", "predictions": predictions}
