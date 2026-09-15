# ClinGuard AI Backend Setup & Developer Guide

This document provides step-by-step instructions for setting up the ClinGuard AI backend environment, configuring the database, running database migrations, seeding synthetic data, running tests, and launching the local server.

---

## Prerequisites

- **Python**: Version 3.11+
- **Pip**: Latest version

---

## 1. Installation

Install all required Python dependencies:

```bash
pip install -r requirements.txt
```

---

## 2. Database Configuration

ClinGuard AI supports both local SQLite development and PostgreSQL production environments:

- **Default (SQLite)**: If `DATABASE_URL` is not set, the application defaults to `sqlite:///./clinguard.db`.
- **PostgreSQL**: Set the environment variable `DATABASE_URL` (e.g., `postgresql://user:password@localhost:5432/clinguard_db`).

---

## 3. Database Migrations (Alembic)

Database schemas are managed using Alembic migration scripts.

To apply all database schema migrations and bring your database to the latest revision:

```bash
python -m alembic upgrade head
```

To roll back a migration step:

```bash
python -m alembic downgrade -1
```

---

## 4. Seeding Synthetic Data

The project includes a deterministic synthetic data generator (`src/backend/seed.py`) using a fixed random seed (`42`).

To seed the database with synthetic protocols, sites, patients, visit records, planted deviations, site risk scores, and CAPA reports:

```bash
python -m src.backend.seed
```

### Seed Dataset Overview:
- **1 Protocol**: `PROTO-001` (Phase II study with 2 study drugs and 6 visit types).
- **5 Sites**:
  - `SITE-101`: Metro General Research Center (High risk, 35% turnover)
  - `SITE-102`: St. Jude Clinical Institute (Mixed risk, 15% turnover)
  - `SITE-103`: Heidelberg University Hospital (Mixed risk, 12% turnover)
  - `SITE-104`: Tokyo Medical Research Hub (Mixed risk, 8% turnover)
  - `SITE-105`: Nordic Health Trial Site (Low risk, 2% turnover)
- **35 Patients**: Distributed across the 5 sites.
- **210 Visit Records**: Mix of clean records and planted deviations.
- **24 Planted Deviations**: Covering all 5 deviation types (`missed_visit`, `wrong_dose`, `banned_comed`, `eligibility_breach`, `documentation`).
- **Fixtures Export**: Baseline fixture saved at `src/backend/fixtures/expected_deviations.json`.

---

## 5. Running Tests

To run the automated test suite verifying health check endpoints, database schema, and seed data integrity:

```bash
python -m pytest
```

---

## 6. Starting the FastAPI Server

Launch the Uvicorn development server:

```bash
python -m uvicorn src.backend.main:app --reload --port 8000
```

### Interactive Documentation & Health Endpoint

- **Health Check Endpoint**: [http://localhost:8000/health](http://localhost:8000/health)
- **Interactive OpenAPI Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## Project Directory Layout

```
├── docs/
│   └── setup-guide.md
├── requirements.txt
├── alembic.ini
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial_schema.py
├── tests/
│   ├── test_health.py
│   └── test_seed.py
└── src/
    └── backend/
        ├── config.py
        ├── database.py
        ├── main.py
        ├── seed.py
        ├── models/
        │   ├── protocol.py
        │   ├── site.py
        │   ├── patient.py
        │   ├── visit.py
        │   ├── deviation.py
        │   ├── site_risk.py
        │   └── capa.py
        ├── api/
        │   └── health.py
        └── fixtures/
            └── expected_deviations.json
```
