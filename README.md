# 🚀 ClinGuard AI

> **Autonomous Clinical Trial Protocol Compliance, Deterministic Risk Scoring & Automated CAPA Generation**

[![CI - Pytest Suite](https://img.shields.io/badge/tests-107%20passed-brightgreen.svg)](tests/)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI%200.110+-blue.svg)](src/backend/)
[![React](https://img.shields.io/badge/frontend-React%2018%20%2B%20Vite-61dafb.svg)](src/frontend/)
[![IBM watsonx.ai](https://img.shields.io/badge/AI-IBM%20watsonx.ai-black.svg)](https://www.ibm.com/products/watsonx-ai)
[![Model Context Protocol](https://img.shields.io/badge/protocol-MCP%20JSON--RPC%202.0-purple.svg)](src/backend/mcp_server/)

---

## 👥 Team

| Field | Value |
|---|---|
| **Team Name** | AutoGen |
| **Track** | AI |
| **Team Lead** | Kushal Vaghela — [kushalvaghela2003@gmail.com](mailto:kushalvaghela2003@gmail.com) |
| **Members** | Jemeet Shahi — [sjemeet@gmail.com](mailto:sjemeet@gmail.com)<br>Raj Panchigar — [rajpanchigar2004@gmail.com](mailto:rajpanchigar2004@gmail.com)<br>Darsh Boghara — [darshboghara61@gmail.com](mailto:darshboghara61@gmail.com) |

---

## 🎯 Problem Statement

A major clinical trial has **5,000+ patient visits across 200+ sites**. Protocol deviations — missed visits, wrong dosing, banned co-medications — go undetected until the FDA audit. A single rejected submission **delays drug approval by 6–12 months and costs $50–100M**. Risk managers need real-time visibility into which sites are highest risk before problems escalate.

> **Challenge**: Build a Bob solution that compares patient records against the protocol specification, classifies each deviation by severity (ICH E6 GCP: major/minor/administrative), scores site-level risk using leading indicators, and generates CAPA-ready reports with recommended mitigations.

---

## 💡 Solution

**ClinGuard AI** is an autonomous clinical compliance and Risk-Based Monitoring (RBM) platform built on a **strict architectural boundary between deterministic logic and generative AI**:
1. **Deterministic Deviation Detection**: 100% rule-based evaluation of visit windows, drug doses, prohibited co-medications, eligibility criteria, and documentation logs with full evidence trails.
2. **Hybrid Severity Classification**: Deterministic ICH E6(R2) classification rules paired with **IBM watsonx.ai Granite** review for ambiguous clinical edge cases.
3. **Deterministic 7-Factor Site Risk Scoring (0–100)**: Transparent weighted formula evaluating deviation frequency, EDC query resolution latency, turnover, and CRA monitoring recency.
4. **Automated CAPA Generator**: Temporal and categorical clustering of deviations within 30-day windows to draft root causes and preventive actions, exporting to Markdown and signed PDF.
5. **Model Context Protocol (MCP) Server**: 4 deterministic JSON-RPC compliance tools enabling natural-language chat assistants to answer queries with zero hallucination.

---

## ✨ Key Features

- **Rule-Based Protocol Deviation Engine**: Evaluates patient visit records against protocol specifications for missed/out-of-window visits, weight-adjusted dosing errors, banned CYP3A4 inhibitors, inclusion/exclusion lab failures, and missing signatures.
- **Hybrid Severity Classifier with watsonx.ai**: Categorizes deviations into Major, Minor, and Administrative grades, invoking IBM watsonx.ai to draft clinical rationales citing ICH E6(R2) Section 5.20 for borderline cases.
- **Quantitative Site Risk Scoring (0–100)**: Multi-factor risk engine computing auditable `contributing_factors` across major deviation rates (30%), query resolution time (15%), deviation trend (15%), staff turnover (10%), enrollment target deficit (10%), monitoring visit recency (10%), and minor gaps (10%).
- **Automated CAPA Report Generation**: Clusters repeat deviations by site, type, and 30-day timeframe into formal Corrective and Preventive Action plans with one-click Markdown and PDF downloads.
- **Model Context Protocol (MCP) AI Assistant**: Exposes 4 deterministic compliance tools (`run_deviation_detection`, `get_site_risk_scores`, `get_deviations`, `generate_or_fetch_capa`) for AI agents and chat interfaces.

---

## 🛠️ Tech Stack

| Category | Technologies |
|---|---|
| **Languages** | Python 3.11+, TypeScript 5.0+ |
| **Frameworks** | FastAPI 0.110+, React 18, Vite 5, TailwindCSS 3 |
| **IBM Technologies** | IBM watsonx.ai (`ibm/granite-13b-instruct-v2`), IBM Bob |
| **Databases** | SQLite (local development), PostgreSQL (production-ready SQLAlchemy ORM) |
| **Protocols & Export** | Model Context Protocol (MCP) JSON-RPC 2.0, fpdf2 (PDF generation) |
| **Testing** | pytest 9.1+ (107 automated unit and integration tests) |

---

## 📁 Repository Structure

```
├── src/
│   ├── backend/               # FastAPI backend, MCP server, and compliance engines
│   │   ├── api/               # REST endpoints (/api/detect, /api/risk, /api/capa, /health)
│   │   ├── capa/              # CAPA clustering, narrative drafting, and PDF/MD export
│   │   ├── config/            # Settings and risk_weights.json configuration
│   │   ├── detection/         # Deterministic deviation engine & severity classifier
│   │   ├── mcp_server/        # Model Context Protocol JSON-RPC tools & server
│   │   ├── models/            # SQLAlchemy models (Site, Patient, Visit, Deviation, etc.)
│   │   ├── risk/              # Deterministic 7-factor site risk scoring engine
│   │   ├── llm_client.py      # WatsonxLLMClient and MockLLMClient abstractions
│   │   └── seed.py            # Synthetic clinical trial data generator
│   ├── frontend/              # React 18 + Vite clinical dashboard
│   │   └── src/components/    # RiskHeatmapView, DeviationsView, ChatPanel, CAPA modal
│   └── .env.example           # Backend environment variable template
├── docs/                      # Comprehensive documentation
│   ├── problem-statement.md   # Clinical background and regulatory challenges
│   ├── solution-overview.md   # Architectural overview and design decisions
│   ├── architecture.md        # Technical architecture with Mermaid system diagram
│   └── setup-guide.md         # Tested installation, run, and troubleshooting guide
├── demo/                      # Demo artifacts
│   ├── demo-video-link.txt    # Link to walkthrough demonstration video
│   ├── live-demo-url.txt      # Link to deployed application (or localhost instructions)
│   └── screenshots/           # Application screenshots
├── presentation/              # Hackathon slide deck
│   └── README.md              # Slide deck guide
├── tests/                     # 107 passing automated tests
└── submission.yaml            # Machine-readable submission metadata
```

---

## ⚡ How to Run

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ and npm

### 2. Backend Setup
```bash
# Clone the repository
git clone https://github.com/kushalvk/bob-ai-hackathon-AutoGen.git
cd bob-ai-hackathon-AutoGen

# Install backend dependencies
pip install -r requirements.txt

# Seed the database with synthetic protocol, sites, and deviations
python -m src.backend.seed

# Start the FastAPI backend server (Terminal 1)
python -m uvicorn src.backend.main:app --reload --port 8000
```

### 3. Frontend Setup
```bash
# In a second terminal:
cd src/frontend
npm install
npm run dev
```

- **Frontend Dashboard**: [http://localhost:5173](http://localhost:5173)
- **FastAPI Interactive Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Backend Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

### 4. Run Automated Tests
```bash
python -m pytest tests/ -v
```

---

## 🖥️ Demo

| Artifact | Link |
|---|---|
| 📹 Demo Video | [See demo/demo-video-link.txt](demo/demo-video-link.txt) |
| 🌐 Live Demo | [See demo/live-demo-url.txt](demo/live-demo-url.txt) |
| 🖼️ Screenshots | [See demo/screenshots/](demo/screenshots/) |
| 📊 Presentation | [See presentation/](presentation/) |

---

## ⚠️ Known Limitations

- **watsonx.ai API Credentials**: Generating live AI clinical rationales and root-cause narratives requires valid `WATSONX_API_KEY` and `WATSONX_PROJECT_ID` environment variables. When unconfigured, the system automatically and transparently falls back to deterministic rule tables and standard clinical CAPA templates without crashing.
- **Simulated EDC Data Feeds**: The system currently runs against reproducible synthetic trial datasets modeled after Phase II/III protocol specifications (`PROTO-001`) rather than live streaming HL7 FHIR or CDISC ODM clinical endpoints.
- **PDF Styling**: Generated CAPA PDFs use standard Helvetica core fonts. Custom clinical sponsor letterhead and logos require local image placement in the asset directory.

---

## 🏅 What We're Most Proud Of

**Zero Hallucination Compliance Core**:
We refused to let an LLM "guess" or "estimate" protocol deviations or site risk scores. All deviation detection, 7-factor mathematical risk calculations, and evidence indexing are **100% deterministic, transparent, and covered by 107 automated unit tests**. 

Generative AI (IBM watsonx.ai) is confined strictly to its natural strength: drafting articulate clinical rationales and regulatory action items. Furthermore, by implementing the **Model Context Protocol (MCP)**, conversational assistants retrieve mathematically verified site metrics and deviation audits with zero risk of confabulation.
