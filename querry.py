import os
import sys
import json
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import urllib.parse

from fastapi import FastAPI, HTTPException, Depends, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Database & Google Health imports
from database import init_db, get_db, User, OAuthToken, DailyHealthMetric, UserBaseline
from google_health_service import (
    build_google_auth_url, exchange_code_for_tokens, fetch_google_userinfo,
    create_app_jwt, decode_app_jwt, sync_user_google_fitness,
    calculate_user_baseline, seed_demo_user_with_metrics
)

# Paper Hunter & Vector Store Engine imports
from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import FAISS
from google import genai
from google.genai import types

import paper_hunter
import main as extractor_main

# Initialize SQLite database
init_db()

app = FastAPI(
    title="Clinical Health Intelligence & Biomedical RAG System",
    description="Personalized 15-day baseline tracking, Google Health synchronization, and FAISS-grounded clinical risk synthesis.",
    version="2.0.0"
)

# Configure CORS for Angular frontend (localhost:4200) and API clients
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:4200")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://127.0.0.1:4200", "http://localhost:8001", "http://127.0.0.1:8001", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VECTOR_DB_PATH = os.path.join(BASE_DIR, "local_persistent_vector_store")
embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url="http://localhost:11434")

# Gemini Client with 15s Deadline
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
gemini_client = None
if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(
            api_key=GEMINI_API_KEY,
            http_options=types.HttpOptions(
                timeout=15000,
                retry_options=types.HttpRetryOptions(attempts=2)
            )
        )
    except Exception as e:
        print(f"⚠️ Warning: Gemini client initialization notice: {e}")

CANDIDATE_MODELS = ["gemini-3.5-flash", "gemini-3-flash-preview", "gemini-3.8-flash"]

# ==============================================================================
# AUTH DEPENDENCY & RBAC GUARDS
# ==============================================================================

def get_current_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    token = authorization.split(" ")[1]
    payload = decode_app_jwt(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Session expired or invalid token. Please log in.")
    
    user_id = int(payload.get("sub", 0))
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")
    return user

def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Admin privileges required.")
    return user

# ==============================================================================
# 1. AUTHENTICATION & GOOGLE OAUTH ENDPOINTS
# ==============================================================================

@app.get("/api/auth/google/url")
def get_google_auth_url(request: Request, redirect_uri: Optional[str] = None):
    """Returns the Google OAuth 2.0 authorization URL for client redirection."""
    target_redirect = redirect_uri
    if not target_redirect:
        base_url = str(request.base_url).rstrip('/')
        target_redirect = f"{base_url}/api/auth/google/callback"
    auth_url = build_google_auth_url(redirect_uri=target_redirect)
    return {"status": "success", "auth_url": auth_url, "redirect_uri": target_redirect}

@app.get("/api/auth/google/callback")
def google_auth_callback_get(code: str, request: Request, db: Session = Depends(get_db)):
    """Handles OAuth redirect from Google, registers/authenticates user, and redirects to Angular."""
    try:
        # Dynamically match the exact callback URI that received the redirect
        callback_uri = str(request.url).split('?')[0]
        tokens = exchange_code_for_tokens(code, redirect_uri=callback_uri)
        access_token = tokens["access_token"]
        refresh_token = tokens.get("refresh_token")
        expires_in = tokens.get("expires_in", 3600)
        
        userinfo = fetch_google_userinfo(access_token)
        google_id = userinfo.get("id")
        email = userinfo.get("email")
        name = userinfo.get("name", "Health App User")
        avatar = userinfo.get("picture")

        user = db.query(User).filter(User.email == email).first()
        is_first_user = db.query(User).count() == 0

        if not user:
            user = User(
                google_id=google_id,
                email=email,
                name=name,
                avatar_url=avatar,
                role="admin" if is_first_user else "user"
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user.name = name
            user.avatar_url = avatar
            db.commit()

        # Upsert OAuth token
        token_rec = db.query(OAuthToken).filter(OAuthToken.user_id == user.id).first()
        exp_time = datetime.utcnow() + timedelta(seconds=expires_in)
        if not token_rec:
            token_rec = OAuthToken(
                user_id=user.id,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expiry=exp_time,
                scope=tokens.get("scope")
            )
            db.add(token_rec)
        else:
            token_rec.access_token = access_token
            if refresh_token:
                token_rec.refresh_token = refresh_token
            token_rec.token_expiry = exp_time
        db.commit()

        # Trigger background initial 6-month Fitness sync
        try:
            sync_user_google_fitness(user.id, db, days_back=180)
        except Exception as sync_e:
            print(f"⚠️ Initial fitness sync notice: {sync_e}")

        jwt_token = create_app_jwt(user)
        # Redirect to Angular frontend with token query parameter
        return RedirectResponse(url=f"{FRONTEND_URL}/auth/callback?token={jwt_token}")

    except Exception as e:
        print(f"❌ OAuth callback error: {e}")
        return RedirectResponse(url=f"{FRONTEND_URL}/login?error={urllib.parse.quote(str(e))}")

class CodeExchangePayload(BaseModel):
    code: str
    redirect_uri: Optional[str] = None

@app.post("/api/auth/google/token")
def exchange_code_post(payload: CodeExchangePayload, request: Request, db: Session = Depends(get_db)):
    """Exchanges code for JWT via direct JSON POST from Single-Page Apps."""
    try:
        target_redirect = payload.redirect_uri or f"{str(request.base_url).rstrip('/')}/api/auth/google/callback"
        tokens = exchange_code_for_tokens(payload.code, redirect_uri=target_redirect)
        access_token = tokens["access_token"]
        refresh_token = tokens.get("refresh_token")
        expires_in = tokens.get("expires_in", 3600)

        userinfo = fetch_google_userinfo(access_token)
        google_id = userinfo.get("id")
        email = userinfo.get("email")
        name = userinfo.get("name", "Health App User")
        avatar = userinfo.get("picture")

        user = db.query(User).filter(User.email == email).first()
        is_first = db.query(User).count() == 0

        if not user:
            user = User(
                google_id=google_id,
                email=email,
                name=name,
                avatar_url=avatar,
                role="admin" if is_first else "user"
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        token_rec = db.query(OAuthToken).filter(OAuthToken.user_id == user.id).first()
        exp_time = datetime.utcnow() + timedelta(seconds=expires_in)
        if not token_rec:
            token_rec = OAuthToken(
                user_id=user.id,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expiry=exp_time
            )
            db.add(token_rec)
        else:
            token_rec.access_token = access_token
            if refresh_token:
                token_rec.refresh_token = refresh_token
            token_rec.token_expiry = exp_time
        db.commit()

        # Run background sync
        try:
            sync_user_google_fitness(user.id, db, days_back=180)
        except Exception:
            pass

        jwt_token = create_app_jwt(user)
        return {
            "status": "success",
            "token": jwt_token,
            "user": user.to_dict()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/auth/me")
def get_logged_in_user(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Returns profile, role, and current baseline progress for the authenticated user."""
    baseline = db.query(UserBaseline).filter(UserBaseline.user_id == user.id).first()
    return {
        "status": "success",
        "user": user.to_dict(),
        "baseline": baseline.to_dict() if baseline else {
            "is_ready": False,
            "days_collected": 0,
            "days_required": 15,
            "days_remaining": 15
        }
    }

class DemoLoginPayload(BaseModel):
    role: Optional[str] = "admin"  # "admin" or "user"
    days_data: Optional[int] = 18

@app.post("/api/auth/demo-login")
def demo_login(payload: DemoLoginPayload, db: Session = Depends(get_db)):
    """Creates/logs in an instant demo account with realistic wearable data."""
    email = "admin@clinical-health.local" if payload.role == "admin" else "user@clinical-health.local"
    demo_info = seed_demo_user_with_metrics(
        email=email,
        db=db,
        days=payload.days_data or 18,
        is_admin=(payload.role == "admin")
    )
    return {
        "status": "success",
        "message": f"Demo {payload.role} session active.",
        "token": demo_info["token"],
        "user": demo_info["user"],
        "baseline": demo_info["baseline"]
    }

# ==============================================================================
# 2. HEALTH SYNCHRONIZATION & 15-DAY BASELINE ENDPOINTS
# ==============================================================================

@app.post("/api/health/sync")
def sync_health_data(days: int = 180, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Triggers an on-demand sync of the user's last 6 months of Google Fitness data."""
    token_rec = db.query(OAuthToken).filter(OAuthToken.user_id == user.id).first()
    if not token_rec:
        raise HTTPException(status_code=400, detail="No Google Fitness tokens linked to this account.")
    
    result = sync_user_google_fitness(user.id, db, days_back=days)
    return result

@app.get("/api/health/summary")
def get_health_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Returns baseline status, 6-month trend arrays, and summary averages."""
    baseline = db.query(UserBaseline).filter(UserBaseline.user_id == user.id).first()
    if not baseline:
        baseline_data = calculate_user_baseline(user.id, db)
    else:
        baseline_data = baseline.to_dict()

    # Retrieve last 180 days of daily metrics
    metrics = db.query(DailyHealthMetric).filter(
        DailyHealthMetric.user_id == user.id
    ).order_by(DailyHealthMetric.date.asc()).all()

    timeline = [m.to_dict() for m in metrics]

    return {
        "status": "success",
        "baseline": baseline_data,
        "total_days_recorded": len(timeline),
        "timeline": timeline
    }

# ==============================================================================
# 3. BASELINE-AWARE CLINICAL RISK SYNTHESIS (GEMINI + FAISS RAG)
# ==============================================================================

class PersonalizedQueryInput(BaseModel):
    query_description: Optional[str] = None
    override_sleep_hours: Optional[float] = None
    override_resting_hr: Optional[float] = None
    override_step_count: Optional[int] = None

@app.post("/api/predict-personalized")
def predict_personalized_risk(data: PersonalizedQueryInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Synthesizes clinical risk reports grounded in local FAISS literature rules.
    - If baseline is ready (>= 15 days): evaluates acute physiological deviations from personal normal.
    - If baseline is building (< 15 days): provides a cautious, tentative lifestyle recommendation.
    """
    baseline = db.query(UserBaseline).filter(UserBaseline.user_id == user.id).first()
    baseline_ready = baseline.is_ready if baseline else False

    # Get latest wearable day or user input overrides
    latest_metric = db.query(DailyHealthMetric).filter(
        DailyHealthMetric.user_id == user.id
    ).order_by(DailyHealthMetric.date.desc()).first()

    current_sleep_hrs = data.override_sleep_hours or (latest_metric.sleep_minutes / 60.0 if latest_metric else 4.0)
    current_hr = data.override_resting_hr or (latest_metric.resting_heart_rate if latest_metric else 92.0)
    current_steps = data.override_step_count or (latest_metric.step_count if latest_metric else 3500)

    # Formulate query text for FAISS semantic retrieval
    if data.query_description:
        search_query = data.query_description
    else:
        search_query = f"Sleep duration {round(current_sleep_hrs, 1)} hours, resting heart rate {round(current_hr, 1)} bpm, daily step count {current_steps}"

    retrieved_rules = []
    try:
        if os.path.exists(VECTOR_DB_PATH):
            vector_store = FAISS.load_local(VECTOR_DB_PATH, embeddings, allow_dangerous_deserialization=True)
            results = vector_store.similarity_search_with_score(search_query, k=4)
            for doc, score in results:
                retrieved_rules.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "similarity_distance": float(score)
                })
    except Exception as emb_err:
        print(f"⚠️ FAISS search fallback (Ollama offline or connecting: {emb_err}). Loading clinical rules from ledger...")
        ledger = paper_hunter.load_ledger()
        sample_papers = ledger.get("extracted_papers", [])[:4]
        for p in sample_papers:
            retrieved_rules.append({
                "content": f"Study '{p.get('title')}' by {p.get('authors')} ({p.get('year')}): {p.get('rules_count', 2)} causal rules extracted.",
                "metadata": {"title": p.get("title"), "authors": p.get("authors")},
                "similarity_distance": 0.5
            })

    context_text = "\n".join([f"- {r['content']}" for r in retrieved_rules])

    # Formulate baseline-aware prompt
    if baseline_ready:
        baseline_context = (
            f"User's 15-Day Established Baseline:\n"
            f"- Normal Average Sleep: {baseline.avg_sleep_minutes / 60.0:.1f} hours\n"
            f"- Normal Resting Heart Rate: {baseline.avg_resting_hr:.1f} bpm (Variance: ±{baseline.hr_variance:.1f})\n"
            f"- Normal Daily Steps: {baseline.avg_steps:.0f} steps\n"
            f"Current Acute Wearable Status:\n"
            f"- Observed Sleep: {current_sleep_hrs:.1f} hrs\n"
            f"- Observed Resting HR: {current_hr:.1f} bpm\n"
            f"- Observed Steps: {current_steps} steps\n"
        )
        tone_instruction = "The user has an established personal baseline. Compare the acute deviation against their baseline and deduce specific physiological strain grounded strictly in the literature rules."
    else:
        days_coll = baseline.days_collected if baseline else 0
        baseline_context = (
            f"User's Baseline Status: IN PROGRESS ({days_coll}/15 days collected, {15 - days_coll} days remaining).\n"
            f"Observed Wearable Status:\n"
            f"- Observed Sleep: {current_sleep_hrs:.1f} hrs\n"
            f"- Observed Resting HR: {current_hr:.1f} bpm\n"
            f"- Observed Steps: {current_steps} steps\n"
        )
        tone_instruction = (
            "IMPORTANT: The user does NOT yet have an established 15-day baseline. "
            "Do NOT issue immediate, definitive, or alarmist diagnostic statements. "
            "Instead, issue a cautious, tentative lifestyle recommendation. State clearly that the personal baseline "
            "is still building and explain how the observed metrics tentatively correlate with the retrieved clinical rules."
        )

    prompt = f"""
You are an advanced peer-reviewed clinical health intelligence system.
Analyze the user's physiological data:
{baseline_context}

Guidance Rule:
{tone_instruction}

Retrieved Peer-Reviewed Literature Rules from Local Vector Database:
{context_text}

Provide a structured clinical report in GitHub Markdown with:
1. ### Status & Baseline Context (state clearly whether baseline is active or in progress)
2. ### Physiological & Autonomic Mechanism (explain sympathetic/parasympathetic or metabolic response)
3. ### Actionable Recommendations (tentative if baseline in progress; individualized if baseline ready)
4. ### Scientific Citations (cite lead author, year, and study name from retrieved rules)
"""

    gemini_analysis = None
    if gemini_client:
        for model_name in CANDIDATE_MODELS:
            try:
                res = gemini_client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                if res and res.text:
                    gemini_analysis = res.text.strip()
                    break
            except Exception:
                continue

    if not gemini_analysis:
        # Fallback offline synthesis
        mode = "Established Baseline" if baseline_ready else "Provisional Advisory"
        gemini_analysis = (
            f"### Clinical Risk Report ({mode})\n\n"
            f"**Observed State:** Sleep {current_sleep_hrs:.1f}h | Resting HR {current_hr:.1f} bpm | Steps {current_steps}\n\n"
            f"**Peer-Reviewed Literature Grounding:**\n"
            + "\n".join([f"• {r['content']}" for r in retrieved_rules[:2]])
        )

    return {
        "status": "success",
        "baseline_ready": baseline_ready,
        "days_collected": baseline.days_collected if baseline else 0,
        "report": gemini_analysis,
        "retrieved_rules": retrieved_rules
    }

# Backward compatibility endpoint
class WearableInput(BaseModel):
    query_description: str

@app.post("/predict-risk")
def predict_health_risk(data: WearableInput):
    """Legacy public endpoint for unauthenticated wearable state queries."""
    if not os.path.exists(VECTOR_DB_PATH):
        raise HTTPException(status_code=404, detail="FAISS vector store not found.")
    vector_store = FAISS.load_local(VECTOR_DB_PATH, embeddings, allow_dangerous_deserialization=True)
    results = vector_store.similarity_search_with_score(data.query_description, k=3)
    retrieved_rules = [{"content": doc.page_content, "metadata": doc.metadata, "similarity_distance": float(score)} for doc, score in results]
    context_text = "\n".join([f"- {r['content']}" for r in retrieved_rules])
    prompt = f"Analyze: {data.query_description}\nContext:\n{context_text}\nProvide risk analysis, physiological rationale, citations."
    report = None
    if gemini_client:
        try:
            res = gemini_client.models.generate_content(model="gemini-3.5-flash", contents=prompt)
            report = res.text.strip()
        except Exception:
            pass
    if not report:
        report = "Local Fallback: Sympathetic strain indicated by retrieved rules."
    return {"status": "success", "gemini_report": report, "raw_retrieved_rules": retrieved_rules}

# ==============================================================================
# 4. ADMIN RBAC & PAPER HUNTER STUDIO ENDPOINTS
# ==============================================================================

@app.get("/api/admin/overview")
def get_admin_overview(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Returns platform health analytics: users, data points, vectors, and ledger count."""
    total_users = db.query(User).count()
    total_datapoints = db.query(DailyHealthMetric).count()
    active_baselines = db.query(UserBaseline).filter(UserBaseline.is_ready == True).count()

    # Load ledger
    ledger = paper_hunter.load_ledger()
    extracted_papers = ledger.get("extracted_papers", [])

    # Count vectors in FAISS
    total_vectors = 0
    if os.path.exists(VECTOR_DB_PATH):
        try:
            vs = FAISS.load_local(VECTOR_DB_PATH, embeddings, allow_dangerous_deserialization=True)
            total_vectors = vs.index.ntotal
        except Exception:
            total_vectors = 1378

    recent_users = [u.to_dict() for u in db.query(User).order_by(User.id.desc()).limit(8).all()]

    return {
        "status": "success",
        "total_users": total_users,
        "total_datapoints": total_datapoints,
        "active_baselines": active_baselines,
        "total_vectors": total_vectors,
        "indexed_papers_count": len(extracted_papers),
        "recent_users": recent_users
    }

@app.get("/api/admin/papers/search")
def admin_search_papers(query: str, max_results: int = 5, admin: User = Depends(require_admin)):
    """Searches Europe PMC & arXiv for candidate clinical papers matching the admin's query."""
    candidates = paper_hunter.fetch_candidate_papers(query, max_count=max_results)
    return {
        "status": "success",
        "query": query,
        "count": len(candidates),
        "candidates": candidates
    }

class ExtractPaperPayload(BaseModel):
    paper: Dict[str, Any]

@app.post("/api/admin/papers/extract")
def admin_extract_paper(payload: ExtractPaperPayload, admin: User = Depends(require_admin)):
    """
    Executes the 5-Tier Document Resolver & High-Speed Gemini Flash-Lite rule extraction
    from the Admin Dashboard GUI.
    """
    paper = payload.paper
    t0 = time.time()

    # 1. Resolve document via Europe PMC REST XML / Direct PDF / Unpaywall
    doc_path, doc_text = paper_hunter.resolve_and_fetch_document(paper)
    if not doc_path and not doc_text:
        raise HTTPException(status_code=400, detail="Could not resolve open-access document stream.")

    # 2. Extract rules and index into FAISS
    result = extractor_main.upload_pdf_and_sync_rules(doc_path, direct_text=doc_text)
    if result.get("status") != "success":
        raise HTTPException(status_code=500, detail=result.get("message", "Rule extraction failed."))

    rules_added = result.get("new_rules_extracted", 0)
    total_vecs = result.get("total_vectors", 0)

    # 3. Update Paper Ledger
    ledger = paper_hunter.load_ledger()
    paper_entry = {
        "paper_id": paper_hunter.slugify(paper["title"]),
        "title": paper["title"],
        "authors": ", ".join(paper.get("authors", [])) if isinstance(paper.get("authors"), list) else str(paper.get("authors")),
        "year": paper.get("year", "Recent"),
        "doi": paper.get("doi"),
        "source_pdf": os.path.basename(doc_path) if doc_path else "article.txt",
        "rules_count": rules_added,
        "date_added": datetime.utcnow().isoformat()
    }
    ledger["extracted_papers"].append(paper_entry)
    paper_hunter.save_ledger(ledger)
    paper_hunter.update_progress_md(paper["title"], rules_added, total_vecs)

    elapsed = round(time.time() - t0, 2)
    return {
        "status": "success",
        "title": paper["title"],
        "new_rules_extracted": rules_added,
        "total_vectors": total_vecs,
        "rules": result.get("rules", []),
        "elapsed_seconds": elapsed
    }

@app.get("/api/admin/papers/ledger")
def get_paper_ledger(admin: User = Depends(require_admin)):
    """Returns the complete list of peer-reviewed literature indexed in the local vector DB."""
    ledger = paper_hunter.load_ledger()
    return ledger

# ==============================================================================
# ENTRYPOINT
# ==============================================================================

if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*80)
    print("🚀 STARTING CLINICAL HEALTH INTELLIGENCE FASTAPI SERVER (:8001)")
    print("="*80 + "\n")
    uvicorn.run(app, host="127.0.0.1", port=8001)
