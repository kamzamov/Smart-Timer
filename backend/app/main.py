from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
import csv
import io
import os

from app.database import get_db, init_db
from app.models import StudySession, User, Note
from app.schemas import (
    UserRegister,
    UserLogin,
    TokenResponse,
    SessionStart,
    SessionEdit,
    SessionResponse,
    WeeklyStats,
    LastSession,
    SubjectItem,
    NoteCreate,
    NoteResponse,
    NoteEdit,
)

SECRET_KEY = os.getenv("JWT_SECRET", "smart-timer-secret-key-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

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


# --- Auth helpers ---
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))


def create_token(user_id: int, username: str) -> str:
    payload = {"sub": str(user_id), "username": username}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# --- Auth endpoints ---
@app.post("/api/auth/register", response_model=TokenResponse)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.username == data.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")

    user = User(username=data.username, hashed_password=hash_password(data.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_token(user.id, user.username)
    return TokenResponse(access_token=token, username=user.username)


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Wrong username or password")

    token = create_token(user.id, user.username)
    return TokenResponse(access_token=token, username=user.username)


# --- Session endpoints ---
@app.post("/api/sessions/start", response_model=SessionResponse)
async def start_session(
    data: SessionStart,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = StudySession(subject=data.subject.strip(), user_id=user.id)
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
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(StudySession).where(StudySession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != user.id:
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


@app.put("/api/sessions/{session_id}", response_model=SessionResponse)
async def edit_session(
    session_id: int,
    data: SessionEdit,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(StudySession).where(StudySession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your session")

    if data.subject is not None:
        session.subject = data.subject.strip()
    if data.start_time is not None:
        session.start_time = data.start_time
    if data.end_time is not None:
        session.end_time = data.end_time

    await db.commit()
    await db.refresh(session)

    duration = None
    if session.end_time:
        duration = (session.end_time - session.start_time).total_seconds() / 60.0

    return SessionResponse(
        id=session.id,
        subject=session.subject,
        start_time=session.start_time,
        end_time=session.end_time,
        duration_minutes=round(duration, 2) if duration else None,
    )


@app.delete("/api/sessions/{session_id}")
async def delete_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(StudySession).where(StudySession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your session")

    await db.delete(session)
    await db.commit()
    return {"detail": "Session deleted"}


@app.get("/api/stats/weekly", response_model=WeeklyStats)
async def weekly_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    monday = now - timedelta(days=now.weekday(), hours=now.hour, minutes=now.minute, seconds=now.second, microseconds=now.microsecond)

    result = await db.execute(
        select(StudySession)
        .where(StudySession.user_id == user.id)
        .where(StudySession.start_time >= monday)
        .where(StudySession.end_time.isnot(None))
        .order_by(StudySession.start_time.desc())
    )
    sessions = result.scalars().all()

    total_minutes = 0.0
    by_subject: dict[str, float] = {}
    by_day = [0.0] * 7
    by_day_by_subject: dict[str, list[float]] = {}
    last_sessions = []

    for s in sessions:
        dur = (s.end_time - s.start_time).total_seconds() / 60.0
        total_minutes += dur
        by_subject[s.subject] = by_subject.get(s.subject, 0.0) + dur

        day_idx = s.start_time.weekday()
        by_day[day_idx] += dur

        if s.subject not in by_day_by_subject:
            by_day_by_subject[s.subject] = [0.0] * 7
        by_day_by_subject[s.subject][day_idx] += dur

        last_sessions.append(
            LastSession(
                id=s.id,
                subject=s.subject,
                start_time=s.start_time,
                end_time=s.end_time,
                duration_minutes=round(dur, 2),
            )
        )

    # Add notes to stats
    notes_result = await db.execute(
        select(Note)
        .where(Note.user_id == user.id)
        .where(Note.note_time >= monday)
        .order_by(Note.note_time.desc())
    )
    notes = notes_result.scalars().all()

    for n in notes:
        dur = float(n.duration_minutes)
        total_minutes += dur
        day_idx = n.note_time.weekday()
        by_day[day_idx] += dur

        subject_label = "📝 " + n.content[:30]
        if subject_label not in by_day_by_subject:
            by_day_by_subject[subject_label] = [0.0] * 7
        by_day_by_subject[subject_label][day_idx] += dur

        # For by_subject tracking
        by_subject[subject_label] = by_subject.get(subject_label, 0.0) + dur

        last_sessions.append(
            LastSession(
                id=n.id,
                subject="Note: " + n.content,
                start_time=n.note_time,
                end_time=n.note_time,
                duration_minutes=round(dur, 2),
            )
        )

    # Sort all by time desc
    last_sessions.sort(key=lambda x: x.start_time, reverse=True)

    return WeeklyStats(
        total_minutes=round(total_minutes, 2),
        by_subject=by_subject,
        by_day=[round(v, 2) for v in by_day],
        by_day_by_subject={k: [round(v, 2) for v in vals] for k, vals in by_day_by_subject.items()},
        last_sessions=last_sessions[:10],
    )


@app.get("/api/subjects", response_model=list[SubjectItem])
async def list_subjects(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(StudySession.subject)
        .where(StudySession.user_id == user.id)
        .distinct()
        .order_by(StudySession.subject)
    )
    subjects = result.scalars().all()
    return [SubjectItem(subject=s) for s in subjects]


@app.get("/api/sessions")
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(StudySession)
        .where(StudySession.user_id == user.id)
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
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(StudySession)
        .where(StudySession.user_id == user.id)
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


# --- Notes endpoints ---
@app.post("/api/notes", response_model=NoteResponse)
async def create_note(
    data: NoteCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if data.duration_hours < 0 or data.duration_minutes < 0:
        raise HTTPException(status_code=400, detail="Duration must be positive")
    if data.duration_minutes > 59:
        raise HTTPException(status_code=400, detail="Minutes must be 0-59")

    nt = data.note_time or datetime.now(timezone.utc)
    if nt > datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Cannot create notes for future dates")

    total_min = data.duration_hours * 60 + data.duration_minutes
    note = Note(content=data.content.strip(), note_time=nt, duration_minutes=total_min, user_id=user.id)
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return NoteResponse(id=note.id, content=note.content, note_time=note.note_time, duration_minutes=note.duration_minutes)


@app.get("/api/notes", response_model=list[NoteResponse])
async def list_notes(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Note)
        .where(Note.user_id == user.id)
        .order_by(Note.note_time.desc())
        .limit(100)
    )
    notes = result.scalars().all()
    return [NoteResponse(id=n.id, content=n.content, note_time=n.note_time, duration_minutes=n.duration_minutes) for n in notes]


@app.put("/api/notes/{note_id}", response_model=NoteResponse)
async def edit_note(
    note_id: int,
    data: NoteEdit,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Note).where(Note.id == note_id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    if note.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your note")

    if data.content is not None:
        note.content = data.content.strip()
    if data.note_time is not None:
        if data.note_time > datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Cannot set note time to future date")
        note.note_time = data.note_time
    if data.duration_hours is not None or data.duration_minutes is not None:
        h = data.duration_hours if data.duration_hours is not None else note.duration_minutes // 60
        m = data.duration_minutes if data.duration_minutes is not None else note.duration_minutes % 60
        if h < 0 or m < 0:
            raise HTTPException(status_code=400, detail="Duration must be positive")
        if m > 59:
            raise HTTPException(status_code=400, detail="Minutes must be 0-59")
        note.duration_minutes = h * 60 + m

    await db.commit()
    await db.refresh(note)
    return NoteResponse(id=note.id, content=note.content, note_time=note.note_time, duration_minutes=note.duration_minutes)


@app.delete("/api/notes/{note_id}")
async def delete_note(
    note_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Note).where(Note.id == note_id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    if note.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your note")

    await db.delete(note)
    await db.commit()
    return {"detail": "Note deleted"}
