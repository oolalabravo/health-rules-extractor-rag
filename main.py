import os
import sys
import requests
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import FAISS

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

# Import Colab Automator for zero-touch cell execution
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

def upload_pdf_and_sync_rules(pdf_path: str, colab_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Uploads a local biomedical PDF to the Colab extraction server, retrieves
    the extracted causal relationships, and cumulatively indexes them into FAISS.
    """
    if not os.path.exists(pdf_path):
        err = f"Local PDF file not found at: {pdf_path}"
        print(f"❌ {err}")
        return {"status": "error", "message": err, "rules_added": 0}

    target_url = colab_url or os.getenv("COLAB_API_URL") or COLAB_API_URL
    if check_colab_health and (not target_url or not check_colab_health(target_url)):
        print("🔍 Colab endpoint is not active. Auto-discovering endpoint...")
        if ensure_colab_ready:
            try:
                target_url = ensure_colab_ready()
            except Exception as e:
                print(f"⚠️ Auto-discovery notice: {e}")

    print(f"\n📤 Uploading '{os.path.basename(pdf_path)}' to Colab ({target_url})...")

    headers = {}
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key:
        headers["x-gemini-api-key"] = gemini_key

    try:
        with open(pdf_path, "rb") as f:
            files_payload = {"file": (os.path.basename(pdf_path), f, "application/pdf")}
            # 180s timeout so large PDFs don't hang indefinitely
            response = requests.post(target_url, files=files_payload, headers=headers, timeout=180)

        if response.status_code != 200:
            err = f"Colab API error: {response.status_code} - {response.text}"
            print(f"⚠️ {err}")
            return {"status": "error", "message": err, "rules_added": 0}

        data = response.json()
        rules = data.get("all_rules", [])
        new_count = data.get("new_rules_extracted", len(rules))
        print(f"📥 Received rules from Colab. New rules: {new_count} | Total accumulated: {len(rules)}")

        if not rules:
            print("ℹ️ No rules returned from this PDF.")
            return {"status": "success", "message": "No rules found in document", "rules_added": 0}

        texts, metas = [], []
        for r in rules:
            text_repr = (
                f"A {r.get('change_a', 'changes')} in {r.get('metric_a', 'unknown')} and "
                f"{r.get('change_b', 'changes')} in {r.get('metric_b', 'unknown')} "
                f"leads to {r.get('predicted_outcome', 'unknown')}. "
                f"Rationale: {r.get('confidence_rationale', 'N/A')} "
                f"(Study by {r.get('author_name', 'Unknown')} in {r.get('publication_date', 'Unknown')}, Source: {r.get('source_pdf', 'unknown')})"
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
                "source_pdf": r.get("source_pdf", "unknown")
            })

        # Cumulative FAISS persistence
        if os.path.exists(VECTOR_DB_PATH):
            print("🔗 Loading existing local FAISS database and appending new rules...")
            vector_store = FAISS.load_local(VECTOR_DB_PATH, embeddings, allow_dangerous_deserialization=True)
            vector_store.add_texts(texts=texts, metadatas=metas)
        else:
            print("✨ Creating brand new local FAISS database from scratch...")
            vector_store = FAISS.from_texts(texts=texts, embedding=embeddings, metadatas=metas)

        vector_store.save_local(VECTOR_DB_PATH)
        print(f"✅ Successfully embedded and persisted database ({vector_store.index.ntotal} total vectors)!")
        return {
            "status": "success",
            "message": "Rules successfully extracted and indexed",
            "rules_added": new_count,
            "total_vectors": vector_store.index.ntotal,
            "rules": rules
        }

    except requests.exceptions.Timeout:
        err = "Upload timed out. Colab server took too long to process."
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
        upload_pdf_and_sync_rules(local_pdf)
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
