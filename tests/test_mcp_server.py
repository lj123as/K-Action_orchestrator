# -*- coding: utf-8 -*-
"""The Action Operation MCP adapter is a transport over action_ops, not a second implementation."""
import json
import subprocess
import sys
from pathlib import Path


SERVER = Path(__file__).resolve().parents[1] / "mcp" / "server.py"


def call(*messages):
    proc = subprocess.run(
        [sys.executable, str(SERVER)],
        input="\n".join(json.dumps(message) for message in messages) + "\n",
        capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    return [json.loads(line) for line in (proc.stdout or "").splitlines() if line.strip()]


def test_initialize_reports_this_component_as_the_server():
    responses = call({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})

    assert responses[0]["result"]["serverInfo"]["name"] == "action-orchestrator"


def test_tools_list_is_the_action_operation_entry():
    responses = call({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    assert [tool["name"] for tool in responses[0]["result"]["tools"]] == [
        "action_request", "action_update_component"]


def test_an_unknown_operation_is_an_error_result_not_a_crash():
    responses = call({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                      "params": {"name": "action_request",
                                 "arguments": {"operation": "explode", "request": ""}}})

    result = responses[0]["result"]
    assert result["isError"] is True
    assert "unknown operation: explode" in result["content"][0]["text"]


def test_a_tool_this_component_does_not_own_is_not_served_here():
    """Knowledge Network's tools belong to its own adapter; this surface must not grow them."""
    responses = call({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                      "params": {"name": "kn_propose", "arguments": {}}})

    result = responses[0]["result"]
    assert result["isError"] is True
    assert "unknown tool: kn_propose" in result["content"][0]["text"]
