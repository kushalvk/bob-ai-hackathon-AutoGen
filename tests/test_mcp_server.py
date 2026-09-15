"""Integration tests for the ClinGuard AI MCP Server.

Validates that each MCP tool directly delegates to existing backend modules,
returns deterministic data consistent with the seeded database, and adheres
to Model Context Protocol (MCP) JSON-RPC schemas and response conventions.
"""

import json
from typing import Any, Dict

from src.backend.mcp_server import (
    list_tools,
    call_tool,
    handle_jsonrpc_request,
    run_deviation_detection,
    get_site_risk_scores,
    get_deviations,
    generate_or_fetch_capa,
)
from src.backend.database import SessionLocal
from src.backend.models import Deviation, CAPAReport, SiteRiskScore


# ---------------------------------------------------------------------------
# 1. Tool Schemas and Registry Validation
# ---------------------------------------------------------------------------

class TestMCPToolSchemas:
    """Validate MCP tool definitions and JSON schema conformance."""

    def test_all_required_tools_registered(self):
        """Verify that all four required tools are registered with valid schemas."""
        tools = list_tools()
        tool_names = {t["name"] for t in tools}

        expected_tools = {
            "run_deviation_detection",
            "get_site_risk_scores",
            "get_deviations",
            "generate_or_fetch_capa",
        }
        assert expected_tools.issubset(tool_names), (
            f"Missing required tools: {expected_tools - tool_names}"
        )

    def test_tool_schemas_have_required_metadata(self):
        """Ensure every tool schema contains descriptions, inputSchema, and outputSchema."""
        tools = list_tools()
        for t in tools:
            assert "name" in t and len(t["name"]) > 0
            assert "description" in t and len(t["description"]) > 10
            assert "inputSchema" in t
            assert t["inputSchema"].get("type") == "object"
            assert "outputSchema" in t
            assert t["outputSchema"].get("type") == "object"


# ---------------------------------------------------------------------------
# 2. run_deviation_detection Tool Tests
# ---------------------------------------------------------------------------

class TestRunDeviationDetectionTool:
    """Verify run_deviation_detection against seeded protocol and site data."""

    def test_run_detection_returns_seeded_deviations(self):
        """Executing detection on PROTO-001 returns all planted protocol deviations."""
        result = run_deviation_detection(protocol_id="PROTO-001")

        assert result["protocol_id"] == "PROTO-001"
        assert result["total_deviations"] > 0
        assert len(result["deviations"]) == result["total_deviations"]

        # Ensure all 5 deviation categories are detected
        types_detected = set(result["deviations_by_type"].keys())
        expected_types = {"missed_visit", "wrong_dose", "banned_comed", "eligibility_breach", "documentation"}
        assert expected_types.issubset(types_detected), (
            f"Detection run missed categories: {expected_types - types_detected}"
        )

        # Validate deviation item schema
        first = result["deviations"][0]
        assert "deviation_id" in first
        assert "site_id" in first
        assert "type" in first
        assert "severity" in first
        assert "evidence" in first
        assert isinstance(first["evidence"], dict)

    def test_run_detection_with_site_filter(self):
        """Filtering detection by site_id returns only deviations for that site."""
        result = run_deviation_detection(protocol_id="PROTO-001", site_id="SITE-101")

        assert result["site_id_filter"] == "SITE-101"
        for dev in result["deviations"]:
            assert dev["site_id"] == "SITE-101"


# ---------------------------------------------------------------------------
# 3. get_site_risk_scores Tool Tests
# ---------------------------------------------------------------------------

class TestGetSiteRiskScoresTool:
    """Verify deterministic site risk scores retrieval and factor transparency."""

    def test_get_all_site_risk_scores(self):
        """Calling get_site_risk_scores without args returns all 5 seeded site scores."""
        result = get_site_risk_scores()

        assert result["count"] == 5
        assert len(result["scores"]) == 5

        site_ids = {s["site_id"] for s in result["scores"]}
        expected_sites = {"SITE-101", "SITE-102", "SITE-103", "SITE-104", "SITE-105"}
        assert site_ids == expected_sites

        for s in result["scores"]:
            assert 0.0 <= s["score"] <= 100.0
            assert s["risk_tier"] in ("High", "Medium", "Low")
            assert len(s["contributing_factors"]) == 7, "Must contain all 7 risk factors"

            # Check contributing factor breakdown fields
            factor = s["contributing_factors"][0]
            assert "factor" in factor
            assert "weight" in factor
            assert "raw_value" in factor
            assert "contribution" in factor

    def test_get_specific_site_risk_score(self):
        """Filtering by site_id returns exactly one score for that site."""
        result = get_site_risk_scores(site_id="SITE-101")

        assert result["count"] == 1
        assert result["scores"][0]["site_id"] == "SITE-101"
        assert result["site_id_filter"] == "SITE-101"


# ---------------------------------------------------------------------------
# 4. get_deviations Tool Tests
# ---------------------------------------------------------------------------

class TestGetDeviationsTool:
    """Verify flexible query filtering on deviations."""

    def test_get_all_deviations(self):
        """Querying deviations without filters returns all seeded records."""
        result = get_deviations()

        assert result["count"] >= 20
        assert len(result["deviations"]) == result["count"]

    def test_filter_by_site_id(self):
        """Querying deviations for a specific site returns only matching records."""
        result = get_deviations(site_id="SITE-101")

        assert result["count"] > 0
        assert all(d["site_id"] == "SITE-101" for d in result["deviations"])

    def test_filter_by_severity(self):
        """Querying deviations filtered by severity='major' returns only major records."""
        result = get_deviations(severity="major")

        assert result["count"] > 0
        for d in result["deviations"]:
            assert d["final_severity"].lower() == "major" or d["severity"].lower() == "major"

    def test_filter_by_date_range(self):
        """Querying deviations by date interval filters detected_at accordingly."""
        result = get_deviations(date_range={"start_date": "2026-08-01", "end_date": "2026-09-30"})

        assert result["count"] > 0
        for d in result["deviations"]:
            assert "2026-" in d["detected_at"]


# ---------------------------------------------------------------------------
# 5. generate_or_fetch_capa Tool Tests
# ---------------------------------------------------------------------------

class TestGenerateOrFetchCapaTool:
    """Verify CAPA retrieval and automated generation via MCP."""

    def test_fetch_existing_capa_by_capa_id(self):
        """Fetching a known seeded CAPA report by ID succeeds."""
        # Find a known CAPA ID from database
        db = SessionLocal()
        try:
            known_capa = db.query(CAPAReport).first()
            assert known_capa is not None, "Seeded database has no CAPA reports"
            target_id = known_capa.capa_id
        finally:
            db.close()

        result = generate_or_fetch_capa(capa_id=target_id)

        assert result["action"] == "fetched_by_capa_id"
        assert result["capa_id"] == target_id
        assert len(result["root_cause"]) > 0
        assert len(result["corrective_action"]) > 0
        assert len(result["preventive_action"]) > 0
        assert result["owner"] != ""
        assert result["status"] in ("open", "in_progress", "pending_review", "closed")

    def test_fetch_capa_by_deviation_id(self):
        """Fetching or generating a CAPA report by deviation_id succeeds."""
        db = SessionLocal()
        try:
            dev = db.query(Deviation).first()
            assert dev is not None, "Seeded database has no deviations"
            dev_id = dev.deviation_id
        finally:
            db.close()

        result = generate_or_fetch_capa(deviation_id=dev_id)

        assert result["action"] in ("fetched_existing_by_deviation", "generated_new")
        assert dev_id in result["deviation_ids"]
        assert len(result["root_cause"]) > 0
        assert len(result["corrective_action"]) > 0
        assert len(result["preventive_action"]) > 0

    def test_fetch_capa_missing_args(self):
        """Calling without capa_id or deviation_id returns not_found action with message."""
        result = generate_or_fetch_capa()
        assert result["action"] == "not_found"
        assert "must be specified" in result["message"]

    def test_fetch_nonexistent_capa(self):
        """Calling with non-existent capa_id returns not_found action."""
        result = generate_or_fetch_capa(capa_id="CAPA-999-999")
        assert result["action"] == "not_found"
        assert "not found" in result["message"].lower()


# ---------------------------------------------------------------------------
# 6. MCP Server Protocol Dispatch Tests
# ---------------------------------------------------------------------------

class TestMCPServerProtocol:
    """Test MCP protocol dispatcher and JSON-RPC 2.0 message handling."""

    def test_call_tool_dispatch_success(self):
        """call_tool executes a valid tool and formats standard MCP response."""
        response = call_tool("get_site_risk_scores", {"site_id": "SITE-101"})

        assert response["isError"] is False
        assert len(response["content"]) == 1
        assert response["content"][0]["type"] == "text"

        parsed = json.loads(response["content"][0]["text"])
        assert parsed["count"] == 1
        assert parsed["scores"][0]["site_id"] == "SITE-101"
        assert response["structuredContent"]["count"] == 1

    def test_call_tool_dispatch_unknown_tool(self):
        """Calling an unregistered tool returns isError: true."""
        response = call_tool("nonexistent_compliance_tool", {})
        assert response["isError"] is True
        assert "Unknown tool" in response["content"][0]["text"]

    def test_jsonrpc_initialize(self):
        """JSON-RPC initialize request returns server info and protocol capabilities."""
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        }
        res = handle_jsonrpc_request(req)
        assert res["id"] == 1
        assert "serverInfo" in res["result"]
        assert res["result"]["serverInfo"]["name"] == "clinguard-ai-mcp-server"
        assert "tools" in res["result"]["capabilities"]

    def test_jsonrpc_tools_list(self):
        """JSON-RPC tools/list request returns all 4 registered tools."""
        req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        res = handle_jsonrpc_request(req)
        assert res["id"] == 2
        tools = res["result"]["tools"]
        assert len(tools) == 4
        names = {t["name"] for t in tools}
        assert "run_deviation_detection" in names
        assert "get_site_risk_scores" in names

    def test_jsonrpc_tools_call(self):
        """JSON-RPC tools/call executes tool and packages result."""
        req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_deviations",
                "arguments": {"site_id": "SITE-101"},
            },
        }
        res = handle_jsonrpc_request(req)
        assert res["id"] == 3
        tool_result = res["result"]
        assert tool_result["isError"] is False
        assert len(tool_result["content"]) == 1
