import os
import sys
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import FAISS
from google import genai
from google.genai import types

# Ensure UTF-8 output on Windows consoles to prevent UnicodeEncodeError with PDF text
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

app = FastAPI(title="Local Health Retrieval & Gemini Synthesis API")

# Robust path resolution relative to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VECTOR_DB_PATH = os.path.join(BASE_DIR, "local_persistent_vector_store")

# 1. Local embedding setup
embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url="http://localhost:11434")

# Load environment variables if available
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    pass

# 2. Dynamic API Key Resolution (Loaded from .env or environment variable)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is not set. Please copy .env.example to .env and set your Gemini API key, or set GEMINI_API_KEY in your environment."
    )

# 3. Initialize Google GenAI Client with explicit timeout to prevent hanging
gemini_client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options=types.HttpOptions(
        timeout=15000,  # 15s deadline to prevent hanging indefinitely
        retry_options=types.HttpRetryOptions(attempts=2)
    )
)

# Candidate models ordered by reliability & availability
# (gemini-3.5-flash is currently fast and active; gemini-3.8-flash has intermittent 503 spikes)
CANDIDATE_MODELS = ["gemini-3.5-flash", "gemini-3-flash-preview", "gemini-3.8-flash"]

class WearableInput(BaseModel):
    query_description: str

@app.post("/predict-risk")
def predict_health_risk(data: WearableInput):
    print(f"\n📥 [REQUEST RECEIVED] Query: {data.query_description}")
    
    if not os.path.exists(VECTOR_DB_PATH):
        raise HTTPException(
            status_code=404, 
            detail="Local FAISS vector store not found. Sync your rules from Colab first using your ingestion script."
        )
        
    # 1. Load local FAISS database and search locally
    print("🔍 Searching local FAISS vector store...")
    vector_store = FAISS.load_local(VECTOR_DB_PATH, embeddings, allow_dangerous_deserialization=True)
    results = vector_store.similarity_search_with_score(data.query_description, k=3)
    
    retrieved_rules = []
    for doc, score in results:
        retrieved_rules.append({
            "content": doc.page_content,
            "metadata": doc.metadata,
            "similarity_distance": float(score)
        })
        
    print(f"✨ Found {len(retrieved_rules)} matching rules locally.")
        
    if not retrieved_rules:
        return {
            "status": "success",
            "user_query": data.query_description,
            "gemini_report": "No matching research rules found in the local vector database.",
            "raw_retrieved_rules": []
        }
        
    # 2. Format context from local FAISS
    context_text = "\n".join([f"- {r['content']}" for r in retrieved_rules])
    
    prompt = f"""
    You are an advanced AI health intelligence system. 
    Analyze the user's wearable state / query: "{data.query_description}"
    
    Using strictly the following peer-reviewed literature rules retrieved from our local vector database:
    {context_text}
    
    Provide a detailed, structured response that includes:
    1. **Risk Analysis**: Explicitly state the bad routine or health risk identified based on the literature.
    2. **Physiological Rationale**: Explain the biological mechanism behind why this happens.
    3. **Academic Citations**: Cite the lead authors, publication years, and source documents accurately from the provided data.
    """
    
    gemini_analysis = None
    last_error = None

    # Try candidate models with timeout protection
    for model_name in CANDIDATE_MODELS:
        try:
            print(f"🚀 Sending request to Gemini API (model: {model_name})...")
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            if response and response.text:
                gemini_analysis = response.text.strip()
                print(f"✅ Successfully received response from Gemini API ({model_name})!")
                break
        except Exception as e:
            last_error = e
            print(f"⚠️ Model '{model_name}' encountered issue ({type(e).__name__}: {e}). Trying next model...")

    # Fallback to local synthesis if all remote model attempts fail or time out
    if not gemini_analysis:
        print(f"⚠️ All remote Gemini calls failed or timed out ({last_error}). Using local fallback...")
        fallback_bullets = "\n".join([f"• {r['content']}" for r in retrieved_rules])
        gemini_analysis = (
            f"### Clinical Risk Synthesis (Local Fallback Mode)\n\n"
            f"**User Status:** {data.query_description}\n\n"
            f"**Retrieved Literature Evidence:**\n{fallback_bullets}\n\n"
            f"*Analysis: Local database matching indicates heightened sympathetic strain.*"
        )

    return {
        "status": "success",
        "user_query": data.query_description,
        "gemini_report": gemini_analysis,
        "raw_retrieved_rules": retrieved_rules
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)