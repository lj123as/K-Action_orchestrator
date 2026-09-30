---
desired_action_type: software
cognition_ref: cognition/ai-workspace/README.md
reason: give the AI Workspace component its own Atomic Action identity
revision: bootstrap-v1
provenance: managed:software-factory
profiles: [agentic]
---

# ActionIntent: ai-workspace

AI Workspace 是有 component.yaml、有资产安装、也有 cognition topic 的组件，但一直没有自己的
Software Atomic Action descriptor——身份只在组件层存在，没进入 Action 层（阶段二 T2 步骤 5）。

它保持 `action_type: software`：它的形状是完整的 software（component.yaml、deploy 资产清单、
Obsidian 插件 Installation、version），而不是 harness 的引用式绑定（见 [[cognition/ai-workspace/README]] 与
[[cognition/harness/README]]）。Harness 身份由独立的 `workspace-harness` 承担，两者不是同一个 Action。

本意图是**声明**，不是手工写状态文件：descriptor 由
[[action/K-Action_orchestrator]] 解析出 software-factory 后经它生成。

```bash
python action/K-Action_orchestrator/tools/action_ops.py reconcile --dry-run \
  action/K-Action_orchestrator/requests/ai-workspace.md
```
