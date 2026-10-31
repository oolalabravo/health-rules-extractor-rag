import os
import sys
import json
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
import urllib.parse
import requests
import jwt
from dotenv import load_dotenv
from sqlalchemy.orm import Session

# Windows UTF-8 console output guard
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

# OAuth & Security Config
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8001/api/auth/google/callback")
JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_biomedical_health_jwt_key_2026_clinical")
JWT_ALGORITHM = "HS256"

# Required Google Fitness & Profile Scopes
FITNESS_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/fitness.activity.read",
    "https://www.googleapis.com/auth/fitness.body.read",
    "https://www.googleapis.com/auth/fitness.heart_rate.read",
    "https://www.googleapis.com/auth/fitness.sleep.read"
]

# Database imports
from database import User, OAuthToken, DailyHealthMetric, UserBaseline

# ==============================================================================
# 1. AUTHENTICATION & TOKEN SERVICES
# ==============================================================================

def build_google_auth_url(state: Optional[str] = None, redirect_uri: Optional[str] = None) -> str:
    """Generates the Google OAuth 2.0 authorization URL requesting fitness and identity scopes."""
    target_redirect = redirect_uri or GOOGLE_REDIRECT_URI
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": target_redirect,
        "response_type": "code",
        "scope": " ".join(FITNESS_SCOPES),
        "access_type": "offline",      # Guarantees refresh token delivery
        "prompt": "consent",           # Forces consent screen so refresh token is re-issued
        "include_granted_scopes": "true",
    }
    if state:
        params["state"] = state
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"

def exchange_code_for_tokens(code: str, redirect_uri: Optional[str] = None) -> Dict[str, Any]:
    """Exchanges authorization code for Google access and refresh tokens."""
    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri or GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code"
    }
    resp = requests.post(token_url, data=payload, timeout=15)
    if not resp.ok:
        raise RuntimeError(f"Google token exchange failed ({resp.status_code}): {resp.text}")
    return resp.json()

def fetch_google_userinfo(access_token: str) -> Dict[str, Any]:
    """Retrieves Google profile and email using the access token."""
    userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(userinfo_url, headers=headers, timeout=10)
    if not resp.ok:
        raise RuntimeError(f"Failed to fetch Google userinfo ({resp.status_code}): {resp.text}")
    return resp.json()

def get_valid_access_token(user_id: int, db: Session) -> str:
    """Checks token expiration and auto-refreshes token via Google OAuth refresh token if necessary."""
    token_rec = db.query(OAuthToken).filter(OAuthToken.user_id == user_id).first()
    if not token_rec:
        raise RuntimeError(f"No OAuth token found for user_id={user_id}")

    # Check if token expires within the next 3 minutes
    now = datetime.utcnow()
    if token_rec.token_expiry and token_rec.token_expiry > (now + timedelta(minutes=3)):
        return token_rec.access_token

    if not token_rec.refresh_token:
        # Fall back to existing token if no refresh token exists
        return token_rec.access_token

    # Refresh the token
    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": token_rec.refresh_token,
        "grant_type": "refresh_token"
    }
    resp = requests.post(token_url, data=payload, timeout=15)
    if not resp.ok:
        # Return existing token if refresh call fails temporarily
        return token_rec.access_token

    data = resp.json()
    new_access_token = data.get("access_token")
    expires_in = data.get("expires_in", 3600)

    token_rec.access_token = new_access_token
    token_rec.token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
    db.commit()
    return new_access_token

def create_app_jwt(user: User) -> str:
    """Generates signed JWT token for application RBAC session."""
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "exp": datetime.utcnow() + timedelta(days=30)  # 30-day session
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_app_jwt(token: str) -> Optional[Dict[str, Any]]:
    """Validates and decodes the application JWT token."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception:
        return None

# ==============================================================================
# 2. GOOGLE FITNESS 6-MONTH AGGREGATE INGESTION
# ==============================================================================

def sync_user_google_fitness(user_id: int, db: Session, days_back: int = 180) -> Dict[str, Any]:
    """
    Pulls up to 6 months (180 days) of daily physiological data from Google Fitness API
    using 30-day window chunking to strictly adhere to Google API duration limits:
    - Steps: com.google.step_count.delta
    - Sleep: com.google.sleep.segment
    - Heart rate: com.google.heart_rate.bpm
    Stores aggregated daily metrics into SQLite and triggers baseline recalculation.
    """
    access_token = get_valid_access_token(user_id, db)

    now = datetime.utcnow()
    end_dt = datetime(now.year, now.month, now.day, 23, 59, 59)
    total_start_dt = end_dt - timedelta(days=days_back)

    # Google Fitness dataset:aggregate restricts query duration to max 30-31 days.
    # We partition the 180-day range into 30-day sequential windows.
    CHUNK_SIZE_DAYS = 30
    windows: List[Tuple[datetime, datetime]] = []
    curr_start = total_start_dt
    while curr_start < end_dt:
        curr_end = min(curr_start + timedelta(days=CHUNK_SIZE_DAYS), end_dt)
        windows.append((curr_start, curr_end))
        curr_start = curr_end

    aggregate_url = "https://fitness.googleapis.com/fitness/v1/users/me/dataset:aggregate"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    total_buckets_processed = 0
    records_saved = 0

    print(f"🔄 Slicing {days_back}-day sync into {len(windows)} safe 30-day Google Fitness windows...")

    for w_idx, (w_start, w_end) in enumerate(windows, start=1):
        start_ms = int(w_start.timestamp() * 1000)
        end_ms = int(w_end.timestamp() * 1000)

        request_body = {
            "aggregateBy": [
                {
                    "dataTypeName": "com.google.step_count.delta",
                    "dataSourceId": "derived:com.google.step_count.delta:com.google.android.gms:estimated_steps"
                },
                {
                    "dataTypeName": "com.google.sleep.segment"
                },
                {
                    "dataTypeName": "com.google.heart_rate.bpm",
                    "dataSourceId": "derived:com.google.heart_rate.bpm:com.google.android.gms:merge_heart_rate_bpm"
                }
            ],
            "bucketByTime": {
                "durationMillis": 86400000  # 1 day buckets
            },
            "startTimeMillis": start_ms,
            "endTimeMillis": end_ms
        }

        try:
            resp = requests.post(aggregate_url, headers=headers, json=request_body, timeout=25)
            if not resp.ok:
                # Fall back gracefully to standard data types if derived sources are unavailable
                request_body["aggregateBy"] = [
                    {"dataTypeName": "com.google.step_count.delta"},
                    {"dataTypeName": "com.google.sleep.segment"},
                    {"dataTypeName": "com.google.heart_rate.bpm"}
                ]
                resp = requests.post(aggregate_url, headers=headers, json=request_body, timeout=25)

            if not resp.ok:
                print(f"  ⚠️ Chunk {w_idx}/{len(windows)} notice ({resp.status_code}): {resp.text[:120]}")
                continue

            data = resp.json()
            buckets = data.get("bucket", [])
            total_buckets_processed += len(buckets)

            for bucket in buckets:
                b_start_ms = int(bucket.get("startTimeMillis", 0))
                date_str = datetime.utcfromtimestamp(b_start_ms / 1000.0).strftime("%Y-%m-%d")

                step_count = 0
                sleep_minutes = 0.0
                deep_sleep_minutes = 0.0
                rem_sleep_minutes = 0.0
                hr_values: List[float] = []

                for dataset in bucket.get("dataset", []):
                    for point in dataset.get("point", []):
                        dt_name = point.get("dataTypeName", "")

                        # 1. Step Count
                        if "step_count" in dt_name:
                            for val in point.get("value", []):
                                step_count += int(val.get("intVal", 0))

                        # 2. Sleep Segments
                        elif "sleep" in dt_name:
                            p_start = int(point.get("startTimeNanos", 0))
                            p_end = int(point.get("endTimeNanos", 0))
                            duration_mins = max(0, (p_end - p_start) / (1e9 * 60.0))
                            sleep_minutes += duration_mins

                            for val in point.get("value", []):
                                stage_type = val.get("intVal", 2)
                                if stage_type == 5:
                                    deep_sleep_minutes += duration_mins
                                elif stage_type == 6:
                                    rem_sleep_minutes += duration_mins

                        # 3. Heart Rate
                        elif "heart_rate" in dt_name:
                            for val in point.get("value", []):
                                fp_val = val.get("fpVal")
                                if fp_val and fp_val > 0:
                                    hr_values.append(float(fp_val))

                avg_hr = round(sum(hr_values) / len(hr_values), 1) if hr_values else 0.0
                resting_hr = round(sorted(hr_values)[max(0, int(len(hr_values) * 0.1))], 1) if hr_values else 0.0

                # Upsert into daily_health_metrics
                metric_rec = db.query(DailyHealthMetric).filter(
                    DailyHealthMetric.user_id == user_id,
                    DailyHealthMetric.date == date_str
                ).first()

                if not metric_rec:
                    metric_rec = DailyHealthMetric(
                        user_id=user_id,
                        date=date_str,
                        step_count=step_count,
                        sleep_minutes=sleep_minutes,
                        deep_sleep_minutes=deep_sleep_minutes,
                        rem_sleep_minutes=rem_sleep_minutes,
                        resting_heart_rate=resting_hr,
                        avg_heart_rate=avg_hr
                    )
                    db.add(metric_rec)
                else:
                    if step_count > 0:
                        metric_rec.step_count = step_count
                    if sleep_minutes > 0:
                        metric_rec.sleep_minutes = sleep_minutes
                        metric_rec.deep_sleep_minutes = deep_sleep_minutes
                        metric_rec.rem_sleep_minutes = rem_sleep_minutes
                    if avg_hr > 0:
                        metric_rec.avg_heart_rate = avg_hr
                        metric_rec.resting_heart_rate = resting_hr

                records_saved += 1

        except Exception as chunk_err:
            print(f"  ⚠️ Chunk {w_idx} encountered error ({chunk_err}), continuing...")
            continue

    db.commit()

    # Recalculate 15-day baseline
    baseline_info = calculate_user_baseline(user_id, db)

    return {
        "status": "success",
        "user_id": user_id,
        "chunks_processed": len(windows),
        "buckets_processed": total_buckets_processed,
        "days_synced": records_saved,
        "baseline": baseline_info
    }

# ==============================================================================
# 3. 15-DAY PHYSIOLOGICAL BASELINING ENGINE
# ==============================================================================

def calculate_user_baseline(user_id: int, db: Session) -> Dict[str, Any]:
    """
    Computes a personalized physiological baseline using the user's recorded days:
    - If active_days >= 15: is_ready = True. Baseline is established.
    - If active_days < 15: is_ready = False. Baseline is in training mode.
    """
    # Fetch all records ordered chronologically
    records = db.query(DailyHealthMetric).filter(
        DailyHealthMetric.user_id == user_id
    ).order_by(DailyHealthMetric.date.desc()).all()

    # Filter for valid active days (where at least one biometric was recorded)
    active_days = [
        r for r in records
        if r.step_count > 0 or r.sleep_minutes > 0 or r.avg_heart_rate > 0
    ]

    total_active_days = len(active_days)
    is_ready = total_active_days >= 15

    # Compute baseline metrics from the most recent 15-30 days
    sample_window = active_days[:30] if total_active_days >= 15 else active_days

    steps_list = [r.step_count for r in sample_window if r.step_count > 0]
    sleep_list = [r.sleep_minutes for r in sample_window if r.sleep_minutes > 0]
    hr_list = [r.resting_heart_rate for r in sample_window if r.resting_heart_rate > 0]

    avg_steps = sum(steps_list) / len(steps_list) if steps_list else 0.0
    avg_sleep = sum(sleep_list) / len(sleep_list) if sleep_list else 0.0
    avg_hr = sum(hr_list) / len(hr_list) if hr_list else 0.0

    # Calculate variance / standard deviation for resting heart rate
    if len(hr_list) > 1:
        variance = sum((x - avg_hr) ** 2 for x in hr_list) / (len(hr_list) - 1)
        hr_std_dev = variance ** 0.5
    else:
        hr_std_dev = 0.0

    # Upsert baseline table
    baseline_rec = db.query(UserBaseline).filter(UserBaseline.user_id == user_id).first()
    if not baseline_rec:
        baseline_rec = UserBaseline(
            user_id=user_id,
            is_ready=is_ready,
            days_collected=total_active_days,
            avg_steps=avg_steps,
            avg_sleep_minutes=avg_sleep,
            avg_resting_hr=avg_hr,
            hr_variance=hr_std_dev
        )
        db.add(baseline_rec)
    else:
        baseline_rec.is_ready = is_ready
        baseline_rec.days_collected = total_active_days
        baseline_rec.avg_steps = avg_steps
        baseline_rec.avg_sleep_minutes = avg_sleep
        baseline_rec.avg_resting_hr = avg_hr
        baseline_rec.hr_variance = hr_std_dev

    db.commit()
    return baseline_rec.to_dict()

# ==============================================================================
# 4. MOCK DATA GENERATOR (FOR LOCAL TESTING & INSTANT DEMONSTRATION)
# ==============================================================================

def seed_demo_user_with_metrics(email: str, db: Session, days: int = 18, is_admin: bool = False) -> Dict[str, Any]:
    """Helper for testing: seeds a demo user with realistic 6-month wearable data."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            google_id=f"demo_google_{int(time.time())}",
            email=email,
            name="Clinical Research Participant",
            avatar_url="https://lh3.googleusercontent.com/a/default-user",
            role="admin" if is_admin else "user"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Seed daily metrics going back `days`
    import random
    now = datetime.utcnow()
    for d in range(days):
        dt = now - timedelta(days=d)
        date_str = dt.strftime("%Y-%m-%d")

        existing = db.query(DailyHealthMetric).filter(
            DailyHealthMetric.user_id == user.id,
            DailyHealthMetric.date == date_str
        ).first()

        if not existing:
            # Realistic physiological simulation
            steps = random.randint(6500, 11500)
            sleep_hours = random.uniform(6.2, 8.4)
            sleep_mins = sleep_hours * 60.0
            deep_mins = sleep_mins * random.uniform(0.18, 0.25)
            rem_mins = sleep_mins * random.uniform(0.20, 0.28)
            resting_hr = random.uniform(62.0, 72.0)
            avg_hr = resting_hr + random.uniform(10.0, 22.0)

            rec = DailyHealthMetric(
                user_id=user.id,
                date=date_str,
                step_count=steps,
                sleep_minutes=sleep_mins,
                deep_sleep_minutes=deep_mins,
                rem_sleep_minutes=rem_mins,
                resting_heart_rate=resting_hr,
                avg_heart_rate=avg_hr
            )
            db.add(rec)

    db.commit()
    baseline = calculate_user_baseline(user.id, db)
    token = create_app_jwt(user)

    return {
        "user": user.to_dict(),
        "baseline": baseline,
        "token": token
    }

if __name__ == "__main__":
    print("Google Health Service initialized.")
    print("Auth URL preview:")
    print(build_google_auth_url())
