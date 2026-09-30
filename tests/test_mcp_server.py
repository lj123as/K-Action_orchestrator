# -*- coding: utf-8 -*-
"""The Action Operation MCP adapter is a transport over action_ops, not a second implementation."""
import json
import subprocess
import sys
from pathlib import Path


SERVER = Path(__file__).resolve().parents[1] / "mcp" / "server.py"
VAULT = Path(__file__).resolve().parents[3]


def call(*messages, env=None):
    import os
    run_env = dict(os.environ, KA_VAULT_ROOT=str(VAULT), **(env or {}))
    proc = subprocess.run(
        [sys.executable, str(SERVER)],
        input="\n".join(json.dumps(message) for message in messages) + "\n",
        capture_output=True, text=True, encoding="utf-8", timeout=120,
        env=run_env,
    )
    return [json.loads(line) for line in (proc.stdout or "").splitlines() if line.strip()]


def test_initialize_reports_this_component_as_the_server():
    responses = call({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})

    assert responses[0]["result"]["serverInfo"]["name"] == "action-orchestrator"


def test_tools_list_is_the_action_operation_entry():
    responses = call({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    assert [tool["name"] for tool in responses[0]["result"]["tools"]] == [
        "action_request", "action_update_component",
        "action_registry_catalog", "action_reconcile"]


def test_registry_catalog_lists_the_declared_action_types():
    responses = call({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                      "params": {"name": "action_registry_catalog", "arguments": {}}})

    payload = json.loads(responses[0]["result"]["content"][0]["text"])
    assert payload["exit"] == 0, payload
    assert {item["id"] for item in payload["action_types"]} >= {"software", "harness", "human"}


def test_reconcile_previews_by_default_and_writes_only_on_a_boolean_apply():
    """T3-3: preview is the Registry face's default. A string "false" is not a write order."""
    intent = (chr(10).join(["---", "cognition_ref: cognition/ai-workspace/README.md",
                            "desired_action_type: software", "revision: bootstrap-v1", "---"])
              + chr(10))
    state = VAULT / ".knowledge/state/atomic-actions.json"
    before = state.read_text(encoding="utf-8")

    preview = json.loads(call({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                               "params": {"name": "action_reconcile",
                                          "arguments": {"request": intent}}})
                         [0]["result"]["content"][0]["text"])
    assert preview["exit"] == 0, preview
    assert preview["dry_run"] is True
    assert state.read_text(encoding="utf-8") == before

    quoted = json.loads(call({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                              "params": {"name": "action_reconcile",
                                         "arguments": {"request": intent, "apply": "false"}}})
                        [0]["result"]["content"][0]["text"])
    assert quoted["dry_run"] is True
    assert state.read_text(encoding="utf-8") == before

    applied = json.loads(call({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                               "params": {"name": "action_reconcile",
                                          "arguments": {"request": intent, "apply": True}}})
                         [0]["result"]["content"][0]["text"])
    assert applied["exit"] == 0, applied
    assert applied["plan"]["operations"][0]["op"] == "noop"
    assert applied["result"]["status"] == "noop"
    assert "dry_run" not in applied
    assert state.read_text(encoding="utf-8") == before


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
