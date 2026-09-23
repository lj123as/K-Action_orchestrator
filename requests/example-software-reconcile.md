---
desired_action_type: software
cognition_ref: cognition/harness-factory/README.md
current_action_ref: harness-factory
reason: prove the KA-System Registry -> K-Action_orchestrator -> software-factory chain
revision: bootstrap-v1
---

# Example ActionIntent (software)

A human-written intent. The orchestrator resolves the Factory for `software` only through the
KA-System Action Type Registry, then asks that Factory to plan. Without `--apply` nothing is written.

```bash
python action/K-Action_orchestrator/tools/action_ops.py reconcile --dry-run \
  action/K-Action_orchestrator/requests/example-software-reconcile.md
```

