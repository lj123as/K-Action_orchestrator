---
desired_action_type: software
cognition_ref: cognition/harness-factory/README.md
current_action_ref: harness-factory
revision: 1.0.0
reason: align the descriptor revision with the version declared in component.yaml (post-bootstrap maintenance)
---

# Maintenance intent: harness-factory

Bootstrap created this descriptor with `revision: bootstrap-v1` while `component.yaml` declares
`version: 1.0.0`. Post-bootstrap maintenance goes through the chain, so this intent carries the
change and the software factory writes it:

```bash
python action/K-Action_orchestrator/tools/action_ops.py --apply reconcile \
  action/K-Action_orchestrator/requests/maintain-harness-factory.md
```

