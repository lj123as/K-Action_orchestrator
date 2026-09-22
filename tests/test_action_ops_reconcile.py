# -*- coding: utf-8 -*-
import json
import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / "action/KA-system/tools/action_type_registry.py"
ACTION_OPS = ROOT / "action/K-Action_orchestrator/tools/action_ops.py"


def run_cmd(vault, args, stdin=""):
    env = os.environ.copy()
    env["KA_VAULT_ROOT"] = str(vault)
    return subprocess.run(
        [sys.executable, *map(str, args)],
        cwd=ROOT,
        env=env,
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def load_factory_ops():
    path = ROOT / "action/software-factory/provider/factory_ops.py"
    spec = importlib.util.spec_from_file_location("software_factory_factory_ops_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def seed_fake_factory(vault):
    provider = vault / "action" / "fake-factory"
    provider.mkdir(parents=True)
    (provider / "component.yaml").write_text(
        """
id: fake-factory
provides:
  - action.factory_provider
action_types:
  - fake-type
requires: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    entrypoint = vault / "installed/providers/fake_factory.py"
    entrypoint.parent.mkdir(parents=True)
    entrypoint.write_text(
        """
from pathlib import Path


def plan(request, vault=None):
    return {"exit": 0, "plan": {"operations": [{"op": "noop"}], "effects": [], "risks": [], "requires_review": False, "expected_state": {"action_ref": "action/fake"}}}


def apply(plan, request, vault=None):
    Path(vault, "apply-called").write_text("yes", encoding="utf-8")
    return {"exit": 0, "result": {"status": "noop", "action_ref": "action/fake", "realized_state": plan.get("expected_state", {}), "artifacts": [], "observations": [], "diagnostics": []}}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    state = vault / ".knowledge/state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "software-realizations.json").write_text(
        json.dumps({
            "version": 1,
            "actions": {
                "fake-factory": {
                    "installations": [{
                        "id": "fake-factory@test",
                        "host_id": "test-host",
                        "status": "active",
                        "components": [{
                            "id": "fake-factory",
                            "status": "active",
                            "entrypoint": "installed/providers/fake_factory.py",
                            "provides": ["action.factory_provider"],
                            "action_types": ["fake-type"],
                        }],
                    }],
                    "runtime_instances": [],
                }
            },
        }),
        encoding="utf-8",
    )


def test_reconcile_uses_registry_resolved_fake_factory(tmp_path):
    seed_fake_factory(tmp_path)
    assert run_cmd(tmp_path, [REGISTRY, "discover"]).returncode == 0
    registry_path = tmp_path / ".knowledge/state/action-type-registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["updated"] = "2000-01-01T00:00:00Z"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    registry_before = registry_path.read_text(encoding="utf-8")
    intent = """---
cognition_ref: cognition/fake/README.md
desired_action_type: fake-type
reason: test
revision: r1
---
"""

    result = run_cmd(tmp_path, [ACTION_OPS, "reconcile", "-", "--dry-run"], intent)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["factory"]["provider_id"] == "fake-factory"
    assert payload["plan"]["operations"] == [{"op": "noop"}]
    assert not (tmp_path / "apply-called").exists()
    assert registry_path.read_text(encoding="utf-8") == registry_before

    applied = run_cmd(tmp_path, [ACTION_OPS, "reconcile", "-", "--apply"], intent)

    assert applied.returncode == 0, applied.stderr
    assert (tmp_path / "apply-called").read_text(encoding="utf-8") == "yes"


def test_reconcile_passes_current_atomic_action_state_to_factory(tmp_path):
    seed_fake_factory(tmp_path)
    (tmp_path / ".knowledge/state").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".knowledge/state/atomic-actions.json").write_text(
        json.dumps({
            "version": 1,
            "actions": {
                "fake": {
                    "id": "fake",
                    "action_type": "fake-type",
                    "cognition_ref": "cognition/fake/README.md",
                    "revision": "r1",
                }
            },
        }),
        encoding="utf-8",
    )
    provider = tmp_path / "installed/providers/fake_factory.py"
    provider.write_text(
        """
def plan(request, vault=None):
    if not request.get("current_state"):
        return {"exit": 2, "error": "current_state missing"}
    return {"exit": 0, "plan": {"operations": [{"op": "noop"}], "effects": [], "risks": [], "requires_review": False, "expected_state": request["current_state"]}}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    run_cmd(tmp_path, [REGISTRY, "discover"])
    intent = """---
cognition_ref: cognition/fake/README.md
desired_action_type: fake-type
current_action_ref: action/fake
reason: test
revision: r1
---
"""

    result = run_cmd(tmp_path, [ACTION_OPS, "reconcile", "-", "--dry-run"], intent)

    assert result.returncode == 0, result.stderr
    assert result.stdout


def test_reconcile_requires_confirmed_action_type(tmp_path):
    seed_fake_factory(tmp_path)
    run_cmd(tmp_path, [REGISTRY, "discover"])
    intent = """---
cognition_ref: cognition/fake/README.md
revision: r1
---
"""

    result = run_cmd(tmp_path, [ACTION_OPS, "reconcile", "-", "--dry-run"], intent)

    assert result.returncode == 2
    assert "missing action_type" in result.stderr


def test_create_uses_registry_provider_instead_of_manifest_creator(tmp_path):
    seed_fake_factory(tmp_path)
    provider = tmp_path / "installed/providers/fake_factory.py"
    provider.write_text(
        provider.read_text(encoding="utf-8")
        + "\n\ndef create_instance(spec, vault=None):\n"
        + "    return {'exit': 0, 'instance': {'provider_seen': 'fake-factory'}}\n",
        encoding="utf-8",
    )
    manifest = tmp_path / ".knowledge/manifest.yaml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        """action_types:
  - id: fake-type
    owner: ka-system
    creators: [wrong-provider]
    operations: [create]
""",
        encoding="utf-8",
    )
    assert run_cmd(tmp_path, [REGISTRY, "discover"]).returncode == 0
    intent = """---
action_type: fake-type
status: approved
spec_id: spec-1
subject: registry-routed
---
"""

    result = run_cmd(tmp_path, [ACTION_OPS, "create", "-"], intent)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["instance"]["provider"] == "fake-factory"
    assert payload["instance"]["capability_instance"]["provider_seen"] == "fake-factory"


def test_reconcile_rejects_conflicting_write_flags_and_escaping_ref(tmp_path):
    seed_fake_factory(tmp_path)
    run_cmd(tmp_path, [REGISTRY, "discover"])
    intent = """---
cognition_ref: ../outside.md
desired_action_type: fake-type
revision: r1
---
"""

    conflicting = run_cmd(tmp_path, [ACTION_OPS, "reconcile", "-", "--dry-run", "--apply"], intent)
    escaping = run_cmd(tmp_path, [ACTION_OPS, "reconcile", "-", "--dry-run"], intent)

    assert conflicting.returncode == 2
    assert "mutually exclusive" in conflicting.stderr
    assert escaping.returncode == 2
    assert "must stay inside the vault" in escaping.stderr


def test_ka_system_seed_reconciles_through_software_factory(tmp_path):
    provider = tmp_path / "action/software-factory"
    provider.mkdir(parents=True)
    shutil.copy(ROOT / "action/software-factory/action_provider.py", provider / "action_provider.py")
    shutil.copy(ROOT / "action/software-factory/component.yaml", provider / "component.yaml")
    shutil.copytree(ROOT / "action/software-factory/provider", provider / "provider")
    shutil.copytree(ROOT / "action/software-factory/profiles", provider / "profiles")
    (provider / "component.yaml").write_text(
        "id: software-factory\nprovides: [action.factory_provider]\naction_types: [software]\n",
        encoding="utf-8",
    )
    cognition = tmp_path / "cognition/KA-system/README.md"
    cognition.parent.mkdir(parents=True)
    cognition.write_text("# KA-System\n", encoding="utf-8")
    state = tmp_path / ".knowledge/state"
    state.mkdir(parents=True)
    (state / "software-realizations.json").write_text(
        json.dumps({
            "version": 1,
            "actions": {
                "software-factory": {
                    "installations": [{
                        "id": "software-factory@test",
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
                    "runtime_instances": [],
                }
            },
        }),
        encoding="utf-8",
    )
    (state / "atomic-actions.json").write_text(
        json.dumps({
            "version": 1,
            "actions": {
                "ka-system": {
                    "id": "ka-system",
                    "action_type": "software",
                    "cognition_ref": "cognition/KA-system/README.md",
                    "workspace_ref": "action/KA-system",
                    "revision": "bootstrap-v1",
                    "status": "active",
                    "provenance": "external:human",
                }
            },
        }),
        encoding="utf-8",
    )
    assert run_cmd(tmp_path, [REGISTRY, "discover"]).returncode == 0
    intent = """---
cognition_ref: cognition/KA-system/README.md
desired_action_type: software
current_action_ref: action/KA-system
reason: self-host proof
revision: bootstrap-v1
action_id: ka-system
workspace_ref: action/KA-system
provenance: external:human
---
"""

    result = run_cmd(tmp_path, [ACTION_OPS, "reconcile", "-", "--dry-run"], intent)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["factory"]["provider_id"] == "software-factory"
    assert payload["plan"]["operations"] == [{"op": "noop"}]
    descriptor = json.loads((state / "atomic-actions.json").read_text(encoding="utf-8"))["actions"]["ka-system"]
    assert descriptor["provenance"] == "external:human"


def test_software_factory_reconcile_apply_materializes_workspace(tmp_path):
    provider = tmp_path / "action/software-factory"
    provider.mkdir(parents=True)
    shutil.copy(ROOT / "action/software-factory/action_provider.py", provider / "action_provider.py")
    shutil.copy(ROOT / "action/software-factory/component.yaml", provider / "component.yaml")
    shutil.copytree(ROOT / "action/software-factory/provider", provider / "provider")
    shutil.copytree(ROOT / "action/software-factory/profiles", provider / "profiles")
    (provider / "component.yaml").write_text(
        "id: software-factory\nprovides: [action.factory_provider]\naction_types: [software]\n",
        encoding="utf-8",
    )
    state = tmp_path / ".knowledge/state"
    state.mkdir(parents=True)
    (state / "software-realizations.json").write_text(
        json.dumps({
            "version": 1,
            "actions": {
                "software-factory": {
                    "installations": [{
                        "id": "software-factory@test",
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
                    "runtime_instances": [],
                }
            },
        }),
        encoding="utf-8",
    )
    (state / "atomic-actions.json").write_text(
        json.dumps({"version": 1, "actions": {}}),
        encoding="utf-8",
    )
    assert run_cmd(tmp_path, [REGISTRY, "discover"]).returncode == 0
    intent = """---
cognition_ref: cognition/demo/README.md
desired_action_type: software
action_id: demo
workspace_ref: action/demo
reason: e2e create
revision: r1
    requirements:
      - provide a search API
      - support export
---
"""
    result = run_cmd(tmp_path, [ACTION_OPS, "reconcile", "-", "--apply"], intent)
    assert result.returncode == 0, result.stderr
    ws = tmp_path / "action" / "demo"
    assert (ws / "design/design.md").exists()
    design_text = (ws / "design/design.md").read_text(encoding="utf-8")
    assert "- provide a search API" in design_text
    assert "- support export" in design_text
    manifest = (ws / "deploy/manifest.yaml").read_text(encoding="utf-8")
    assert "id: demo" in manifest
    assert "type: software" in manifest
    actions = json.loads((state / "atomic-actions.json").read_text(encoding="utf-8"))
    assert actions["actions"]["demo"]["action_type"] == "software"
    assert actions["actions"]["demo"]["acceptance"]["status"] == "accepted"


def test_software_factory_bootstraps_ka_and_kn_with_agentic_profile(tmp_path):
    provider = tmp_path / "action/software-factory"
    provider.mkdir(parents=True)
    shutil.copy(ROOT / "action/software-factory/action_provider.py", provider / "action_provider.py")
    shutil.copy(ROOT / "action/software-factory/component.yaml", provider / "component.yaml")
    shutil.copytree(ROOT / "action/software-factory/provider", provider / "provider")
    shutil.copytree(ROOT / "action/software-factory/profiles", provider / "profiles")
    shutil.copytree(ROOT / "cognition/KA-system", tmp_path / "cognition/KA-system")
    shutil.copytree(ROOT / "cognition/knowledge-network", tmp_path / "cognition/knowledge-network")
    state = tmp_path / ".knowledge/state"
    state.mkdir(parents=True)
    (state / "software-realizations.json").write_text(
        json.dumps({
            "version": 1,
            "actions": {
                "software-factory": {
                    "installations": [{
                        "id": "software-factory@test",
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
                    "runtime_instances": [],
                }
            },
        }),
        encoding="utf-8",
    )
    (state / "atomic-actions.json").write_text(
        json.dumps({"version": 1, "actions": {}}), encoding="utf-8"
    )
    assert run_cmd(tmp_path, [REGISTRY, "discover"]).returncode == 0

    requests = {
        "ka-system": "cognition/KA-system/README.md",
        "knowledge-network": "cognition/knowledge-network/README.md",
    }
    for action_id, cognition_ref in requests.items():
        intent = "\n".join([
            "---",
            f"cognition_ref: {cognition_ref}",
            "desired_action_type: software",
            "profiles:",
            "  - agentic",
            f"action_id: {action_id}",
            f"workspace_ref: action/{action_id}",
            "reason: bootstrap MVP",
            "revision: bootstrap-v1",
            "---",
            "",
        ])
        result = run_cmd(tmp_path, [ACTION_OPS, "reconcile", "-", "--apply"], intent)
        assert result.returncode == 0, result.stderr

    factory_ops = load_factory_ops()
    actions = json.loads((state / "atomic-actions.json").read_text(encoding="utf-8"))["actions"]
    for action_id in requests:
        descriptor = actions[action_id]
        assert descriptor["action_type"] == "software"
        assert descriptor["profiles"] == ["agentic"]
        assert factory_ops.validate(tmp_path / "action" / action_id)["exit"] == 0
        manifest = (tmp_path / "action" / action_id / "deploy/manifest.yaml").read_text(encoding="utf-8")
        assert "type: software" in manifest
        assert "profile: agentic" in manifest

    tracked = [state / "atomic-actions.json", state / "action-type-registry.json"]
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in tracked}
    for action_id, cognition_ref in requests.items():
        intent = "\n".join([
            "---",
            f"cognition_ref: {cognition_ref}",
            "desired_action_type: software",
            "profiles:",
            "  - agentic",
            f"current_action_ref: action/{action_id}",
            "reason: bootstrap audit",
            "revision: bootstrap-v1",
            "---",
            "",
        ])
        result = run_cmd(tmp_path, [ACTION_OPS, "reconcile", "-", "--dry-run"], intent)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["plan"]["operations"] == [{"op": "noop"}]
    assert before == {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in tracked}


def test_reconcile_uses_registration_install_root(tmp_path):
    """The loader must use the registration install root, not the process environment."""
    install_root = tmp_path / "ka-install-root"
    provider_dir = install_root / "fake-factory@1.0.0" / "Lib" / "site-packages"
    provider_dir.mkdir(parents=True)
    provider = provider_dir / "action_provider.py"
    provider.write_text(
        "def plan(request, vault=None):" + chr(10) +
        "    return {'exit': 0, 'plan': {'operations': [{'op': 'noop'}], 'effects': []," + chr(10) +
        "            'risks': [], 'requires_review': False, 'expected_state': {}}}" + chr(10),
        encoding="utf-8")
    state = tmp_path / ".knowledge/state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "software-realizations.json").write_text(json.dumps({
        "version": 1,
        "deployment_environments": {"ka-vault-server": {
            "id": "ka-vault-server", "type": "production", "install_root": str(install_root)}},
        "actions": {"fake-factory": {
            "source_workspaces": [], "distributions": [], "service_bindings": [],
            "installations": [{
                "id": "fake-factory@ka-vault-server", "host_id": "ka-vault-server",
                "status": "active", "link_kind": "artifact", "revision": "1.0.0",
                "distribution_id": "fake-factory@1.0.0",
                "deployment_environment_id": "ka-vault-server",
                "components": [{"id": "fake-factory", "status": "active",
                                "provides": ["action.factory_provider"],
                                "action_types": ["fake-type"],
                                "provider_entrypoint": str(provider)}]}]}}}, ensure_ascii=False),
        encoding="utf-8")
    env = os.environ.copy()
    env.pop("KA_INSTALL_ROOT", None)  # the point: no process-level install root
    env["KA_VAULT_ROOT"] = str(tmp_path)
    intent = ("---" + chr(10) + "cognition_ref: cognition/fake/README.md" + chr(10) +
              "desired_action_type: fake-type" + chr(10) + "reason: install root" + chr(10) +
              "revision: r1" + chr(10) + "---" + chr(10))

    result = subprocess.run([sys.executable, str(ACTION_OPS), "reconcile", "-", "--dry-run"],
                            cwd=ROOT, env=env, input=intent, capture_output=True,
                            text=True, encoding="utf-8")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["factory"]["install_root"].endswith("ka-install-root")
    assert payload["plan"]["operations"] == [{"op": "noop"}]
