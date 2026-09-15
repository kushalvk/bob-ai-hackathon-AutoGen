# Setup Guide

> **This file is read by the automated evaluation pipeline. Be precise and complete.**

## Prerequisites

Before you begin, ensure you have the following installed:

- [x] Python 3.11+
- [x] Pip package manager

---

## Environment Variables

Copy `.env.example` (or create `.env`) and fill in the values:

| Variable | Description | Default | Required |
|---|---|---|---|
| `DATABASE_URL` | Database connection string | `sqlite:///./clinguard.db` | No (defaults to SQLite) |
| `DEBUG` | Enable debug logging | `False` | No |

---

## Installation & Setup

```bash
# 1. Install backend dependencies
pip install -r requirements.txt

# 2. Run database migrations (Alembic)
python -m alembic upgrade head

# 3. Seed synthetic dataset (deterministically seeds protocol, sites, patients, visit records, and planted deviations)
python -m src.backend.seed
```

---

## Running the Application

Start the FastAPI backend with Uvicorn:

```bash
python -m uvicorn src.backend.main:app --reload --port 8000
```

The application will be available at:
- **Health Check Endpoint**: [http://localhost:8000/health](http://localhost:8000/health)
- **Interactive OpenAPI Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## Running Tests

Execute automated pytest suite:

```bash
python -m pytest
```

---

## Seed Dataset Overview

- **1 Protocol**: `PROTO-001` (Phase II study with 2 study drugs and 6 visit types).
- **5 Sites**:
  - `SITE-101`: Metro General Research Center (High risk, 35% turnover)
  - `SITE-102`: St. Jude Clinical Institute (Mixed risk, 15% turnover)
  - `SITE-103`: Heidelberg University Hospital (Mixed risk, 12% turnover)
  - `SITE-104`: Tokyo Medical Research Hub (Mixed risk, 8% turnover)
  - `SITE-105`: Nordic Health Trial Site (Low risk, 2% turnover)
- **35 Patients**: Distributed across 5 sites.
- **210 Visit Records**: Mix of clean records and planted deviations.
- **24 Planted Deviations**: Covering all 5 deviation types (`missed_visit`, `wrong_dose`, `banned_comed`, `eligibility_breach`, `documentation`).
- **Baseline Fixture**: Saved at `src/backend/fixtures/expected_deviations.json`.

---

## Troubleshooting

| Issue | Solution |
|---|---|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| `Alembic Migration Failure` | Ensure SQLite file write permissions or check `DATABASE_URL` connectivity |
| `Database connection refused` | Check `DATABASE_URL` environment variable syntax |
