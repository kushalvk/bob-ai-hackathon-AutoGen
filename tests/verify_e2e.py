"""End-to-end verification script testing live API endpoints, risk scores, and exports."""

import json
import urllib.request
from src.backend.mcp_server.tools import (
    run_deviation_detection_impl,
    get_site_risk_scores_impl,
    get_deviations_impl,
    generate_or_fetch_capa_impl,
)

BASE_URL = "http://localhost:8000"


def verify_all():
    print("=" * 60)
    print("CLINGUARD AI END-TO-END VERIFICATION")
    print("=" * 60)

    # 1. Check Health
    health_resp = urllib.request.urlopen(f"{BASE_URL}/health")
    health = json.loads(health_resp.read().decode())
    print(f"1. Health Check: {health['status']} (DB: {health['database']})")
    assert health["status"] == "ok"

    # 2. Check Deviations API
    dev_resp = urllib.request.urlopen(f"{BASE_URL}/api/detect/results")
    dev_data = json.loads(dev_resp.read().decode())
    count = dev_data["count"]
    print(f"2. Deviations Found: {count}")
    assert count >= 24

    severities = {}
    types = {}
    for d in dev_data["deviations"]:
        sev = d["final_severity"]
        severities[sev] = severities.get(sev, 0) + 1
        t = d["type"]
        types[t] = types.get(t, 0) + 1

    print(f"   Severities: {severities}")
    print(f"   Types: {types}")
    assert "major" in severities and "minor" in severities

    # 3. Check Site Risk Scores
    risk_resp = urllib.request.urlopen(f"{BASE_URL}/api/risk/scores")
    risk_data = json.loads(risk_resp.read().decode())
    scores = {s["site_id"]: s["score"] for s in risk_data["scores"]}
    print(f"3. Site Risk Scores: {scores}")

    assert scores["SITE-101"] == max(scores.values()), "SITE-101 is not highest!"
    assert scores["SITE-105"] == min(scores.values()), "SITE-105 is not lowest!"
    print(f"   [PASS] SITE-101 ({scores['SITE-101']}) is highest, SITE-105 ({scores['SITE-105']}) is lowest")

    # 4. Check CAPA Reports & Export
    capa_resp = urllib.request.urlopen(f"{BASE_URL}/api/capa/reports")
    capa_data = json.loads(capa_resp.read().decode())
    capa_count = capa_data["count"]
    print(f"4. CAPA Reports Available: {capa_count}")
    assert capa_count >= 1

    first_capa = capa_data["capa_reports"][0]
    capa_id = first_capa["capa_id"]

    # Test PDF Export
    pdf_resp = urllib.request.urlopen(f"{BASE_URL}/api/capa/export/{capa_id}/pdf")
    pdf_bytes = pdf_resp.read()
    assert pdf_resp.getcode() == 200
    assert len(pdf_bytes) > 500
    print(f"   [PASS] PDF Export ({capa_id}): {len(pdf_bytes)} bytes")

    # Test Markdown Export
    md_resp = urllib.request.urlopen(f"{BASE_URL}/api/capa/export/{capa_id}/markdown")
    md_text = md_resp.read().decode()
    assert md_resp.getcode() == 200
    assert "CAPA REPORT" in md_text
    print(f"   [PASS] Markdown Export ({capa_id}): {len(md_text)} chars")

    # 5. Check MCP Server Tools
    print("5. MCP Server Tools Verification:")
    det_mcp = run_deviation_detection_impl("PROTO-001")
    assert det_mcp["status"] == "success"
    print(f"   [PASS] MCP run_deviation_detection: {det_mcp['total_deviations']} deviations")

    risk_mcp = get_site_risk_scores_impl()
    assert risk_mcp["count"] == 5
    print(f"   [PASS] MCP get_site_risk_scores: {risk_mcp['count']} sites evaluated")

    devs_mcp = get_deviations_impl(site_id="SITE-101", severity="major")
    assert devs_mcp["count"] > 0
    print(f"   [PASS] MCP get_deviations (SITE-101, major): {devs_mcp['count']} found")

    capa_mcp = generate_or_fetch_capa_impl(capa_id=capa_id)
    assert capa_mcp["status"] == "found"
    print(f"   [PASS] MCP generate_or_fetch_capa ({capa_id}): Status {capa_mcp['status']}")

    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    verify_all()
