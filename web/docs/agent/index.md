# Agent 智能体

Agent 是把大模型从「会聊天」变成「会干活」的那一层：给它工具、给它记忆、给它一个循环，它就能自己拆任务、调接口、看结果、再决定下一步。难点不在概念，而在工程：工具怎么设计、循环怎么不跑飞、状态怎么持久化、多 Agent 怎么不被成本和延迟拖垮。本主题用中文笔记 + **浏览器可视化交互演示**，把 ReAct、Function Calling、MCP、LangGraph 一路讲到能做出来的程度。

> 版本参考：LangGraph 0.2+ / AutoGen 0.4+ / CrewAI / MCP 2025 规范。演示不发起真实调用；默认打开 `demos/index.html`。

## 先决知识

- 会调用大模型 API，理解 Function Calling 基本用法
- 已完成[提示词工程](/prompt-engineering/) 主题（结构化输出是工具调用的前提）
- 建议已完成[RAG 检索增强生成](/rag/) 主题（Agent 常把检索当工具）
- Python 基础，能读懂异步/循环逻辑更佳

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位) | `./start.sh 01` | 从 Prompt 到 Agent 的四次演进、能力边界与风险 |
| 2 | [02-Agent核心架构](./notes/02-Agent核心架构) | `./start.sh 02` | 规划 / 记忆 / 工具三要素、感知-决策-行动循环 |
| 3 | [03-ReAct推理范式](./notes/03-ReAct推理范式) | `./start.sh 03` | Thought-Action-Observation 循环、完整 trace、失败模式 |
| 4 | [04-FunctionCalling与MCP](./notes/04-FunctionCalling与MCP) | `./start.sh 04` | 工具设计原则、MCP 架构、手写最小调用循环 |
| 5 | [05-LangGraph状态机](./notes/05-LangGraph状态机) | `./start.sh 05` | StateGraph、条件分支、Human-in-the-loop、断点续跑 |
| 6 | [06-多Agent协作](./notes/06-多Agent协作) | `./start.sh 06` | 主管-工人/辩论/流水线、AutoGen vs CrewAI、成本控制 |
| 7 | [07-记忆与上下文管理](./notes/07-记忆与上下文管理) | `./start.sh 07` | 短期记忆截断与摘要、长期记忆、上下文预算分配 |
| 8 | [08-投研助手实战与FAQ](./notes/08-投研助手实战与FAQ) | `./start.sh 08` | 金融投研助手 Agent 架构与关键代码、面试 FAQ |

## 与其他主题的关系

```
Agent 智能体（本主题） ← 能力集成层
   ├─ 输入输出规范 → 提示词工程（结构化输出 / Function Calling）
   ├─ 知识检索工具 → RAG 检索增强生成
   ├─ 向量记忆 → 向量数据库与 Embedding
   └─ 业务落地 → AI 应用 / 金融技术（投研助手、财富管理）
```

## 如何启动演示

```bash
cd notes/agent
./start.sh          # 浏览器可视化交互
./start.sh 03       # 直达 ReAct 循环步进演示
./start.sh --cli    # 备用终端文字版
```

也可：`python3 main.py agent` / `python3 main.py agent 03`。

## 参考与官方文档

- [ReAct 论文](https://arxiv.org/abs/2210.03629)
- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [AutoGen 官方文档](https://microsoft.github.io/autogen/)
