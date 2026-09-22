import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CLI = ROOT / "action/K-Action_orchestrator/tools/capability_dev.py"


def run_cli(vault: Path, request: Path, *args: str):
    env = dict(os.environ, KA_VAULT_ROOT=str(vault))
    return subprocess.run(
        [sys.executable, str(CLI), "dispatch", str(request), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def write_request(vault: Path) -> Path:
    request = vault / "request.md"
    request.write_text(
        "---\nid: gr-test\nsubsystem: demo-provider\ndescription: Demo provider\nreview_status: approved\n---\n",
        encoding="utf-8",
    )
    return request


def test_dispatch_dry_run_has_no_legacy_registry_step(tmp_path):
    result = run_cli(tmp_path, write_request(tmp_path), "--dry-run")

    assert result.returncode == 0, result.stderr
    output = [json.loads(line) for line in result.stdout.splitlines()]
    assert output[-1]["would"] == ["init no-github", "component.yaml", "handoff"]
    assert not (tmp_path / ".knowledge").exists()


def test_dispatch_handoff_does_not_emit_subsystem_lifecycle_registry(tmp_path):
    init = tmp_path / "action/K-Action_orchestrator/skills/create-action-system/scripts/init_system.py"
    init.parent.mkdir(parents=True)
    init.write_text(
        """
import argparse
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("name")
ap.add_argument("--no-github", action="store_true")
ap.add_argument("--description")
ap.add_argument("--vault-root")
args = ap.parse_args()
target = Path(args.vault_root) / "action" / args.name
target.mkdir(parents=True)
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = run_cli(tmp_path, write_request(tmp_path))

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / ".knowledge/state/action-registry.json").exists()
    handoff = (tmp_path / ".knowledge/reports/generation-handoff-gr-test.md").read_text(encoding="utf-8")
    assert "action-registry" not in handoff
    assert "组件目录不会自动成为 Atomic Action" in handoff
    event_file = next((tmp_path / ".knowledge/events").glob("events-*.jsonl"))
    event = json.loads(event_file.read_text(encoding="utf-8").strip())
    assert "registry" not in event
