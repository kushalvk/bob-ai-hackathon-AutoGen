"""Model Context Protocol (MCP) server for ClinGuard AI.

Provides standard MCP tool registration, JSON-RPC 2.0 message handling,
and stdio transport for integration with AI assistants, LLM frameworks,
and chat interfaces (e.g. Claude Desktop, Cursor, AutoGen).
"""

import json
import logging
import sys
from typing import Any, Callable, Dict, List, Optional

from src.backend.mcp_server.tools import (
    RUN_DEVIATION_DETECTION_SCHEMA,
    GET_SITE_RISK_SCORES_SCHEMA,
    GET_DEVIATIONS_SCHEMA,
    GENERATE_OR_FETCH_CAPA_SCHEMA,
    run_deviation_detection,
    get_site_risk_scores,
    get_deviations,
    generate_or_fetch_capa,
)

logger = logging.getLogger(__name__)

# Server Metadata
SERVER_NAME = "clinguard-ai-mcp-server"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2024-11-05"

# Registry of available tools and their underlying execution handlers
TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "run_deviation_detection": {
        "schema": RUN_DEVIATION_DETECTION_SCHEMA,
        "handler": run_deviation_detection,
    },
    "get_site_risk_scores": {
        "schema": GET_SITE_RISK_SCORES_SCHEMA,
        "handler": get_site_risk_scores,
    },
    "get_deviations": {
        "schema": GET_DEVIATIONS_SCHEMA,
        "handler": get_deviations,
    },
    "generate_or_fetch_capa": {
        "schema": GENERATE_OR_FETCH_CAPA_SCHEMA,
        "handler": generate_or_fetch_capa,
    },
}


def list_tools() -> List[Dict[str, Any]]:
    """Return list of registered MCP tools and their JSON schemas.

    Returns:
        List[Dict[str, Any]]: Array of tool schema definitions formatted
        for the MCP `tools/list` protocol method.
    """
    tools = []
    for entry in TOOL_REGISTRY.values():
        schema = entry["schema"]
        tools.append({
            "name": schema["name"],
            "description": schema["description"],
            "inputSchema": schema["inputSchema"],
            "outputSchema": schema.get("outputSchema", {}),
        })
    return tools


def call_tool(name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Execute a registered tool by name with arguments and format MCP result.

    All tools execute deterministic backend logic and database operations.
    If execution fails, an error response with `isError: true` is returned.

    Args:
        name (str): Tool identifier matching a registered tool schema.
        arguments (Optional[Dict[str, Any]]): Key-value arguments matching tool inputSchema.

    Returns:
        Dict[str, Any]: MCP response payload containing:
            - content: List of text content objects with JSON serialized results
            - structuredContent: Raw result dict for direct Python callers
            - isError: Boolean indicating whether execution raised an error
    """
    if name not in TOOL_REGISTRY:
        error_msg = f"Unknown tool: '{name}'. Available tools: {list(TOOL_REGISTRY.keys())}"
        logger.error(error_msg)
        return {
            "content": [{"type": "text", "text": error_msg}],
            "isError": True,
        }

    handler: Callable = TOOL_REGISTRY[name]["handler"]
    args = arguments or {}

    try:
        result = handler(**args)
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2, default=str),
                }
            ],
            "structuredContent": result,
            "isError": False,
        }
    except TypeError as te:
        error_msg = f"Invalid arguments for tool '{name}': {str(te)}"
        logger.exception(error_msg)
        return {
            "content": [{"type": "text", "text": error_msg}],
            "isError": True,
        }
    except Exception as e:
        error_msg = f"Execution error in tool '{name}': {str(e)}"
        logger.exception(error_msg)
        return {
            "content": [{"type": "text", "text": error_msg}],
            "isError": True,
        }


def handle_jsonrpc_request(request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Process a single incoming JSON-RPC 2.0 protocol message.

    Handles `initialize`, `notifications/initialized`, `ping`,
    `tools/list`, and `tools/call`.

    Args:
        request (Dict[str, Any]): Parsed JSON-RPC request dictionary.

    Returns:
        Optional[Dict[str, Any]]: JSON-RPC response dictionary, or None for notifications.
    """
    msg_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})

    # Protocol initialization
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {
                        "listChanged": False,
                    }
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                },
            },
        }

    # Post-initialization notification (no response needed)
    if method == "notifications/initialized":
        return None

    # Liveness check
    if method == "ping":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {},
        }

    # List tools
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": list_tools(),
            },
        }

    # Call a specific tool
    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        result = call_tool(tool_name, tool_args)
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": result,
        }

    # Method not found
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {
            "code": -32601,
            "message": f"Method '{method}' not recognized by ClinGuard MCP server.",
        },
    }


def run_stdio_server() -> None:
    """Run line-delimited JSON-RPC server over standard input and output streams.

    Listens for requests line-by-line from sys.stdin, executes corresponding MCP
    protocol methods, and writes JSON responses to sys.stdout.
    """
    logger.info("Starting %s v%s over stdio transport...", SERVER_NAME, SERVER_VERSION)

    for line in sys.stdin:
        line_clean = line.strip()
        if not line_clean:
            continue

        try:
            request = json.loads(line_clean)
            response = handle_jsonrpc_request(request)
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError as jde:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {str(jde)}",
                },
            }
            sys.stdout.write(json.dumps(error_response) + "\n")
            sys.stdout.flush()
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": f"Internal server error: {str(e)}",
                },
            }
            sys.stdout.write(json.dumps(error_response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    run_stdio_server()
