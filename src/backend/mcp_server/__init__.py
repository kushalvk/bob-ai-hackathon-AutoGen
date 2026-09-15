"""ClinGuard AI Model Context Protocol (MCP) Server package.

Exposes deterministic clinical compliance tools (detection, risk scoring,
deviation filtering, and CAPA generation) for AI assistants and chat interfaces.
"""

from src.backend.mcp_server.server import (
    list_tools,
    call_tool,
    handle_jsonrpc_request,
    run_stdio_server,
    TOOL_REGISTRY,
)
from src.backend.mcp_server.tools import (
    run_deviation_detection,
    get_site_risk_scores,
    get_deviations,
    generate_or_fetch_capa,
)

__all__ = [
    "list_tools",
    "call_tool",
    "handle_jsonrpc_request",
    "run_stdio_server",
    "TOOL_REGISTRY",
    "run_deviation_detection",
    "get_site_risk_scores",
    "get_deviations",
    "generate_or_fetch_capa",
]
