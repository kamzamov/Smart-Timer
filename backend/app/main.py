from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func as sql_func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta
from typing import Optional
import csv
import io

from app.database import get_db, init_db
from app.models import StudySession
from app.schemas import (
    SessionStart,
    SessionResponse,
    WeeklyStats,
    LastSession,
    SubjectItem,
)

app = FastAPI(title="Smart Timer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await init_db()


def get_user_key(x_user_key: Optional[str] = Header(default="demo")) -> str:
    return x_user_key


@app.post("/api/sessions/start", response_model=SessionResponse)
async def start_session(
    data: SessionStart,
    db: AsyncSession = Depends(get_db),
    user_key: str = Depends(get_user_key),
):
    uk = data.user_key if data.user_key != "demo" else user_key
    session = StudySession(subject=data.subject.strip(), user_key=uk)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionResponse(
        id=session.id,
        subject=session.subject,
        start_time=session.start_time,
        end_time=None,
        duration_minutes=None,
    )


@app.post("/api/sessions/{session_id}/stop", response_model=SessionResponse)
async def stop_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user_key: str = Depends(get_user_key),
):
    result = await db.execute(select(StudySession).where(StudySession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_key != user_key:
        raise HTTPException(status_code=403, detail="Not your session")
    if session.end_time is not None:
        raise HTTPException(status_code=400, detail="Session already stopped")

    session.end_time = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)

    duration = (session.end_time - session.start_time).total_seconds() / 60.0
    return SessionResponse(
        id=session.id,
        subject=session.subject,
        start_time=session.start_time,
        end_time=session.end_time,
        duration_minutes=round(duration, 2),
    )


@app.get("/api/stats/weekly", response_model=WeeklyStats)
async def weekly_stats(
    db: AsyncSession = Depends(get_db),
    user_key: str = Depends(get_user_key),
):
    now = datetime.now(timezone.utc)
    monday = now - timedelta(days=now.weekday(), hours=now.hour, minutes=now.minute, seconds=now.second, microseconds=now.microsecond)

    result = await db.execute(
        select(StudySession)
        .where(StudySession.user_key == user_key)
        .where(StudySession.start_time >= monday)
        .where(StudySession.end_time.isnot(None))
        .order_by(StudySession.start_time.desc())
    )
    sessions = result.scalars().all()

    total_minutes = 0.0
    by_subject: dict[str, float] = {}
    by_day = [0.0] * 7
    last_sessions = []

    for s in sessions:
        dur = (s.end_time - s.start_time).total_seconds() / 60.0
        total_minutes += dur
        by_subject[s.subject] = by_subject.get(s.subject, 0.0) + dur

        day_idx = (s.start_time.weekday())
        by_day[day_idx] += dur

        last_sessions.append(
            LastSession(
                id=s.id,
                subject=s.subject,
                start_time=s.start_time,
                end_time=s.end_time,
                duration_minutes=round(dur, 2),
            )
        )

    return WeeklyStats(
        total_minutes=round(total_minutes, 2),
        by_subject=by_subject,
        by_day=[round(v, 2) for v in by_day],
        last_sessions=last_sessions[:10],
    )


@app.get("/api/subjects", response_model=list[SubjectItem])
async def list_subjects(
    db: AsyncSession = Depends(get_db),
    user_key: str = Depends(get_user_key),
):
    result = await db.execute(
        select(StudySession.subject)
        .where(StudySession.user_key == user_key)
        .distinct()
        .order_by(StudySession.subject)
    )
    subjects = result.scalars().all()
    return [SubjectItem(subject=s) for s in subjects]


@app.get("/api/sessions")
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    user_key: str = Depends(get_user_key),
):
    result = await db.execute(
        select(StudySession)
        .where(StudySession.user_key == user_key)
        .where(StudySession.end_time.isnot(None))
        .order_by(StudySession.start_time.desc())
        .limit(50)
    )
    sessions = result.scalars().all()
    out = []
    for s in sessions:
        dur = (s.end_time - s.start_time).total_seconds() / 60.0
        out.append(
            SessionResponse(
                id=s.id,
                subject=s.subject,
                start_time=s.start_time,
                end_time=s.end_time,
                duration_minutes=round(dur, 2),
            )
        )
    return out


@app.get("/api/export/csv")
async def export_csv(
    db: AsyncSession = Depends(get_db),
    user_key: str = Depends(get_user_key),
):
    result = await db.execute(
        select(StudySession)
        .where(StudySession.user_key == user_key)
        .where(StudySession.end_time.isnot(None))
        .order_by(StudySession.start_time.desc())
    )
    sessions = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "subject", "start_time", "end_time", "duration_minutes"])
    for s in sessions:
        dur = (s.end_time - s.start_time).total_seconds() / 60.0
        writer.writerow([s.id, s.subject, str(s.start_time), str(s.end_time), round(dur, 2)])

    from fastapi.responses import Response
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sessions.csv"},
    )
