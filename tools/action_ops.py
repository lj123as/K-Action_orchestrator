#!/usr/bin/env python3
"""K-Action Orchestrator Runtime API: unified Action Operation entry.

Action Request (target + action_type + operation) -> resolve Factory via KA-System Registry -> call provider capability ->
record/update .knowledge/state/action-instances.json + events.

Operations: create (new instance), update (existing instance fields/state),
execute (state machine running/done), validate (instance + provider check).
create is just one operation; maintenance is NOT a separate architecture.
Stdlib only.
"""
import argparse, importlib.util, json, os, sys
from datetime import datetime, timezone
from pathlib import Path

VAULT = Path(os.environ.get("KA_VAULT_ROOT", ".")).resolve()
STATE = VAULT / ".knowledge/state"
INSTANCES = STATE / "action-instances.json"
EVENTS = VAULT / ".knowledge/events"
N = chr(10)
OPS = ("create", "update", "execute", "validate", "register", "catalog", "reconcile")

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def parse_fm(text):
    fm = {}
    if text.startswith("---" + N):
        end = text.find(N + "---", 4)
        if end != -1:
            last_key = None
            for line in text[4:end].splitlines():
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                if s.startswith("- ") and last_key:
                    fm.setdefault(last_key, []).append(s[2:].strip())
                    continue
                if ":" in s:
                    if s.endswith(":"):
                        last_key = s[:-1].strip()
                        fm.setdefault(last_key, [])
                    else:
                        k, v = s.split(":", 1)
                        fm[k.strip()] = v.strip().strip(chr(34))
    return fm

def load_action_types():
    mf = VAULT / ".knowledge/manifest.yaml"
    types = {}
    if not mf.exists():
        return types
    text = mf.read_text(encoding="utf-8", errors="ignore")
    in_types = False
    cur = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("action_types:"):
            in_types = True
            continue
        if not in_types or not s or s.startswith("#"):
            continue
        if s.startswith("- id:"):
            if cur:
                types[cur["id"]] = cur
            cur = {"id": s.split(":", 1)[1].strip(), "creators": [], "operations": []}
        elif s.startswith("creators:") and cur is not None:
            raw = s.split(":", 1)[1].strip()
            cur["creators"] = [c.strip().strip(chr(91)) for c in raw.strip(chr(93)).split(",") if c.strip().strip(chr(91))]
        elif s.startswith("operations:") and cur is not None:
            raw = s.split(":", 1)[1].strip()
            cur["operations"] = [c.strip() for c in raw.strip(chr(91)).strip(chr(93)).split(",") if c.strip()]
        elif s.startswith("-") and cur is not None and s[1:].strip():
            cur["creators"].append(s[1:].strip())
    if cur:
        types[cur["id"]] = cur
    return types

def load_provider(provider, mod, fn_name):
    path = VAULT / "action" / provider / mod
    if not path.exists():
        return None, None
    try:
        spec_l = importlib.util.spec_from_file_location("p_" + provider + "_" + mod.split(".")[0], path)
        m = importlib.util.module_from_spec(spec_l)
        spec_l.loader.exec_module(m)
        return m, getattr(m, fn_name, None)
    except Exception as e:
        return None, "provider load failed: " + str(e)[:200]

def _registry_tool_path() -> Path:
    return Path(__file__).resolve().parents[2] / "KA-system/tools/action_type_registry.py"


def _factory_install_root(factory):
    """Install root declared by the FactoryRegistration deployment environment."""
    raw = str((factory or {}).get("install_root") or "").strip()
    return Path(raw).expanduser().resolve() if raw else None


def resolve_entrypoint_via_registry(entrypoint, install_root=None):
    """Resolve a Provider entrypoint with the KA-System Registry predicate.

    The install root comes from the FactoryRegistration's deployment environment, so
    the Registry and the Orchestrator validate with identical inputs. There is no
    second vault-only predicate left in this file.
    """
    tool = _registry_tool_path()
    if not tool.exists():
        return None, "registry tool not found: " + str(tool)
    try:
        spec_l = importlib.util.spec_from_file_location("action_type_registry_entrypoint", tool)
        module = importlib.util.module_from_spec(spec_l)
        spec_l.loader.exec_module(module)
        return module.resolve_entrypoint(VAULT, entrypoint, install_root)
    except Exception as exc:
        return None, "registry entrypoint resolution failed: " + str(exc)[:200]


def load_provider_entrypoint(provider, entrypoint, fn_name, install_root=None):
    # Entrypoint resolution is owned by the KA-System Registry: one predicate, so the
    # Registry and the Orchestrator can never disagree about what is loadable.
    resolved, error = resolve_entrypoint_via_registry(entrypoint, install_root)
    if error:
        return None, error
    path = Path(resolved)
    if not path.is_absolute():
        path = (VAULT / resolved).resolve()
    if not path.is_file():
        return None, "provider entrypoint not found: " + str(entrypoint)
    try:
        spec_l = importlib.util.spec_from_file_location("p_" + provider, path)
        m = importlib.util.module_from_spec(spec_l)
        spec_l.loader.exec_module(m)
        return m, getattr(m, fn_name, None)
    except Exception as e:
        return None, "provider load failed: " + str(e)[:200]

def call_provider(provider, fn_name, *args, entrypoint=None, install_root=None):
    if entrypoint:
        _, fn = load_provider_entrypoint(provider, entrypoint, fn_name, install_root)
        if isinstance(fn, str):
            return None, fn
        if not fn:
            return None, fn_name + " not found in provider " + provider
        try:
            return fn(*args), None
        except Exception as e:
            return None, fn_name + " failed: " + str(e)[:200]
    for mod in ("action_provider.py", "design_model.py", "design_model_provider.py"):
        m, fn = load_provider(provider, mod, fn_name)
        if isinstance(fn, str):
            return None, fn
        if fn:
            try:
                return fn(*args), None
            except Exception as e:
                return None, fn_name + " failed: " + str(e)[:200]
    return None, fn_name + " not found in provider " + provider

def resolve_factory(action_type):
    path = Path(__file__).resolve().parents[2] / "KA-system/tools/action_type_registry.py"
    try:
        spec_l = importlib.util.spec_from_file_location("action_type_registry", path)
        module = importlib.util.module_from_spec(spec_l)
        spec_l.loader.exec_module(module)
        result = module.resolve(action_type, VAULT)
        if result.get("exit") == 0:
            result["_registry_module"] = module
        return result
    except Exception as e:
        return {"exit": 2, "error": "registry resolution failed: " + str(e)[:200]}

def op_reconcile(fm, apply=False):
    action_type = str(fm.get("desired_action_type") or "").strip()
    if not action_type:
        return {"exit": 2, "error": "missing action_type: ActionIntent requires desired_action_type"}
    resolved = resolve_factory(action_type)
    if resolved.get("exit") != 0:
        return resolved
    factory = resolved["factory"]
    registry = resolved["_registry_module"]
    cognition_ref = str(fm.get("cognition_ref") or "").strip()
    cognition_path = (VAULT / cognition_ref).resolve()
    if not cognition_path.is_relative_to(VAULT):
        return {"exit": 2, "error": "cognition_ref must stay inside the vault"}
    cognition = {"ref": cognition_ref}
    if cognition_ref and cognition_path.is_file():
        cognition["content"] = cognition_path.read_text(encoding="utf-8", errors="ignore")
    current_state = registry.find_action(
        fm.get("current_action_ref"),
        cognition_ref,
        action_type,
        VAULT,
    )
    intent = {
        "cognition_ref": cognition_ref,
        "desired_action_type": action_type,
        "current_action_ref": str(fm.get("current_action_ref") or ""),
        "reason": str(fm.get("reason") or ""),
        "revision": str(fm.get("revision") or ""),
    }
    for key in ("requirements", "design_blocks", "acceptance", "template_src", "profiles"):
        if fm.get(key):
            intent[key] = fm[key]
    context = {
        key: fm[key]
        for key in ("action_id", "workspace_ref", "provenance", "operation")
        if fm.get(key)
    }
    request = {
        "intent": intent,
        "cognition": cognition,
        "current_state": current_state,
        "constraints": {},
        "context": context,
    }
    provider_id = factory["provider_id"]
    planned, error = call_provider(provider_id, "plan", request, VAULT,
                                    entrypoint=factory["entrypoint"],
                                    install_root=_factory_install_root(factory))
    if error or not planned or planned.get("exit") != 0:
        return {"exit": 2, "error": error or (planned or {}).get("error", "factory plan failed")}
    plan = planned.get("plan")
    output = {"exit": 0, "factory": factory, "plan": plan}
    if apply:
        applied, error = call_provider(provider_id, "apply", plan, request, VAULT,
                                       entrypoint=factory["entrypoint"],
                                       install_root=_factory_install_root(factory))
        if error or not applied or applied.get("exit") != 0:
            return {"exit": 2, "error": error or (applied or {}).get("error", "factory apply failed")}
        output["result"] = applied.get("result")
    return output

def event(name, payload):
    EVENTS.mkdir(parents=True, exist_ok=True)
    f = EVENTS / ("events-" + datetime.now(timezone.utc).strftime("%Y%m%d") + ".jsonl")
    rec = {"event": name, "ts": now_iso()}
    rec.update(payload)
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + N)

def load_instances():
    if INSTANCES.exists():
        try:
            return json.loads(INSTANCES.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_instances(data):
    STATE.mkdir(parents=True, exist_ok=True)
    data.setdefault("version", 1)
    data["updated"] = now_iso()
    INSTANCES.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

def find_instance(data, fm):
    iid = str(fm.get("instance_id", "")).strip()
    subj = str(fm.get("subject", "")).strip()
    for inst in data.get("instances", []):
        if iid and inst.get("instance_id") == iid:
            return inst
        if subj and inst.get("subject") == subj and str(inst.get("action_type")) == str(fm.get("action_type", "")).strip():
            return inst
    return None

def op_create(fm, types):
    atype = str(fm.get("action_type", "")).strip()
    resolved = resolve_factory(atype)
    if resolved.get("exit") != 0:
        return {"exit": 2, "error": resolved.get("error", "FactoryUnavailable")}
    factory = resolved["factory"]
    provider = factory["provider_id"]
    cap_instance, cap_err = call_provider(
        provider,
        "create_instance",
        fm,
        VAULT,
        entrypoint=factory.get("entrypoint"),
        install_root=_factory_install_root(factory),
    )
    if cap_err:
        return {"exit": 2, "error": cap_err}
    if not isinstance(cap_instance, dict) or cap_instance.get("exit") != 0:
        return {"exit": 2, "error": (cap_instance or {}).get("error", "factory create_instance failed")}
    cap_out = cap_instance.get("instance") if cap_instance and cap_instance.get("exit") == 0 else None
    if not isinstance(cap_out, dict):
        return {"exit": 2, "error": "factory create_instance returned no instance"}
    instance = {
        "instance_id": "act-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "spec_id": fm.get("spec_id", ""),
        "action_type": atype,
        "intent": fm.get("intent", ""),
        "subject": fm.get("subject", ""),
        "provider": provider,
        "state": "created",
        "input": {k: fm[k] for k in ("requirements", "input") if fm.get(k)},
        "capability_instance": cap_out,
        "capability_error": cap_err,
        "created_at": now_iso(),
        "updated_at": "",
        "last_run": "",
        "health": "ok",
    }
    data = load_instances()
    data.setdefault("instances", []).append(instance)
    save_instances(data)
    event("action.instance.created", {"instance_id": instance["instance_id"], "spec_id": instance["spec_id"], "action_type": atype, "provider": provider})
    return {"status": "created", "instance": instance}

def resolve_instance_factory(instance):
    """Resolve an existing instance through the active Action Type Registry."""
    action_type = str(instance.get("action_type") or "").strip()
    if not action_type:
        return None, "instance missing action_type"
    resolved = resolve_factory(action_type)
    if resolved.get("exit") != 0:
        return None, resolved.get("error", "FactoryUnavailable")
    return resolved["factory"], None

def op_update(fm, types):
    data = load_instances()
    inst = find_instance(data, fm)
    if not inst:
        return {"exit": 2, "error": "instance not found (need instance_id or subject+action_type)"}
    factory, factory_error = resolve_instance_factory(inst)
    if factory_error:
        return {"exit": 2, "error": factory_error}
    inst["provider"] = factory["provider_id"]
    cap_out, cap_err = call_provider(
        factory["provider_id"], "update_instance", inst, fm, VAULT,
        entrypoint=factory.get("entrypoint"),
        install_root=_factory_install_root(factory),
    )
    if cap_err:
        return {"exit": 2, "error": cap_err}
    if not isinstance(cap_out, dict) or cap_out.get("exit") != 0:
        return {"exit": 2, "error": (cap_out or {}).get("error", "factory update_instance failed")}
    inst.update(cap_out.get("instance") or {})
    inst["state"] = "updated"
    inst["updated_at"] = now_iso()
    save_instances(data)
    event("action.instance.updated", {"instance_id": inst["instance_id"], "action_type": inst["action_type"]})
    return {"status": "updated", "instance": inst}

def op_execute(fm, types):
    data = load_instances()
    inst = find_instance(data, fm)
    if not inst:
        return {"exit": 2, "error": "instance not found (need instance_id or subject+action_type)"}
    factory, factory_error = resolve_instance_factory(inst)
    if factory_error:
        return {"exit": 2, "error": factory_error}
    inst["provider"] = factory["provider_id"]
    inst["state"] = "running"
    inst["last_run"] = now_iso()
    save_instances(data)
    cap_out, cap_err = call_provider(
        factory["provider_id"], "execute", inst, fm, VAULT,
        entrypoint=factory.get("entrypoint"),
        install_root=_factory_install_root(factory),
    )
    final = "done"
    if cap_out and cap_out.get("exit") == 0:
        final = cap_out.get("state", "done")
        if cap_out.get("executed") is False:
            final = "failed"
    elif cap_out and cap_out.get("exit") != 0:
        final = "failed"
    elif cap_err:
        final = "failed"
    inst["state"] = final
    inst["last_end"] = now_iso() if final in ("done", "failed") else ""
    if isinstance(cap_out, dict):
        for k in ("maintenance", "note"):
            if cap_out.get(k) is not None:
                inst[k] = cap_out[k]
        if cap_out.get("error"):
            inst["capability_error"] = cap_out["error"]
    if cap_err:
        inst["capability_error"] = cap_err
    save_instances(data)
    event("action.instance.executed", {"instance_id": inst["instance_id"], "state": final})
    return {"status": final, "instance": inst}

def op_validate(fm, types):
    data = load_instances()
    inst = find_instance(data, fm)
    issues = []
    if not inst:
        issues.append("instance not found")
    else:
        if not inst.get("provider"):
            issues.append("missing provider")
        factory, factory_error = resolve_instance_factory(inst)
        if factory_error:
            issues.append(factory_error)
            cap_out, cap_err = None, None
        else:
            inst["provider"] = factory["provider_id"]
            cap_out, cap_err = call_provider(
                factory["provider_id"], "validate", inst, fm, VAULT,
                entrypoint=factory.get("entrypoint"),
        install_root=_factory_install_root(factory),
            )
        if cap_out and cap_out.get("exit") == 0:
            pass
        else:
            issues.append(cap_err or "provider validate failed")
    if issues:
        return {"exit": 2, "valid": False, "issues": issues}
    return {"exit": 0, "valid": True, "instance": inst}

def component_declared_types(path):
    """Parse action_types block of a component.yaml (Type Contract 声明源)."""
    types, in_at = [], False
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.rstrip()
        if s.strip() == "action_types:":
            in_at = True
            continue
        if not in_at:
            continue
        if s.strip().startswith("- "):
            types.append(s.strip()[2:].strip())
        elif s and not s.startswith(" ") and s.strip() and not s.strip().startswith("#"):
            in_at = False
    return types


def registry_entry(type_id, provider, ops):
    return ["  - id: " + type_id,
            "    description: Registered by K-Action_orchestrator register (Type Contract reconcile)",
            "    owner: ka-system",
            "    creators: [" + provider + "]",
            "    operations: [" + ", ".join(ops) + "]"]


def op_register(fm, types, apply=False):
    """Loop 3: reconcile Type Contract (component.yaml) into Action System Registry (manifest action_types).

    Source of truth for first discovery is the source contract, not registration
    by "an Action registering itself". register/reconcile only maintains the
    registry (missing types / creator mismatches), dry-run default.
    """
    atype = str(fm.get("action_type", "")).strip()
    if atype not in types:
        return {"exit": 2, "error": "action_type unknown (use an existing catalog type to locate provider): " + atype}
    provider = (types[atype]["creators"] or [""])[0]
    cy = VAULT / "action" / provider / "component.yaml"
    if not cy.exists():
        return {"exit": 2, "error": "provider component.yaml not found: " + str(cy)}
    declared = component_declared_types(cy)
    if not declared:
        return {"exit": 2, "error": provider + " component.yaml declares no action_types"}
    mf = VAULT / ".knowledge/manifest.yaml"
    if not mf.exists():
        return {"exit": 2, "error": "manifest not found: " + str(mf)}
    raw = mf.read_text(encoding="utf-8", errors="ignore")
    mf_nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.split(mf_nl)
    missing, creator_fixes = [], []
    for dt in declared:
        if dt not in types:
            missing.append(dt)
        elif provider not in types[dt]["creators"]:
            creator_fixes.append((dt, provider))
    changed_lines = list(lines)
    if apply:
        if not lines[-1]:
            changed_lines = lines[:-1]
        for dt in missing:
            changed_lines += registry_entry(dt, provider, ["create", "update", "execute", "validate"])
        for dt, prov in creator_fixes:
            # find the "creators:" line under the matching - id: dt block
            in_block = False
            for i, ln in enumerate(changed_lines):
                s = ln.strip()
                if s.startswith("- id:") and s.split(":", 1)[1].strip() == dt:
                    in_block = True
                    continue
                if in_block and ln.strip().startswith("creators:"):
                    raw_c = ln.strip().split(":", 1)[1].strip()
                    raw_c = raw_c.strip("[ ]").strip()
                    cur = [c.strip() for c in raw_c.split(",") if c.strip()]
                    if prov not in cur:
                        indent = ln[:len(ln) - len(ln.lstrip())]
                        changed_lines[i] = indent + "creators: [" + ", ".join(cur + [prov]) + "]"
                    in_block = False
        mf.write_text(mf_nl.join(changed_lines) + mf_nl, encoding="utf-8")
    event("action.type.registered", {"action_type": atype, "provider": provider,
                                     "missing": missing, "creator_fixes": [x[0] for x in creator_fixes],
                                     "applied": apply})
    return {"exit": 0, "action_type": atype, "provider": provider,
            "declared_types": declared, "missing_types": missing,
            "creator_added": [x[0] for x in creator_fixes],
            "applied": apply, "manifest": str(mf.relative_to(VAULT))}


def _utf8_io():
    for stream in (sys.stdin, sys.stdout):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

def main():
    _utf8_io()
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=list(OPS))
    ap.add_argument("request", nargs="?", default="-")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true", help="register: write registry reconcile changes into manifest")
    args = ap.parse_args()
    if args.dry_run and args.apply:
        ap.error("--dry-run and --apply are mutually exclusive")
    if args.command == "catalog":
        types = load_action_types()
        print(json.dumps({
            "action_types": [
                {"id": tid, "creators": meta.get("creators", []), "operations": meta.get("operations", [])}
                for tid, meta in sorted(types.items())
            ]
        }, ensure_ascii=False, indent=1))
        return 0
    text = sys.stdin.read() if args.request == "-" else Path(args.request).read_text(encoding="utf-8", errors="ignore")
    fm = parse_fm(text)
    op = args.command
    if op == "reconcile":
        result = op_reconcile(fm, apply=args.apply)
        if result.get("exit") == 2:
            print(result.get("error", "failed"), file=sys.stderr)
            return 2
        if not args.apply:
            result["dry_run"] = True
        print(json.dumps({k: v for k, v in result.items() if k != "exit"}, ensure_ascii=False, indent=1))
        return 0
    atype = str(fm.get("action_type", "")).strip()
    review = str(fm.get("review_status", "")).strip()
    status = str(fm.get("status", "")).strip()
    types = load_action_types()
    if atype not in types:
        print("unknown action_type: " + atype + " (known: " + ",".join(sorted(types)) + ")", file=sys.stderr)
        return 2
    allowed = types[atype].get("operations") or []
    if op not in allowed:
        print("operation " + op + " not allowed for action_type " + atype + " (allowed: " + ",".join(allowed) + ")", file=sys.stderr)
        return 2
    if op == "create":
        if review != "approved" and status != "approved":
            print("gate: create spec must be approved", file=sys.stderr)
            return 2
        result = op_create(fm, types)
    elif op == "update":
        result = op_update(fm, types)
    elif op == "execute":
        result = op_execute(fm, types)
    elif op == "register":
        result = op_register(fm, types, apply=args.apply)
    else:
        result = op_validate(fm, types)
    if result.get("exit") == 2:
        print(result.get("error", "failed"), file=sys.stderr)
        return 2
    if args.dry_run:
        result = dict(result, dry_run=True)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0

if __name__ == "__main__":
    sys.exit(main())
