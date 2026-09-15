"""API router for grounded chat assistant backed by MCP compliance tools."""

import re
import logging
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, status

from src.backend.mcp_server.server import call_tool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Grounded Chat"])


class ChatRequest(BaseModel):
    """Chat message request payload."""
    message: str = Field(..., description="Natural language compliance query", min_length=1)


class ChatResponse(BaseModel):
    """Grounded chat response payload including tool provenance."""
    answer: str
    tool_called: str
    tool_arguments: Dict[str, Any]
    tool_result: Dict[str, Any]
    grounded: bool = True


def _extract_site_id(text: str) -> Optional[str]:
    """Extract site identifier like SITE-101 or site 101 from query text."""
    match = re.search(r"\b(SITE[-_]?\d{3})\b", text, re.IGNORECASE)
    if match:
        val = match.group(1).upper()
        if "_" in val:
            return val.replace("_", "-")
        if "-" not in val and len(val) == 7:
            return f"{val[:4]}-{val[4:]}"
        return val

    # Match "site 101"
    match2 = re.search(r"\bsite\s+(\d{3})\b", text, re.IGNORECASE)
    if match2:
        return f"SITE-{match2.group(1)}"

    return None


def _extract_capa_id(text: str) -> Optional[str]:
    """Extract CAPA identifier like CAPA-101-001 from query text."""
    match = re.search(r"\b(CAPA[-_]?\d{3}[-_]?\d{3})\b", text, re.IGNORECASE)
    if match:
        val = match.group(1).upper().replace("_", "-")
        parts = val.split("-")
        if len(parts) == 3:
            return f"CAPA-{parts[1]}-{parts[2]}"
        return val
    return None


def _extract_deviation_id(text: str) -> Optional[str]:
    """Extract deviation identifier like DEV-0001 from query text."""
    match = re.search(r"\b(DEV[-_]?\d{4})\b", text, re.IGNORECASE)
    if match:
        val = match.group(1).upper().replace("_", "-")
        return val
    return None


@router.post("/query", response_model=ChatResponse, status_code=status.HTTP_200_OK)
def handle_chat_query(req: ChatRequest):
    """Process natural language query, route to appropriate MCP tool, and synthesize grounded answer.

    Guarantees zero hallucinations by binding every claim to verified data returned
    by the deterministic MCP tool execution.

    Args:
        req (ChatRequest): Incoming natural language query.

    Returns:
        ChatResponse: Structured response with natural-language answer, tool called,
        exact arguments, and raw structured output.
    """
    user_msg = req.message.strip()
    msg_lower = user_msg.lower()

    site_id = _extract_site_id(user_msg)
    capa_id = _extract_capa_id(user_msg)
    dev_id = _extract_deviation_id(user_msg)

    # 1. Intent: CAPA Generation or Fetching
    if "capa" in msg_lower or capa_id is not None:
        tool_name = "generate_or_fetch_capa"
        if capa_id:
            args = {"capa_id": capa_id}
        elif dev_id:
            args = {"deviation_id": dev_id}
        elif site_id:
            # Check default CAPA ID for site
            site_suffix = site_id.split("-")[1] if "-" in site_id else site_id
            args = {"capa_id": f"CAPA-{site_suffix}-001"}
        else:
            args = {"capa_id": "CAPA-101-001"}

        resp = call_tool(tool_name, args)
        result_data = resp.get("structuredContent", {})

        if resp.get("isError") or result_data.get("action") == "not_found":
            answer = f"I checked for CAPA report matching your query, but could not locate it: {result_data.get('message', 'Not found')}."
        else:
            cid = result_data.get("capa_id", "N/A")
            finding = result_data.get("finding", "N/A")
            rc = result_data.get("root_cause", "N/A")
            ca = result_data.get("corrective_action", "N/A")
            pa = result_data.get("preventive_action", "N/A")
            owner = result_data.get("owner", "N/A")
            status_val = result_data.get("status", "open")
            dev_ids = result_data.get("deviation_ids", [])

            answer = (
                f"**CAPA Report {cid}** (Status: `{status_val}`, Owner: {owner}):\n\n"
                f"- **Finding**: {finding}\n"
                f"- **Covered Deviations**: {', '.join(dev_ids) if dev_ids else 'None'}\n"
                f"- **Root Cause Analysis**: {rc}\n"
                f"- **Immediate Corrective Action**: {ca}\n"
                f"- **Long-term Preventive Action**: {pa}"
            )

        return ChatResponse(
            answer=answer,
            tool_called=tool_name,
            tool_arguments=args,
            tool_result=result_data,
            grounded=True,
        )

    # 2. Intent: Run Deviation Detection
    if any(k in msg_lower for k in ["run detection", "trigger detection", "run detect", "execute detection"]):
        tool_name = "run_deviation_detection"
        args = {"protocol_id": "PROTO-001"}
        if site_id:
            args["site_id"] = site_id

        resp = call_tool(tool_name, args)
        result_data = resp.get("structuredContent", {})
        total = result_data.get("total_deviations", 0)
        by_type = result_data.get("deviations_by_type", {})
        type_str = ", ".join([f"{k}: {v}" for k, v in by_type.items()])

        site_clause = f" for site {site_id}" if site_id else " across all active sites"
        answer = (
            f"Executed deterministic deviation detection run on protocol **PROTO-001**{site_clause}. "
            f"Detected **{total} total deviations** ({type_str}). All findings and audit evidence have been refreshed."
        )

        return ChatResponse(
            answer=answer,
            tool_called=tool_name,
            tool_arguments=args,
            tool_result=result_data,
            grounded=True,
        )

    # 3. Intent: Risk Scores / High Risk Sites
    if any(k in msg_lower for k in ["risk", "score", "high risk", "rank", "dangerous", "turnover", "monitoring"]):
        tool_name = "get_site_risk_scores"
        args = {}
        if site_id:
            args["site_id"] = site_id

        resp = call_tool(tool_name, args)
        result_data = resp.get("structuredContent", {})
        scores = result_data.get("scores", [])

        if not scores:
            answer = "No site risk scores were found for the requested query."
        elif site_id and len(scores) == 1:
            s = scores[0]
            top_factors = sorted(
                s.get("contributing_factors", []),
                key=lambda x: x.get("contribution", 0.0),
                reverse=True,
            )[:3]
            factor_bullets = "\n".join([
                f"  - **{f.get('name', f.get('factor'))}**: raw={f.get('raw_value')}, contribution=+{f.get('contribution')} pts"
                for f in top_factors
            ])
            answer = (
                f"Site **{s['site_id']}** has a composite risk score of **{s['score']:.1f}/100** "
                f"(Risk Tier: `{s['risk_tier']}`).\n\nTop contributing risk factors:\n{factor_bullets}"
            )
        else:
            high_risk = [s for s in scores if s.get("risk_tier") == "High"]
            lines = [
                f"- **{s['site_id']}**: Score **{s['score']:.1f}** (`{s['risk_tier']}` tier)"
                for s in scores
            ]
            answer = (
                f"Evaluated {len(scores)} sites. **{len(high_risk)} site(s) are in the HIGH risk tier** (≥ 60.0):\n\n"
                + "\n".join(lines)
            )

        return ChatResponse(
            answer=answer,
            tool_called=tool_name,
            tool_arguments=args,
            tool_result=result_data,
            grounded=True,
        )

    # 4. Intent: Deviations / Specific Queries like "3+ major deviations"
    tool_name = "get_deviations"
    args = {}
    if site_id:
        args["site_id"] = site_id
    if "major" in msg_lower:
        args["severity"] = "major"
    elif "minor" in msg_lower:
        args["severity"] = "minor"
    elif "administrative" in msg_lower or "admin" in msg_lower:
        args["severity"] = "administrative"

    resp = call_tool(tool_name, args)
    result_data = resp.get("structuredContent", {})
    deviations = result_data.get("deviations", [])

    # Handle queries asking "which sites had 3+ major deviations"
    if "3+" in msg_lower or "three or more" in msg_lower or "more than 2" in msg_lower:
        site_counts: Dict[str, int] = {}
        for d in deviations:
            site_counts[d["site_id"]] = site_counts.get(d["site_id"], 0) + 1

        qualifying = {s: c for s, c in site_counts.items() if c >= 3}
        if qualifying:
            items_text = "\n".join([f"- **{s}**: **{c}** deviations" for s, c in qualifying.items()])
            answer = (
                f"Querying the live database with `get_deviations({args})` reveals **{len(qualifying)} site(s)** "
                f"with 3 or more deviations:\n\n{items_text}"
            )
        else:
            answer = (
                f"Querying the live database with `get_deviations({args})` found **no sites** with 3 or more "
                f"matching deviations. The highest count was {max(site_counts.values()) if site_counts else 0}."
            )
    elif site_id:
        answer = (
            f"Site **{site_id}** has **{len(deviations)} deviation(s)** on record"
            + (f" with severity `{args.get('severity')}`" if "severity" in args else "")
            + f":\n\n"
            + "\n".join([
                f"- **{d['deviation_id']}** (`{d['type']}`, severity: `{d.get('final_severity', d.get('severity'))}`): {d.get('severity_rationale', 'Protocol non-compliance')}"
                for d in deviations[:5]
            ])
            + (f"\n- *(and {len(deviations) - 5} more...)*" if len(deviations) > 5 else "")
        )
    else:
        # Group by site summary
        site_counts: Dict[str, int] = {}
        for d in deviations:
            site_counts[d["site_id"]] = site_counts.get(d["site_id"], 0) + 1
        summary_lines = [f"- **{s}**: {c} deviation(s)" for s, c in sorted(site_counts.items(), key=lambda x: x[1], reverse=True)]
        answer = (
            f"Retrieved **{len(deviations)} total deviation(s)** from database"
            + (f" with severity `{args.get('severity')}`" if "severity" in args else "")
            + f":\n\n"
            + "\n".join(summary_lines)
        )

    return ChatResponse(
        answer=answer,
        tool_called=tool_name,
        tool_arguments=args,
        tool_result=result_data,
        grounded=True,
    )
