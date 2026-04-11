# Smart Timer

A web application for tracking study sessions. Start a timer, pick a subject, stop when done — and see weekly statistics.

## Quick Start

```bash
# Copy environment config
cp .env.example .env

# Start all services
docker compose up -d --build
```

- **Frontend**: http://localhost:3000
- **Backend API docs**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432

## Project Structure

```
Smart-Timer/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app + API endpoints
│   │   ├── models.py         # SQLAlchemy model
│   │   ├── schemas.py        # Pydantic schemas
│   │   └── database.py       # DB connection
│   ├── Dockerfile
│   └── requirements.txt
├── client/
│   ├── index.html            # Single-page app (HTML/JS/Chart.js)
│   ├── nginx.conf
│   └── Dockerfile
├── scripts/
│   └── deploy.sh             # Deploy to university VM
├── docker-compose.yml
├── .env.example
└── README.md
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/sessions/start` | Start a new study session |
| POST | `/api/sessions/{id}/stop` | Stop an active session |
| GET | `/api/stats/weekly` | Get weekly statistics |
| GET | `/api/subjects` | List all subjects for user |
| GET | `/api/sessions` | List recent sessions |
| GET | `/api/export/csv` | Export sessions as CSV |

All endpoints accept `X-User-Key` header for user isolation (default: `demo`).

## Deploy to University VM

```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

The VM is at `10.93.25.19`. After deploy:
- Frontend: http://10.93.25.19:3000
- API: http://10.93.25.19:8000/docs

## Tech Stack

- **Backend**: FastAPI + SQLAlchemy (async) + PostgreSQL
- **Frontend**: Vanilla HTML/JS + Chart.js
- **Infra**: Docker Compose, Nginx

<img width="904" height="925" alt="image" src="https://github.com/user-attachments/assets/3ecbff16-d0ff-420e-8e4c-3b3f8258be92" />

