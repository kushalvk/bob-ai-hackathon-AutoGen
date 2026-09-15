# Solution Overview

## What We Built

**ClinGuard AI** is an autonomous protocol compliance monitoring, quantitative site risk scoring, and automated Corrective and Preventive Action (CAPA) platform for clinical trials. 

By enforcing a strict boundary between deterministic rule evaluation and generative artificial intelligence, ClinGuard AI guarantees that all compliance checks, risk scores, and evidence trails are 100% accurate and mathematically reproducible. Generative AI (powered by **IBM watsonx.ai**) is utilized strictly where human synthesis is needed: drafting regulatory narratives and root-cause rationales citing international Good Clinical Practice (ICH E6(R2)) standards.

---

## How It Works

```
[Electronic Data Capture / Visit Records] 
                    │
                    ▼
┌────────────────────────────────────────────────────────┐
│  1. Deterministic Protocol Deviation Engine            │
│     - Schedule window violations                       │
│     - Weight/milestone dosing deviations               │
│     - Prohibited concomitant drug cross-referencing    │
│     - Eligibility criteria lab breaches                │
│     - Coordinator documentation & signature gaps       │
└───────────────────┬────────────────────────────────────┘
                    │ Candidate Deviations + Evidence
                    ▼
┌────────────────────────────────────────────────────────┐
│  2. Hybrid Severity Classification                     │
│     - Deterministic ICH E6(R2) rules table             │
│     - IBM watsonx.ai Granite review for borderline     │
│       cases with cited regulatory rationale            │
└───────────────────┬────────────────────────────────────┘
                    │ Classified Deviations
                    ▼
┌────────────────────────────────────────────────────────┐
│  3. Deterministic 7-Factor Site Risk Scoring Engine    │
│     - Major deviation frequency (30%)                  │
│     - Query resolution latency (15%)                   │
│     - Trajectory trend (15%)                           │
│     - Staff turnover rate (10%)                        │
│     - Enrollment target deficit (10%)                  │
│     - CRA monitoring visit recency (10%)               │
│     - Minor/administrative gap frequency (10%)         │
│     => Standardized 0–100 site risk score              │
└───────────────────┬────────────────────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────────────────────┐
│  4. Automated CAPA Clustering & Dual-Format Export     │
│     - Cluster deviations within 30-day temporal windows│
│     - Synthesize root cause & preventive interventions │
│     - Export to Markdown & signed regulatory PDF       │
└───────────────────┬────────────────────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────────────────────┐
│  5. Model Context Protocol (MCP) Interface & UI        │
│     - React 18 / Vite Interactive Heatmap Dashboard    │
│     - Zero-hallucination conversational chat assistant │
│       via 4 deterministic MCP JSON-RPC compliance tools│
└────────────────────────────────────────────────────────┘
```

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| **Zero LLM in Core Math & Detection** | Regulatory bodies (FDA, EMA) mandate deterministic audit trails. Mathematical scoring and rule matching must never hallucinate or change answers arbitrarily. |
| **Hybrid Severity Layer** | Routine deviations (e.g., banned co-meds) are unambiguously Major. LLM review is reserved only for edge cases (e.g., borderline 15% dose adjustments) to optimize compute and cost. |
| **Model Context Protocol (MCP) Integration** | Exposes deterministic compliance capabilities to AI chat agents via standard JSON-RPC 2.0 schemas, preventing conversational assistants from inventing trial statistics. |
| **Automated 30-Day CAPA Clustering** | Rather than generating disjointed CAPA reports for individual records, deviations are grouped by site and clinical category within 30-day rolling windows to identify systemic root causes. |
| **Dual Markdown and PDF Export** | Markdown enables fast version-controlled documentation for trial master files (TMF), while formatted PDF supports executive sign-off and regulatory submission. |

---

## IBM Technologies Used

- **IBM watsonx.ai (`ibm/granite-13b-instruct-v2`)**:
  - **Clinical Severity Rationale**: Analyzes patient context, dosing delta, and protocol specifications for ambiguous deviations to draft rationales citing ICH E6(R2) Section 5.20.
  - **CAPA Narrative Synthesis**: Synthesizes root causes, corrective actions, and preventive measures from clustered deviation evidence logs.
  - **Fail-Safe Fallback**: Integrated through an abstract `BaseLLMClient` with graceful deterministic fallback when live credentials are absent.
- **IBM Bob**:
  - Leveraged as an advanced agentic pair-programmer to architect, code, test, and document the entire ClinGuard AI platform end-to-end.
