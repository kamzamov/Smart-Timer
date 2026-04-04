from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict


class SessionStart(BaseModel):
    subject: str
    user_key: str = "demo"


class SessionResponse(BaseModel):
    id: int
    subject: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_minutes: Optional[float] = None

    model_config = {"from_attributes": True}


class ByDayStats(BaseModel):
    day: str
    minutes: float


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
