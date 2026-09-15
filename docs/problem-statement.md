# Problem Statement

## Background

A major clinical trial generates **5,000+ patient visits across 200+ investigation sites** worldwide. Each visit must comply with a legally binding clinical protocol specifying exact dosing schedules, visit windows, prohibited concomitant medications, and eligibility criteria under ICH E6 Good Clinical Practice (GCP) guidelines.

---

## The Problem

**Protocol deviations — missed visits, wrong dosing, banned co-medications — go undetected until the FDA audit.** Clinical Research Associates (CRAs) manually compare patient records against protocol specifications weeks or months after visits occur, allowing critical non-compliances to accumulate silently across sites.

A single rejected submission due to protocol non-compliance **delays drug approval by 6–12 months and costs $50–100M**. Meanwhile, risk managers lack real-time visibility into which sites carry the highest operational risk before problems escalate into regulatory findings.

---

## Who is Affected

- **Sponsor Risk Managers & Quality Assurance**: Need real-time site-level risk visibility to prioritize monitoring resources before audit findings, not after.
- **Clinical Research Associates (CRAs)**: Overwhelmed by manual source data verification across hundreds of sites, unable to focus on the highest-risk locations.
- **Regulatory Affairs & Trial Leadership**: Bear legal and financial accountability when FDA inspections surface systemic protocol non-compliance that could have been caught earlier.
- **Patients**: Exposed to potential safety risks (wrong doses, contraindicated drug interactions) when deviations go undetected.

---

## Why It Matters

- **Financial Impact**: A rejected FDA submission costs **$50–100M** in delayed revenue and extended trial operations. Individual deviation remediation costs $1,500–$5,000 per occurrence.
- **Regulatory Risk**: 68% of FDA Bioresearch Monitoring (BIMO) inspection findings stem from protocol non-compliance and delayed corrective action.
- **Patient Safety**: Undetected dosing errors and banned co-medication interactions directly endanger enrolled participants.
- **Trial Integrity**: Accumulated deviations introduce statistical bias that can invalidate years of clinical research.

---

## Why Existing Solutions Fall Short

1. **Retrospective Detection**: Current systems rely on periodic manual audits, catching deviations months after they occur rather than in real time.
2. **No Severity Classification**: Existing tools flag deviations but don't classify them by ICH E6 GCP severity (major/minor/administrative), forcing manual clinical judgment at scale.
3. **Subjective Risk Scoring**: Site risk assessments use qualitative questionnaires rather than quantitative leading indicators computed from operational data.
4. **No Automated CAPA Generation**: Corrective and Preventive Action reports are drafted manually, delaying the regulatory response cycle.

---

## The Challenge

> **Build a Bob solution that compares patient records against the protocol specification, classifies each deviation by severity (ICH E6 GCP: major/minor/administrative), scores site-level risk using leading indicators, and generates CAPA-ready reports with recommended mitigations.**
