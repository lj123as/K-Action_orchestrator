#!/usr/bin/env python3
"""K-Action_orchestrator MCP stdio server: the Action Operation entry.

Action Operation is this component's capability (`action.operate`), so its MCP adapter belongs
here rather than in AI Workspace -- see [[cognition/ai-workspace/02-mcp-interface]] 的「归 Domain
的工具面」与「实现迁移」。KA-System 的 MCP adapter 归运行时信封（dispatch/schedule/health/
retry/audit/lifecycle），见同文的维护通道总表；两者不是同一组工具。

The adapter is a transport, not a second implementation: every call runs this component's own
`tools/action_ops.py`, which owns the operation. Transport: MCP stdio, newline-delimited
JSON-RPC (protocol 2025-06-18).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Action Operation: what action_ops owns; these write when called (they have no preview step).
OPERATIONS = ("create", "update", "execute", "validate", "register")
# Registry operation: the descriptor face. Its own set, with preview by default.
REGISTRY_OPERATIONS = ("catalog", "reconcile")
NAME = "action-orchestrator"
VERSION = "0.1.0"

TOOLS = [
    {"name": "action_request",
     "description": "KA action operation via the K-Action_orchestrator unified entry "
                    "(create/update/execute/validate/register); a create request must carry "
                    "action_type and review_status approved",
     "inputSchema": {"type": "object",
                     "properties": {"operation": {"type": "string"},
                                    "request": {"type": "string"}},
                     "required": ["operation", "request"]}},
    {"name": "action_update_component",
     "description": "build an update Action Request for action component sync and route it to "
                    "the orchestrator",
     "inputSchema": {"type": "object",
                     "properties": {"action_type": {"type": "string"},
                                    "subject": {"type": "string"},
                                    "instance_id": {"type": "string"},
                                    "spec_id": {"type": "string"},
                                    "intent": {"type": "string"}},
                     "required": ["instance_id"]}},
    {"name": "action_registry_catalog",
     "description": "read-only view of the Action Types declared in .knowledge/manifest.yaml "
                    "(the Registry's declaration source)",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "action_reconcile",
     "description": "create or update an Atomic Action descriptor from an ActionIntent: the "
                    "Registry resolves the Factory, the Factory plans and applies. PREVIEW BY "
                    "DEFAULT - state is written only when apply is true. The Action Operations "
                    "(create/update/execute/validate/register) are not preview-gated and must "
                    "not be described as if they were",
     "inputSchema": {"type": "object",
                     "properties": {"request": {"type": "string"},
                                    "apply": {"type": "boolean"}},
                     "required": ["request"]}},
]


def run_operation(operation, request):
    """One Action Operation, executed by this component's own tool."""
    if operation not in OPERATIONS:
        return {"exit": 2, "error": "unknown operation: " + str(operation)}
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools/action_ops.py"), operation, "-"],
        input=str(request or ""), capture_output=True, text=True, encoding="utf-8", timeout=120)
    try:
        payload = json.loads((proc.stdout or "").strip())
    except ValueError:
        payload = {"stdout": (proc.stdout or "").strip(), "stderr": (proc.stderr or "").strip()}
    return {"exit": proc.returncode, **payload}


def update_intent(args):
    """The update Action Request this tool builds; the operation still belongs to action_ops."""
    lines = ["---"]
    for key in ("action_type", "subject", "instance_id", "spec_id", "intent"):
        if args.get(key):
            lines.append(key + ": " + str(args[key]))
    lines.append("---")
    return chr(10).join(lines) + chr(10)


def run_registry(operation, request="", apply=False):
    """A Registry operation, at the preview semantics that operation declares.

    `reconcile` is dry-run unless `apply` is true. `apply` is accepted only as a JSON boolean:
    a string "false" is not a declaration to write, and treating it as one is how a preview
    turns into a write.
    """
    if operation not in REGISTRY_OPERATIONS:
        return {"exit": 2, "error": "unknown registry operation: " + str(operation)}
    argv = [sys.executable, str(ROOT / "tools/action_ops.py"), operation]
    if apply is True:
        argv.append("--apply")
    if operation != "catalog":
        argv.append("-")
    proc = subprocess.run(argv, input=str(request or ""), capture_output=True, text=True,
                          encoding="utf-8", timeout=300)
    try:
        payload = json.loads((proc.stdout or "").strip())
    except ValueError:
        payload = {"stdout": (proc.stdout or "").strip(), "stderr": (proc.stderr or "").strip()}
    return {"exit": proc.returncode, **payload}


def dispatch(name, args):
    args = args or {}
    if name == "action_request":
        return run_operation(args.get("operation", ""), args.get("request", ""))
    if name == "action_update_component":
        return run_operation("update", update_intent(args))
    if name == "action_registry_catalog":
        return run_registry("catalog")
    if name == "action_reconcile":
        return run_registry("reconcile", args.get("request", ""), args.get("apply"))
    raise ValueError("unknown tool: " + str(name))


def handle(msg):
    method = msg.get("method", "")
    rid = msg.get("id")
    if method == "initialize":
        proto = (msg.get("params") or {}).get("protocolVersion", "2025-06-18")
        return {"jsonrpc": "2.0", "id": rid,
                "result": {"protocolVersion": proto, "capabilities": {"tools": {}},
                           "serverInfo": {"name": NAME, "version": VERSION}}}
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
    if method == "resources/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"resources": []}}
    if method == "prompts/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"prompts": []}}
    if method == "tools/call":
        params = msg.get("params") or {}
        try:
            result = dispatch(params.get("name", ""), params.get("arguments") or {})
            text = (json.dumps(result, ensure_ascii=False, indent=1)
                    if isinstance(result, dict) else str(result))
            is_error = isinstance(result, dict) and result.get("exit", 0) != 0
            return {"jsonrpc": "2.0", "id": rid,
                    "result": {"content": [{"type": "text", "text": text}], "isError": is_error}}
        except Exception as exc:
            return {"jsonrpc": "2.0", "id": rid,
                    "result": {"content": [{"type": "text", "text": "ERROR: " + str(exc)}],
                               "isError": True}}
    return {"jsonrpc": "2.0", "id": rid,
            "error": {"code": -32601, "message": "method not found: " + method}}


def main():
    # MCP carries UTF-8; the console codec cannot be relied on for Chinese arguments.
    for stream in (sys.stdin, sys.stdout):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        resp = handle(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + chr(10))
            sys.stdout.flush()


if __name__ == "__main__":
    main()
