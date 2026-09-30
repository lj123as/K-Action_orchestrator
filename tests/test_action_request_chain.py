# -*- coding: utf-8 -*-
"""The Action Operation chain, against this component's own adapter.

These came from AI Workspace's adapter tests, where they loaded the orchestrator's MCP from the
wrong component. Action Operation belongs here (see cognition/ai-workspace/02-mcp-interface).
"""
import importlib.util
import json
import tempfile
from pathlib import Path


MCP = Path(__file__).resolve().parents[1] / "mcp" / "server.py"


def load_mcp():
    spec = importlib.util.spec_from_file_location("action_orchestrator_mcp", MCP)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def make_vault(root: Path):
    drafts = root / ".knowledge" / "drafts"
    drafts.mkdir(parents=True)
    (drafts / "draft-cli.md").write_text(
        "---\ntype: atomic\nsubtype: cognition\nstatus: draft\nreview_status: needs_review\n"
        "source: test\nid: 20260827-draft-cli\ntags: [type/cognition]\nclaim: draft cli test claim\n"
        "evidence:\n  states: []\n---\n\n# Draft CLI\n", encoding="utf-8")
    return root


def make_chain_vault(root: Path):
    make_vault(root)
    (root / "cognition").mkdir(exist_ok=True)
    (root / ".knowledge" / "manifest.yaml").write_text(
        "action_types:\n  - id: software\n    creators: [software-factory]\n"
        "    operations: [create, update, execute, validate]\n", encoding="utf-8")
    prov_dir = root / "action" / "software-factory"
    prov_dir.mkdir(parents=True)
    (prov_dir / "action_provider.py").write_text(
        "def create_instance(spec, vault=None):\n"
        "    return {\"exit\": 0, \"instance\": {\"agent_id\": \"agt-stub\", \"subject\": (spec or {}).get(\"subject\", \"\")}}\n"
        "def update_instance(instance, request, vault=None):\n"
        "    return {\"exit\": 0, \"instance\": instance}\n"
        "def execute(instance, request, vault=None):\n"
        "    return {\"exit\": 0, \"state\": \"done\", \"executed\": True}\n"
        "def validate(instance, request, vault=None):\n"
        "    return {\"exit\": 0, \"valid\": True}\n", encoding="utf-8")
    state = root / ".knowledge" / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "software-realizations.json").write_text(json.dumps({
        "version": 1,
        "actions": {"software-factory": {
            "source_workspaces": [], "distributions": [], "service_bindings": [],
            "installation_generations": [{
                "id": "software-factory@test-host",
                "host_id": "test-host",
                "status": "active",
                "components": [{
                    "id": "software-factory",
                    "status": "active",
                    "entrypoint": "action/software-factory/action_provider.py",
                    "provides": ["action.factory_provider"],
                    "action_types": ["software"],
                }],
            }],
        }},
    }, ensure_ascii=False), encoding="utf-8")


def test_action_update_component_uses_action_request_update(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        vault = Path(td)
        make_chain_vault(vault)
        monkeypatch.setenv("KA_VAULT_ROOT", str(vault))
        mcp = load_mcp()
        create_req = "---\naction_type: software\nspec_id: s1\nsubject: knowledge-network\nreview_status: approved\nstatus: approved\n---\n"
        created = mcp.dispatch("action_request", {"operation": "create", "request": create_req})
        assert created["exit"] == 0, created

        # An update names the instance: a subject is not an identity.
        anonymous = mcp.dispatch("action_update_component", {"action_type": "software", "subject": "knowledge-network"})
        assert anonymous["exit"] == 2
        assert "instance_id is required" in json.dumps(anonymous)

        updated = mcp.dispatch("action_update_component", {"action_type": "software", "instance_id": created["instance"]["instance_id"], "intent": "sync with KN cognition"})
        assert updated["exit"] == 0, updated
        assert updated["status"] == "updated"


def test_action_request_create_gate_and_unknown_op(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        vault = Path(td)
        make_vault(vault)
        (vault / ".knowledge" / "manifest.yaml").write_text(
            "action_types:\n  - id: software\n    creators: [software-factory]\n"
            "    operations: [create, update, execute, validate]\n", encoding="utf-8")
        monkeypatch.setenv("KA_VAULT_ROOT", str(vault))
        mcp = load_mcp()
        req = "---\naction_type: software\nspec_id: s1\nsubject: demo\nreview_status: needs_review\n---\n"
        res = mcp.dispatch("action_request", {"operation": "create", "request": req})
        assert res["exit"] == 2
        assert "gate" in res.get("stderr", "")
        bad = mcp.dispatch("action_request", {"operation": "explode", "request": req})
        assert bad["exit"] == 2
        assert "unknown operation" in bad.get("error", "")

