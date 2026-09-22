import json, os, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path.cwd()
TOOL = ROOT / "action/K-Action_orchestrator/tools/action_ops.py"

def make_vault(root: Path, provider="fake_ss", prov_impl=None):
    (root / ".knowledge" / "state").mkdir(parents=True)
    (root / ".knowledge" / "events").mkdir(parents=True)
    if prov_impl is not None:
        pp = root / "action" / provider
        pp.mkdir(parents=True, exist_ok=True)
        (pp / "design_model.py").write_text(prov_impl, encoding="utf-8")
    mf = root / ".knowledge" / "manifest.yaml"
    mf.write_text(chr(10).join([
        "version: \"1\"",
        "action_types:",
        "  - id: software",
        "    creators: [" + provider + "]",
        "    operations: [create, update, execute, validate, register]",
    ]), encoding="utf-8")
    (root / ".knowledge" / "state" / "software-realizations.json").write_text(
        json.dumps({
            "version": 1,
            "actions": {
                provider: {
                    "installations": [{
                        "id": provider + "@test",
                        "host_id": "test-host",
                        "status": "active",
                        "components": [{
                            "id": provider,
                            "status": "active",
                            "entrypoint": "action/" + provider + "/design_model.py",
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
    return root

def make_spec(root: Path, name="spec.md", op="create"):
    spec = root / name
    body = [
        "---",
        "spec_id: spec-001",
        "action_type: software",
        "operation: " + op,
        "subject: stock-analysis-system",
    ]
    if op != "create":
        body.append("instance_id: act-0001")
    body += ["status: approved", "review_status: approved", "---", "# Spec", "requirements: ..."]
    spec.write_text(chr(10).join(body), encoding="utf-8")
    return spec

PROVIDER_IMPL = chr(10).join([
    "def create_instance(spec, vault=None):",
    '    return {"exit": 0, "instance": {"instance_type": "FakeSoftwareInstance/v1", "subject": spec.get("subject", ""), "state": "created"}}',
    "def execute(instance, spec=None, vault=None):",
    '    return {"exit": 0, "executed": True, "state": "done", "maintenance": {"added": 1, "dry_run": True}}',
    "def update_instance(instance, spec, vault=None):",
    '    return {"exit": 0, "instance": {"registry_route": "update"}}',
    "def validate(instance, spec=None, vault=None):",
    '    return {"exit": 0, "valid": True, "registry_route": "validate"}',
    "def schema():",
    '    return {"exit": 0, "objects": []}',
])

def run(root: Path, *args):
    env = dict(os.environ); env["KA_VAULT_ROOT"] = str(root)
    return subprocess.run([sys.executable, str(TOOL), *args], env=env, capture_output=True, text=True, timeout=60)

def test_create_operation_creates_instance():
    with tempfile.TemporaryDirectory() as td:
        vault = Path(td)
        make_vault(vault, provider="fake_ss", prov_impl=PROVIDER_IMPL)
        spec = make_spec(vault)
        p = run(vault, "create", str(spec))
        assert p.returncode == 0, p.stderr
        data = json.loads((vault / ".knowledge/state/action-instances.json").read_text(encoding="utf-8"))
        inst = data["instances"][0]
        assert inst["action_type"] == "software"
        assert inst["state"] == "created"
        assert inst["provider"] == "fake_ss"

def test_update_and_execute_operations_mutate_instance_state():
    with tempfile.TemporaryDirectory() as td:
        vault = Path(td)
        make_vault(vault, provider="fake_ss", prov_impl=PROVIDER_IMPL)
        spec = make_spec(vault)
        p0 = run(vault, "create", str(spec))
        assert p0.returncode == 0, p0.stderr
        state = vault / ".knowledge/state/action-instances.json"
        inst_id = json.loads(state.read_text(encoding="utf-8"))["instances"][0]["instance_id"]
        uspec = make_spec(vault, name="update.md", op="update")
        uspec.write_text(uspec.read_text(encoding="utf-8").replace("instance_id: act-0001", "instance_id: " + inst_id, 1), encoding="utf-8")
        p1 = run(vault, "update", str(uspec))
        assert p1.returncode == 0, p1.stderr
        inst = json.loads(state.read_text(encoding="utf-8"))["instances"][0]
        assert inst["state"] == "updated" or inst.get("updated_at")
        espec = make_spec(vault, name="exec.md", op="execute")
        espec.write_text(espec.read_text(encoding="utf-8").replace("instance_id: act-0001", "instance_id: " + inst_id, 1), encoding="utf-8")
        p2 = run(vault, "execute", str(espec))
        assert p2.returncode == 0, p2.stderr
        inst = json.loads(state.read_text(encoding="utf-8"))["instances"][0]
        assert inst["state"] in ("running", "done", "failed")
        assert inst.get("last_run")
        assert inst.get("maintenance") == {"added": 1, "dry_run": True}

def test_validate_operation_checks_instance_and_provider():
    with tempfile.TemporaryDirectory() as td:
        vault = Path(td)
        make_vault(vault, provider="fake_ss", prov_impl=PROVIDER_IMPL)
        spec = make_spec(vault)
        p0 = run(vault, "create", str(spec))
        state = vault / ".knowledge/state/action-instances.json"
        inst_id = json.loads(state.read_text(encoding="utf-8"))["instances"][0]["instance_id"]
        vspec = make_spec(vault, name="val.md", op="validate")
        vspec.write_text(vspec.read_text(encoding="utf-8").replace("instance_id: act-0001", "instance_id: " + inst_id, 1), encoding="utf-8")
        p = run(vault, "validate", str(vspec))
        assert p.returncode == 0, p.stderr
        assert "valid" in p.stdout.lower() or "ok" in p.stdout.lower()

def test_existing_instance_operations_resolve_active_registry_provider():
    with tempfile.TemporaryDirectory() as td:
        vault = Path(td)
        make_vault(vault, provider="fake_ss", prov_impl=PROVIDER_IMPL)
        state = vault / ".knowledge/state/action-instances.json"
        state.write_text(json.dumps({"version": 1, "instances": [{
            "instance_id": "act-1",
            "action_type": "software",
            "subject": "registry-route",
            "provider": "stale-provider",
            "state": "created",
        }]}), encoding="utf-8")

        validate = make_spec(vault, name="validate.md", op="validate")
        validate.write_text(validate.read_text(encoding="utf-8").replace("act-0001", "act-1"), encoding="utf-8")
        result = run(vault, "validate", str(validate))
        assert result.returncode == 0, result.stderr

        update = make_spec(vault, name="update.md", op="update")
        update.write_text(update.read_text(encoding="utf-8").replace("act-0001", "act-1"), encoding="utf-8")
        result = run(vault, "update", str(update))
        assert result.returncode == 0, result.stderr
        instance = json.loads(state.read_text(encoding="utf-8"))["instances"][0]
        assert instance["provider"] == "fake_ss"
        assert instance["registry_route"] == "update"

        execute = make_spec(vault, name="execute.md", op="execute")
        execute.write_text(execute.read_text(encoding="utf-8").replace("act-0001", "act-1"), encoding="utf-8")
        result = run(vault, "execute", str(execute))
        assert result.returncode == 0, result.stderr
        assert json.loads(state.read_text(encoding="utf-8"))["instances"][0]["provider"] == "fake_ss"

def test_create_and_update_fail_without_persisting_success_state():
    with tempfile.TemporaryDirectory() as td:
        vault = Path(td)
        failing = chr(10).join([
            "def create_instance(spec, vault=None):",
            '    return {"exit": 2, "error": "create failed"}',
            "def update_instance(instance, spec, vault=None):",
            '    return {"exit": 2, "error": "update failed"}',
        ])
        make_vault(vault, provider="fake_ss", prov_impl=failing)
        spec = make_spec(vault)
        result = run(vault, "create", str(spec))
        assert result.returncode == 2
        assert "create failed" in result.stderr
        state = vault / ".knowledge/state/action-instances.json"
        assert not state.exists()

        state.write_text(json.dumps({"version": 1, "instances": [{
            "instance_id": "act-1",
            "action_type": "software",
            "subject": "broken-update",
            "provider": "fake_ss",
            "state": "created",
        }]}), encoding="utf-8")
        before = state.read_text(encoding="utf-8")
        update = make_spec(vault, name="update.md", op="update")
        update.write_text(update.read_text(encoding="utf-8").replace("act-0001", "act-1"), encoding="utf-8")
        result = run(vault, "update", str(update))
        assert result.returncode == 2
        assert "update failed" in result.stderr
        assert state.read_text(encoding="utf-8") == before

def test_operation_rejects_unknown_operation():
    with tempfile.TemporaryDirectory() as td:
        vault = Path(td)
        make_vault(vault, provider="fake_ss", prov_impl=PROVIDER_IMPL)
        spec = make_spec(vault, name="bad.md", op="delete")
        p = run(vault, "delete", str(spec))
        assert p.returncode == 2, p.stdout


def test_register_reconciles_manifest_from_component_contract():
    with tempfile.TemporaryDirectory() as td:
        vault = Path(td)
        make_vault(vault, provider="fake_ss", prov_impl=PROVIDER_IMPL)
        comp = vault / "action" / "fake_ss"
        comp.mkdir(parents=True, exist_ok=True)
        (comp / "component.yaml").write_text("id: fake_ss\naction_types:\n  - new-type\n", encoding="utf-8")
        mf = vault / ".knowledge/manifest.yaml"
        before = mf.read_text(encoding="utf-8")
        spec = make_spec(vault, name="reg.md")
        r = run(vault, "register", str(spec))
        assert r.returncode == 0, r.stderr
        assert mf.read_text(encoding="utf-8") == before
        r2 = run(vault, "register", "--apply", str(spec))
        assert r2.returncode == 0, r2.stderr
        after = mf.read_text(encoding="utf-8")
        assert "  - id: new-type" in after
        assert "creators: [fake_ss]" in after
        r3 = run(vault, "register", "--apply", str(spec))
        assert r3.returncode == 0, r3.stderr
        assert mf.read_text(encoding="utf-8") == after


def test_catalog_lists_registered_action_types():
    with tempfile.TemporaryDirectory() as td:
        vault = Path(td)
        make_vault(vault, provider="fake_ss", prov_impl=PROVIDER_IMPL)
        p = run(vault, "catalog")
        assert p.returncode == 0, p.stderr
        data = json.loads(p.stdout)
        ids = [t["id"] for t in data["action_types"]]
        assert ids == ["software"]
        ss = data["action_types"][0]
        assert "fake_ss" in ss["creators"]
        assert "register" in ss["operations"]
