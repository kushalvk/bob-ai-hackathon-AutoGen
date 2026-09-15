# Architecture

## System Architecture

ClinGuard AI provides real-time clinical trial compliance monitoring, deterministic protocol deviation detection, quantitative site risk scoring, and automated Corrective and Preventive Action (CAPA) report generation.

To enable natural-language chat assistants and agentic workflows without hallucinating compliance figures, ClinGuard AI exposes its deterministic backend capabilities via a Model Context Protocol (MCP) server.

```mermaid
graph TD
    User[User / Clinical Monitor] -->|Natural Language| Chat[Chat Interface / LLM Assistant]
    Chat -->|MCP JSON-RPC 2.0| MCPServer[ClinGuard MCP Server\nsrc/backend/mcp_server]
    
    subgraph "Deterministic Backend Layer (No LLM Guessing)"
        MCPServer -->|Tool Call| DetectEngine[Deviation Detection Engine\nsrc/backend/detection]
        MCPServer -->|Tool Call| RiskEngine[Site Risk Scoring Engine\nsrc/backend/risk]
        MCPServer -->|Tool Call| CAPAGen[CAPA Report Generator\nsrc/backend/capa]
        MCPServer -->|Direct SQL Filter| DB[(Database / SQLite / PostgreSQL)]
    end

    subgraph "Narrow LLM Narrative Boundary"
        CAPAGen -.->|Draft 3 Narrative Fields Only\n(Root Cause, Corrective, Preventive)| LLM[watsonx.ai / MockLLM]
        DetectEngine -.->|Review Ambiguous Severity| LLM
    end

    subgraph "REST API & Export Services"
        FastAPI[FastAPI Backend\nsrc/backend/api] --> DB
        FastAPI --> CAPAExport[Markdown & PDF Exporter]
    end
```

---

## Components

| Component | Technology | Responsibility |
|---|---|---|
| **MCP Server** | Python / JSON-RPC 2.0 / stdio | Exposes deterministic compliance tools for AI agents and chat interfaces |
| **Deviation Detection Engine** | Python / SQLAlchemy | Pure rule-based detection of visit schedule, dosing, concomitant medications, and eligibility breaches |
| **Site Risk Scoring Engine** | Python / NumPy / SciPy | 7-factor weighted statistical risk scoring (0–100) combining deviations and operational metrics |
| **CAPA Report Generator** | Python / SQLAlchemy / fpdf2 | Clusters related deviations by site, type, and 30-day window; compiles findings and exports to Markdown/PDF |
| **LLM Narrative Boundary** | IBM watsonx.ai / MockLLM | Strictly isolated LLM drafting of narrative root causes and ambiguous severity classifications |
| **Backend API** | FastAPI / Uvicorn | RESTful endpoints for detection runs, risk score computing, and CAPA export |
| **Database** | SQLite / PostgreSQL | Persists protocols, sites, patient records, visits, deviations, risk scores, and CAPA reports |

---

## Model Context Protocol (MCP) Tool Interface

The ClinGuard AI MCP server (`src/backend/mcp_server/`) provides four deterministic tools for AI assistants. These tools guarantee zero-hallucination compliance queries by delegating directly to verified database queries and mathematical engines.

### Tool Overview

| Tool Name | Key Parameters | Description |
|---|---|---|
| `run_deviation_detection` | `protocol_id` (str), `site_id` (optional str) | Runs the detection engine against visit records and returns audit-backed deviation findings. |
| `get_site_risk_scores` | `site_id` (optional str) | Returns current 0–100 composite risk scores, risk tier (`High`/`Medium`/`Low`), and 7-factor transparent breakdowns. |
| `get_deviations` | `site_id` (optional), `severity` (optional), `date_range` (optional) | Queryable deviation search filtering by site, severity grade, and detection dates. |
| `generate_or_fetch_capa` | `capa_id` (optional), `deviation_id` (optional) | Retrieves an existing CAPA report or generates a new one addressing a specific deviation. |

---

### Tool 1: `run_deviation_detection`

Executes the protocol deviation engine against patient visit records and persists/returns detected breaches.

#### Input Schema
```json
{
  "type": "object",
  "properties": {
    "protocol_id": {
      "type": "string",
      "default": "PROTO-001",
      "description": "Unique identifier of the clinical protocol to evaluate."
    },
    "site_id": {
      "type": "string",
      "description": "Optional site ID filter (e.g. 'SITE-101') to restrict returned deviations."
    }
  },
  "required": ["protocol_id"]
}
```

#### Example JSON-RPC Request
```json
{
  "jsonrpc": "2.0",
  "id": 101,
  "method": "tools/call",
  "params": {
    "name": "run_deviation_detection",
    "arguments": {
      "protocol_id": "PROTO-001",
      "site_id": "SITE-101"
    }
  }
}
```

#### Example Output Payload
```json
{
  "protocol_id": "PROTO-001",
  "site_id_filter": "SITE-101",
  "total_deviations": 6,
  "deviations_by_type": {
    "missed_visit": 2,
    "wrong_dose": 2,
    "banned_comed": 1,
    "documentation": 1
  },
  "deviations": [
    {
      "deviation_id": "DEV-0001",
      "record_id": "REC-0012",
      "site_id": "SITE-101",
      "type": "banned_comed",
      "severity": "major",
      "final_severity": "major",
      "severity_rationale": "Prohibited concomitant medication Simvastatin administered. Impacts patient safety per ICH E6(R2).",
      "severity_source": "deterministic",
      "evidence": {
        "field": "concomitant_medications",
        "expected": "No prohibited statin therapy",
        "actual": "Simvastatin 40mg",
        "delta": "Drug match found in prohibited medication formulary"
      },
      "detected_at": "2026-09-02T14:30:00"
    }
  ]
}
```

---

### Tool 2: `get_site_risk_scores`

Retrieves multi-factor weighted site risk evaluations (0–100 scale) and transparent factor contributions.

#### Input Schema
```json
{
  "type": "object",
  "properties": {
    "site_id": {
      "type": "string",
      "description": "Optional site ID (e.g. 'SITE-101'). If omitted, returns scores for all sites."
    }
  }
}
```

#### Example JSON-RPC Request
```json
{
  "jsonrpc": "2.0",
  "id": 102,
  "method": "tools/call",
  "params": {
    "name": "get_site_risk_scores",
    "arguments": {
      "site_id": "SITE-101"
    }
  }
}
```

#### Example Output Payload
```json
{
  "count": 1,
  "site_id_filter": "SITE-101",
  "scores": [
    {
      "score_id": "RISK-101-20260915",
      "site_id": "SITE-101",
      "score": 78.45,
      "risk_tier": "High",
      "computed_at": "2026-09-15T10:00:00",
      "contributing_factors": [
        {
          "factor": "major_deviation_rate",
          "name": "Major Deviation Rate",
          "weight": 0.30,
          "raw_value": 0.571,
          "normalized_score": 85.6,
          "contribution": 25.68
        },
        {
          "factor": "staff_turnover_rate",
          "name": "Staff Turnover Rate",
          "weight": 0.15,
          "raw_value": 0.40,
          "normalized_score": 80.0,
          "contribution": 12.00
        },
        {
          "factor": "query_resolution_time",
          "name": "Query Resolution Time",
          "weight": 0.10,
          "raw_value": 14.5,
          "normalized_score": 72.5,
          "contribution": 7.25
        }
      ]
    }
  ]
}
```

---

### Tool 3: `get_deviations`

Filters existing deviation records by site, severity grade, or detection date range.

#### Input Schema
```json
{
  "type": "object",
  "properties": {
    "site_id": {
      "type": "string",
      "description": "Filter deviations to a specific site (e.g. 'SITE-101')."
    },
    "severity": {
      "type": "string",
      "enum": ["major", "minor", "administrative"],
      "description": "Filter by assigned severity grade."
    },
    "date_range": {
      "type": "object",
      "description": "Filter by detection timestamp interval (inclusive).",
      "properties": {
        "start_date": {
          "type": "string",
          "description": "Earliest detection date in ISO format (YYYY-MM-DD)."
        },
        "end_date": {
          "type": "string",
          "description": "Latest detection date in ISO format (YYYY-MM-DD)."
        }
      }
    }
  }
}
```

#### Example JSON-RPC Request
```json
{
  "jsonrpc": "2.0",
  "id": 103,
  "method": "tools/call",
  "params": {
    "name": "get_deviations",
    "arguments": {
      "site_id": "SITE-101",
      "severity": "major"
    }
  }
}
```

#### Example Output Payload
```json
{
  "count": 3,
  "filters_applied": {
    "site_id": "SITE-101",
    "severity": "major",
    "date_range": null
  },
  "deviations": [
    {
      "deviation_id": "DEV-0001",
      "site_id": "SITE-101",
      "type": "banned_comed",
      "severity": "major",
      "final_severity": "major",
      "severity_rationale": "Prohibited concomitant medication Simvastatin administered.",
      "severity_source": "deterministic",
      "evidence": { "field": "concomitant_medications" },
      "detected_at": "2026-09-02T14:30:00"
    }
  ]
}
```

---

### Tool 4: `generate_or_fetch_capa`

Retrieves an existing CAPA report by ID, or fetches/creates a CAPA report addressing a specific deviation ID.

#### Input Schema
```json
{
  "type": "object",
  "properties": {
    "capa_id": {
      "type": "string",
      "description": "Primary key ID of an existing CAPA report (e.g. 'CAPA-101-001')."
    },
    "deviation_id": {
      "type": "string",
      "description": "Deviation ID (e.g. 'DEV-0001') to locate or generate a CAPA report for."
    }
  }
}
```

#### Example JSON-RPC Request
```json
{
  "jsonrpc": "2.0",
  "id": 104,
  "method": "tools/call",
  "params": {
    "name": "generate_or_fetch_capa",
    "arguments": {
      "capa_id": "CAPA-101-001"
    }
  }
}
```

#### Example Output Payload
```json
{
  "action": "fetched_by_capa_id",
  "capa_id": "CAPA-101-001",
  "deviation_ids": ["DEV-0001", "DEV-0004"],
  "finding": "2 deviations of type 'banned_comed' at site SITE-101 between 2026-09-01 and 2026-09-10. Highest severity: major.",
  "severity": "major",
  "severity_rationale": "Impacts patient safety per ICH E6(R2).",
  "root_cause": "High staff turnover (40%) led to inadequate coordinator onboarding and protocol adherence.",
  "corrective_action": "Re-train all site clinical research coordinators on protocol eligibility, dosing schedules, and prohibited comed logs.",
  "preventive_action": "Implement mandatory pre-screening checklist and double-check signoff for dose administration.",
  "owner": "Quality Assurance Manager (Dr. E. Vance)",
  "due_date": "2026-10-15",
  "status": "open",
  "message": "Successfully retrieved CAPA report 'CAPA-101-001'."
}
```

---

## Security Considerations

- **API Keys**: All LLM and IBM watsonx.ai credentials (`WATSONX_API_KEY`, `WATSONX_PROJECT_ID`) reside in environment variables and are excluded from git.
- **Pure Deterministic Boundaries**: The MCP server guarantees that all numerical computations, risk thresholds, and deviation detections originate directly from validated backend services.
- **Audit Trails**: Every deviation maintains explicit `severity_source` tags (`deterministic` vs. `llm_override`) and verbatim rationale citations referencing ICH E6(R2) principles.
