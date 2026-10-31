import os
import sys
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

# Windows UTF-8 console output guard
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "clinical_health.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    google_id = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    role = Column(String(50), default="user", nullable=False)  # "user" or "admin"
    created_at = Column(DateTime, default=datetime.utcnow)

    tokens = relationship("OAuthToken", back_populates="user", uselist=False, cascade="all, delete-orphan")
    metrics = relationship("DailyHealthMetric", back_populates="user", cascade="all, delete-orphan")
    baseline = relationship("UserBaseline", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "google_id": self.google_id,
            "email": self.email,
            "name": self.name,
            "avatar_url": self.avatar_url,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_expiry = Column(DateTime, nullable=True)
    scope = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="tokens")

class DailyHealthMetric(Base):
    __tablename__ = "daily_health_metrics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    date = Column(String(10), index=True, nullable=False)  # Format: YYYY-MM-DD
    step_count = Column(Integer, default=0)
    sleep_minutes = Column(Float, default=0.0)
    deep_sleep_minutes = Column(Float, default=0.0)
    rem_sleep_minutes = Column(Float, default=0.0)
    resting_heart_rate = Column(Float, default=0.0)
    avg_heart_rate = Column(Float, default=0.0)
    raw_data = Column(Text, nullable=True)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="metrics")

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_user_date"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "step_count": self.step_count,
            "sleep_minutes": round(self.sleep_minutes, 1),
            "sleep_hours": round(self.sleep_minutes / 60.0, 2),
            "deep_sleep_minutes": round(self.deep_sleep_minutes, 1),
            "rem_sleep_minutes": round(self.rem_sleep_minutes, 1),
            "resting_heart_rate": round(self.resting_heart_rate, 1),
            "avg_heart_rate": round(self.avg_heart_rate, 1)
        }

class UserBaseline(Base):
    __tablename__ = "user_baselines"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    is_ready = Column(Boolean, default=False)
    days_collected = Column(Integer, default=0)
    avg_steps = Column(Float, default=0.0)
    avg_sleep_minutes = Column(Float, default=0.0)
    avg_resting_hr = Column(Float, default=0.0)
    hr_variance = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="baseline")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_ready": self.is_ready,
            "days_collected": self.days_collected,
            "days_required": 15,
            "days_remaining": max(0, 15 - self.days_collected),
            "avg_steps": round(self.avg_steps, 0),
            "avg_sleep_hours": round(self.avg_sleep_minutes / 60.0, 2) if self.avg_sleep_minutes else 0.0,
            "avg_resting_hr": round(self.avg_resting_hr, 1),
            "hr_variance": round(self.hr_variance, 2),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    print("✅ SQLite database initialized successfully at:", DB_PATH)
