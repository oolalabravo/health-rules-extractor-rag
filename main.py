import os
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import FAISS

app = FastAPI(title="Persistent Local Health RAG API")

# PASTE YOUR COLAB NGROK URL HERE:
COLAB_API_URL = "https://eb1d-34-186-15-238.ngrok-free.app/extract-rules"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VECTOR_DB_PATH = os.path.join(BASE_DIR, "local_persistent_vector_store")

# Local Ollama embedding setup (runs completely on your laptop)
embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url="http://localhost:11434")

def upload_pdf_and_sync_rules(pdf_path: str):
    if not os.path.exists(pdf_path):
        print(f"❌ Local PDF file not found at: {pdf_path}")
        return

    print(f"📤 Uploading '{os.path.basename(pdf_path)}' to Google Colab for AI extraction...")
    try:
        with open(pdf_path, "rb") as f:
            files_payload = {"file": (os.path.basename(pdf_path), f, "application/pdf")}
            # 3-minute timeout so large PDFs don't hang indefinitely
            response = requests.post(COLAB_API_URL, files=files_payload, timeout=180)
            
        if response.status_code != 200:
            print(f"⚠️ Colab API error: {response.status_code} - {response.text}")
            return
            
        data = response.json()
        rules = data.get("all_rules", [])
        print(f"📥 Received rules from Colab. Total accumulated rules: {len(rules)}")
        
        if not rules:
            print("No rules returned from this PDF.")
            return

        texts, metas = [], []
        for r in rules:
            # Rich text representation embedding authors, dates, and rationales for accurate similarity search
            text_repr = (
                f"A {r.get('change_a', 'changes')} in {r.get('metric_a', 'unknown')} and "
                f"{r.get('change_b', 'changes')} in {r.get('metric_b', 'unknown')} "
                f"leads to {r.get('predicted_outcome', 'unknown')}. "
                f"Rationale: {r.get('confidence_rationale', 'N/A')} "
                f"(Study by {r.get('author_name', 'Unknown')} in {r.get('publication_date', 'Unknown')}, Source: {r.get('source_pdf', 'unknown')})"
            )
            texts.append(text_repr)
            
            # Store full rich metadata inside FAISS so your hackathon frontend can display beautiful citations
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

        # PERSISTENT LOCAL EMBEDDING & CUMULATIVE MERGING
        if os.path.exists(VECTOR_DB_PATH):
            print("🔗 Loading existing local FAISS database and appending new rules...")
            vector_store = FAISS.load_local(VECTOR_DB_PATH, embeddings, allow_dangerous_deserialization=True)
            vector_store.add_texts(texts=texts, metadatas=metas)
        else:
            print("✨ Creating brand new local FAISS database from scratch...")
            vector_store = FAISS.from_texts(texts=texts, embedding=embeddings, metadatas=metas)
            
        vector_store.save_local(VECTOR_DB_PATH)
        print(f"✅ Successfully embedded and persisted database with full citation metadata locally!")

    except requests.exceptions.Timeout:
        print("❌ Upload timed out. The PDF file might be too large.")
    except Exception as e:
        print(f"❌ Connection or processing error: {e}")

if __name__ == "__main__":
    # Raw string prefix 'r' prevents backslash warning issues on Windows paths
    local_pdf = r"Z:\Programs\VIKRANT HACKATHON\RULES EXTRACTOR\RESEARCH PAPERS\The association between sleep deprivation and arterial pressure variations_ a systematic literature review.pdf"
    
    if os.path.exists(local_pdf):
        upload_pdf_and_sync_rules(local_pdf)
    else:
        print(f"ℹ️ File path check failed. Verify path exists.")

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)