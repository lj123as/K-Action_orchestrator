---
desired_action_type: harness
cognition_ref: cognition/harness/README.md
reason: prove that a type cognition is rejected by harness-factory
model_binding:
  provider: agent-runtime
  model: default
context_binding: {}
---

# Example ActionIntent (harness)

This intent points at **`cognition/harness`**, which is the harness *type* definition
(`action_type: null`). harness-factory must reject it: a type defines what a harness is, it is not
an object to realize. The expected outcome is

```text
cognition defines a type (action_type: null), not an action to realize: cognition/harness/README.md
```

To realize a real harness, point `cognition_ref` at a concrete topic cognition (phase 2 T2 turns
`action/ai-workspace` into exactly such a harness) and give it an explicit `workspace_ref`.

