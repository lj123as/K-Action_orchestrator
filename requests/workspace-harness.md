---
desired_action_type: harness
cognition_ref: cognition/workspace-harness/README.md
reason: realize the human-facing interactive scenario harness hosted by AI Workspace
model_binding:
  provider: pi
  model: default
runtime_provider: pi
execution_semantics: agent-loop
state_semantics: session
context_binding:
  ref: cognition/ai-workspace/README.md
---

# ActionIntent: workspace-harness

第一个真实的场景 harness。它把「人机交互侧的认知工作」这一场景声明成一个 Harness Atomic
Action，供 AI Workspace 承载（见 [[cognition/workspace-harness/README]]）。

场景化发生在 descriptor 层，不发生在 runtime 层：runtime 绑定到 Runtime Provider 词汇表里的
`pi`，场景差异表达为这里的绑定字段。

```bash
python action/K-Action_orchestrator/tools/action_ops.py reconcile \
  action/K-Action_orchestrator/requests/workspace-harness.md --dry-run
```
