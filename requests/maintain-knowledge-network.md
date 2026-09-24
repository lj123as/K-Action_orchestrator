---
desired_action_type: software
cognition_ref: cognition/knowledge-network/README.md
current_action_ref: knowledge-network
revision: bootstrap-v3
reason: exercise the generic maintenance chain end to end
---

# Maintenance intent: knowledge-network

一次通用维护：identity / representation 归 Factory，资产安装归 Host，同一条入口。

```bash
python action/KA-system/tools/ka_system.py maintain \
  action/K-Action_orchestrator/requests/maintain-knowledge-network.md --apply
```
