---
title: KA 模板系统总览
type: guide
tags: [guide, templates, knowledge-network, meta]
created: "2026-01-19"
updated: "2026-01-19"
---

# KA 模板系统总览

> 统一入口：理解 KA 系统的两层模板架构

## 🎯 核心理念

KA 系统的模板分为两个层级，各司其职，协同工作：

```
┌─────────────────────────────────────────────────────┐
│  Level 2: Workflow 层（工作流文档模板）              │
│  位置: cognition/templates/                         │
│  职责: 引导完成认知任务，产出工作文档                 │
│  ─────────────────────────────────────              │
│  文献笔记 → 会议记录 → 研究报告 → 项目文档            │
│                    │                                │
│                    ▼ 产出/引用                       │
│  ─────────────────────────────────────              │
│  Level 1: Schema 层（原子笔记数据结构）              │
│  位置: action/knowledge-network/templates/          │
│  职责: 定义知识网络节点，沉淀原子知识                 │
│  ─────────────────────────────────────              │
│  O·对象 ↔ S·事态 ↔ C·认知 ↔ A·行动                  │
└─────────────────────────────────────────────────────┘
```

---

## 📐 设计原则

### 原子笔记核心原则（Level 1）

| 原则 | 说明 | 实现方式 |
|------|------|---------|
| **单一职责** | 一条笔记 = 一个清晰单位 | O/S/C/A 各自独立 |
| **单一来源** | 知识只在一处定义 | 通过 wikilinks 引用 |
| **可检验性** | 认知可证伪，行动可执行 | claim、steps、success |
| **强链路** | 明确上下游关系 | links 字段规范化 |
| **元数据驱动** | 支持查询和自动化 | YAML frontmatter |

### 工作流模板原则（Level 2）

| 原则 | 说明 | 实现方式 |
|------|------|---------|
| **流程引导** | 引导用户完成认知任务 | 章节结构化 |
| **原子产出** | 指导创建原子笔记 | "原子笔记产出"章节 |
| **聚合呈现** | 汇总原子笔记形成文档 | Dataview 查询 |
| **可交付** | 形成完整可分享的成果 | 结构完整性 |

---

## 🗂️ Level 1: 原子笔记 Schema

**位置**: `action/knowledge-network/templates/`

### 核心模板

| 模板 | 文件前缀 | 职责 | 关键字段 |
|------|---------|------|---------|
| [[action/knowledge-network/templates/TPL_Object|TPL_Object]] | `O·` | 对象/实体定义 | spec, interfaces |
| [[action/knowledge-network/templates/TPL_State|TPL_State]] | `S·` | 事态/场景快照 | window, observations |
| [[action/knowledge-network/templates/TPL_Cognition|TPL_Cognition]] | `C·` | 认知/结论/假设 | claim, evidence, uncertainty |
| [[action/knowledge-network/templates/TPL_Atomic_Generic|TPL_Atomic_Generic]] | 通用 | 快速创建原子笔记 | 基础结构 |

### 可视化辅助模板

| 模板                                                         | 用途           |          |
| ---------------------------------------------------------- | ------------ | -------- |
| [[action/knowledge-network/templates/TPL_Mermaid_Flowchart | Flowchart]]  | 流程图、因果关系 |
| [[action/knowledge-network/templates/TPL_Mermaid_Sequence  | Sequence]]   | 时序交互     |
| [[action/knowledge-network/templates/TPL_Mermaid_Timeline  | Timeline]]   | 时间线      |
| [[action/knowledge-network/templates/TPL_Mermaid_Gantt     | Gantt]]      | 排程甘特图    |
| [[action/knowledge-network/templates/TPL_Mermaid_Mindmap   | Mindmap]]    | 思维导图     |
| [[action/knowledge-network/templates/TPL_Mermaid_Class     | Class]]      | 类图/领域模型  |
| [[action/knowledge-network/templates/TPL_Mermaid_ER        | ER]]         | 实体关系图    |
| [[action/knowledge-network/templates/TPL_Excalidraw_Guide  | Excalidraw]] | 手绘草图     |

### 原子笔记关系网络

```mermaid
flowchart LR
    subgraph Objects
        O1[O·对象A]
        O2[O·对象B]
    end

    subgraph States
        S1[S·事态1]
        S2[S·事态2]
    end

    subgraph Cognitions
        C1[C·认知1]
        C2[C·认知2]
    end

    subgraph Actions
        A1[A·行动1]
        A2[A·行动2]
    end

    O1 --> S1
    O2 --> S1
    S1 --> C1
    S2 --> C2
    C1 --> A1
    C2 --> A2
    A1 --> S2
    A2 --> O1
```

---

## 🗂️ Level 2: 工作流文档模板

**位置**: `cognition/templates/`

### 1_Input - 信息输入类
| 模板 | 职责 | 产出的原子笔记 |
|------|------|---------------|
| [[cognition/templates/1-01_Literature_Note_文献笔记|文献笔记]] | 书籍/论文阅读 | O·概念, C·观点 |
| [[cognition/templates/1-02_Meeting_Note_会议记录|会议记录]] | 会议内容记录 | A·任务, S·决策 |

### 2_Processing - 信息处理类
| 模板 | 职责 | 产出的原子笔记 |
|------|------|---------------|
| [[cognition/templates/2-01_Concept_Note_概念笔记|概念笔记]] | 概念提炼 | O·概念（→objects/）|
| [[cognition/templates/2-02_Knowledge_Note_知识笔记|知识笔记]] | 知识整理 | C·洞见, O·概念 |

### 3_Output - 成果输出类
| 模板 | 职责 | 产出的原子笔记 |
|------|------|---------------|
| [[cognition/templates/3-01_Research_Report_研究报告|研究报告]] | 研究性报告 | S·发现, C·结论, A·建议 |
| [[cognition/templates/3-02_Project_Document_项目文档|项目文档]] | 项目管理 | A·任务, S·里程碑 |

### 4_Periodic - 周期笔记类
| 模板 | 职责 | 产出的原子笔记 |
|------|------|---------------|
| [[4-02_Daily_Note_Summar_日记|日记]] | 每日记录 | A·任务, C·反思 |

### 5_Structure - 结构性工具
| 模板 | 职责 | 产出的原子笔记 |
|------|------|---------------|
| [[cognition/templates/5-01_MOC_内容地图|MOC]] | 知识地图 | 聚合所有类型 |

---

## 🔄 使用流程

### 标准工作流

```mermaid
flowchart TD
    A[开始任务] --> B{任务类型?}

    B -->|信息输入| C[选择 1_Input 模板]
    B -->|知识加工| D[选择 2_Processing 模板]
    B -->|成果输出| E[选择 3_Output 模板]
    B -->|日常记录| F[选择 4_Periodic 模板]
    B -->|组织整理| G[选择 5_Structure 模板]

    C --> H[执行工作流程]
    D --> H
    E --> H
    F --> H
    G --> H

    H --> I{识别到原子知识?}

    I -->|新概念/实体| J[创建 O· 对象笔记]
    I -->|关系/场景| K[创建 S· 事态笔记]
    I -->|结论/假设| L[创建 C· 认知笔记]
    I -->|任务/计划| M[创建 A· 行动笔记]
    I -->|无| N[继续工作流程]

    J --> O[建立双向链接]
    K --> O
    L --> O
    M --> O
    N --> H

    O --> P{工作流完成?}
    P -->|否| H
    P -->|是| Q[完成文档，更新知识网络]
```

### 快速参考

**何时创建原子笔记？**

| 场景 | 创建类型 | 示例 |
|------|---------|------|
| 发现新概念/术语/工具 | O·对象 | `O·React Hooks` |
| 观察到关系/现象/场景 | S·事态 | `S·路由器天线配置分析·20260119` |
| 形成可检验的结论 | C·认知 | `C·双天线设计提升信号稳定性` |
| 需要执行的任务/实验 | A·行动 | `A·天线配置测试·验证信号强度` |

---

## 📊 模板系统架构图

```mermaid
graph TB
    subgraph "用户工作流"
        U[用户] --> W1[阅读文献]
        U --> W2[参加会议]
        U --> W3[做研究]
        U --> W4[管理项目]
        U --> W5[日常反思]
    end

    subgraph "Level 2: Workflow Templates"
        W1 --> T1[1-01_Literature_Note]
        W2 --> T2[1-02_Meeting_Note]
        W3 --> T3[3-01_Research_Report]
        W4 --> T4[3-02_Project_Document]
        W5 --> T5[4-01_Daily_Note]
    end

    subgraph "Level 1: Atomic Schema"
        T1 --> A1[TPL_Object]
        T1 --> A3[TPL_Cognition]
        T3 --> A2[TPL_State]
        T3 --> A3
        T4 --> A4
        T5 --> A3
        T5 --> A4
    end

    subgraph "Knowledge Network"
        A1 --> KN[O·S·C·A· 原子笔记网络]
        A2 --> KN
        A3 --> KN
        A4 --> KN
    end
```

---

## 🔗 相关文档

### 架构与规范
- [[cognition/knowledge-network/02-schema|原子笔记：原则·类型·字段·链接规范]]
- [[action/knowledge-network/templates/README|模板系统说明]]
- [[cognition/templates/README|认知层模板系统 README]]
- [[cognition/templates/UPGRADE_GUIDE|模板系统升级指南]]

### KA 系统文档
- [[cognition/如何构建认知-行动系统|KA系统构建指南]]
- [[README|KA-Vault 项目概览]]

---

## ✅ 检查清单

### 创建原子笔记前
- [ ] 确认是单一职责（一条笔记 = 一个清晰单位）
- [ ] 检查是否已存在类似笔记（单一来源原则）
- [ ] 选择正确的类型（O/S/C/A）
- [ ] 准备好必要的链接关系

### 创建工作流文档前
- [ ] 选择适合任务类型的模板
- [ ] 了解该模板会产出哪些原子笔记
- [ ] 准备好相关的原子笔记链接

### 完成工作后
- [ ] 检查原子笔记产出章节
- [ ] 确保所有新知识都已沉淀为原子笔记
- [ ] 验证双向链接完整性
- [ ] 更新相关 MOC

---

**文档版本**: 1.0
**创建日期**: 2026-01-19
**维护者**: KA 系统

> 💡 这是 KA 模板系统的统一入口，建议收藏此页面以便快速访问
