from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict


# --- Auth ---
class UserRegister(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


# --- Sessions ---
class SessionStart(BaseModel):
    subject: str


class SessionEdit(BaseModel):
    subject: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class SessionResponse(BaseModel):
    id: int
    subject: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_minutes: Optional[float] = None

    model_config = {"from_attributes": True}


# --- Stats ---
class LastSession(BaseModel):
    id: int
    subject: str
    start_time: datetime
    end_time: datetime
    duration_minutes: float


class WeeklyStats(BaseModel):
    total_minutes: float
    by_subject: Dict[str, float]
    by_day: List[float]
    by_day_by_subject: Dict[str, List[float]]
    last_sessions: List[LastSession]


class SubjectItem(BaseModel):
    subject: str


# --- Notes ---
class NoteCreate(BaseModel):
    content: str
    note_time: Optional[datetime] = None
    duration_hours: int = 0
    duration_minutes: int = 0


class NoteResponse(BaseModel):
    id: int
    content: str
    note_time: datetime
    duration_minutes: int

    model_config = {"from_attributes": True}


class NoteEdit(BaseModel):
    content: Optional[str] = None
    note_time: Optional[datetime] = None
    duration_hours: Optional[int] = None
    duration_minutes: Optional[int] = None
