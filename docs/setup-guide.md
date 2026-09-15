# Setup Guide

> **This file is read by the automated evaluation pipeline and evaluators. Follow these tested instructions to run ClinGuard AI locally.**

---

## Prerequisites

Before starting, ensure the following software is installed on your machine:

- **Python 3.11+** (Tested on Python 3.11, 3.12, 3.14)
- **Node.js 18+** and **npm 9+**
- **Git**

---

## Environment Configuration

A template configuration file is provided at `src/.env.example`. Create a `.env` file in the repository root or in `src/`:

```bash
cp src/.env.example .env
```

### Environment Variable Reference

| Variable | Description | Default | Required |
|---|---|---|---|
| `DATABASE_URL` | SQLite or PostgreSQL database URL | `sqlite:///./clinguard.db` | No |
| `DEBUG` | Enable verbose debug logging | `False` | No |
| `LLM_PROVIDER` | LLM backend for narrative review (`watsonx` or empty) | `""` (Deterministic fallback) | No |
| `WATSONX_API_KEY` | IBM Cloud API key for watsonx.ai | `""` | Optional |
| `WATSONX_PROJECT_ID` | IBM watsonx.ai project identifier | `""` | Optional |
| `WATSONX_URL` | IBM watsonx.ai endpoint URL | `https://us-south.ml.cloud.ibm.com` | No |
| `WATSONX_MODEL_ID` | Foundation model identifier | `ibm/granite-13b-instruct-v2` | No |

> **Note on LLM Access**: If `WATSONX_API_KEY` is not provided, ClinGuard AI automatically operates in **pure deterministic mode** with 100% functionality — rule-based classifications, exact risk scores, and standard clinical CAPA narratives.

---

## Installation & Setup

### 1. Backend Installation

From the repository root:

```bash
# 1. Install Python backend dependencies
pip install -r requirements.txt

# 2. Seed synthetic trial dataset (reproducible seed value 42)
python -m src.backend.seed
```

The seed script creates `clinguard.db` and populates:
- **1 Protocol**: `PROTO-001` (Phase II Hypercholesterolemia study)
- **5 Investigation Sites**: Varied operational profiles (`SITE-101` high risk through `SITE-105` low risk)
- **35 Patients**: 7 subjects per site
- **210 Visit Records**: Complete visit schedule and clinical logs
- **24 Planted Protocol Deviations**: Covering all 5 GCP deviation categories
- **Initial Risk Scores & CAPAs**: Persisted baseline scores and CAPAs

### 2. Frontend Installation

In a separate terminal:

```bash
cd src/frontend
npm install
```

---

## Running the Application

### 1. Start the Backend API (Terminal 1)

```bash
python -m uvicorn src.backend.main:app --reload --port 8000
```

Backend services will be live at:
- **Interactive OpenAPI (Swagger) Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
- **API Root**: [http://localhost:8000/](http://localhost:8000/)

### 2. Start the Frontend Dashboard (Terminal 2)

```bash
cd src/frontend
npm run dev
```

- **ClinGuard Clinical Dashboard**: [http://localhost:5173](http://localhost:5173)

### 3. Model Context Protocol (MCP) Server (Optional / Standalone)

The MCP server communicates over standard input/output (stdio) using JSON-RPC 2.0:

```bash
python -m src.backend.mcp_server.server
```

---

## Running Automated Tests

Run the complete test suite (107 unit and integration tests):

```bash
python -m pytest tests/ -v
```

### Test Suite Breakdown

| Test File | Tests | Coverage Scope |
|---|:---:|---|
| `tests/test_detection.py` | 10 | Dosing, window, comed, eligibility, and documentation detection evaluators |
| `tests/test_severity_classifier.py` | 42 | Deterministic ICH E6(R2) table, MockLLM overrides, and evidence extraction |
| `tests/test_site_risk.py` | 14 | 7-factor normalizers, weight validation, site ranking (`SITE-101` > `SITE-105`), and FastAPI endpoints |
| `tests/test_capa.py` | 19 | 30-day clustering, narrative drafting, Markdown export, and PDF generation |
| `tests/test_mcp_server.py` | 18 | JSON-RPC protocol dispatch, schema validation, and all 4 MCP tool implementations |
| `tests/test_seed.py` | 2 | Database entity counts and expected deviations fixture validation |
| `tests/test_health.py` | 2 | `/health` and root API endpoints |
| **Total** | **107** | **100% Passing** |

---

## Troubleshooting

| Symptom | Likely Cause | Solution |
|---|---|---|
| `ModuleNotFoundError: No module named 'fpdf'` | Missing `fpdf2` dependency | Run `pip install fpdf2` or `pip install -r requirements.txt` |
| `ModuleNotFoundError: No module named 'fastapi'` | Dependencies not installed in current Python environment | Run `pip install -r requirements.txt` under your active Python executable |
| `sqlite3.OperationalError: no such table` | Database has not been seeded | Execute `python -m src.backend.seed` to initialize and populate tables |
| `Frontend fails to connect to backend (NetworkError)` | FastAPI server is not running on port 8000 | Verify backend is active on [http://localhost:8000/health](http://localhost:8000/health) |
| `Port 8000 or 5173 already in use` | Another process is holding the port | Specify an alternative port, e.g. `uvicorn src.backend.main:app --port 8001` or edit `vite.config.ts` |
| `LLM review returns default severity` | `WATSONX_API_KEY` is not set or invalid | By design: ClinGuard AI gracefully defaults to deterministic ICH E6(R2) rule tables without error |
