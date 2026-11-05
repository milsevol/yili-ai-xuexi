# Agent 智能体

Agent 是把大模型从「会聊天」变成「会干活」的那一层：给它工具、给它记忆、给它一个循环，它就能自己拆任务、调接口、看结果、再决定下一步。难点不在概念，而在工程：工具怎么设计、循环怎么不跑飞、状态怎么持久化、多 Agent 怎么不被成本和延迟拖垮。

本主题共 10 章，按「概念 → 动手入门 → 核心机制 → 框架编排 → 生产工程 → 企业级案例」递进：先用约 100 行 Python 手写一个能跑的 Agent，再深入 ReAct、Function Calling、MCP、LangGraph、记忆与多 Agent，最后补齐评估、可观测、安全、成本等生产能力，并落到一个可评审的企业级智能投研平台案例。重点章节配浏览器可视化交互演示，纯工程章节以可直接运行的代码与清单为主。

> 版本参考：LangGraph 0.2+ / AutoGen 0.4+ / CrewAI / MCP 2025 规范。演示默认使用内置样例；标注「真实运行」的按钮会调用 DeepSeek（需配置 `DEEPSEEK_API_KEY`）。

## 先决知识

- 会调用大模型 API，理解 Function Calling 基本用法
- 已完成[提示词工程](/prompt-engineering/) 主题（结构化输出是工具调用的前提）
- 建议已完成[RAG 检索增强生成](/rag/) 主题（Agent 常把检索当工具）
- Python 基础，能读懂异步/循环逻辑更佳

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位) | `./start.sh 01` | Agent 是什么、Agent 的一天、适用边界、常见误解 |
| 2 | [02-从零跑通第一个Agent](./notes/02-从零跑通第一个Agent) | — | 环境准备、v0→v1→v2、手写 Function Calling 循环、调试排错 |
| 3 | [03-Agent核心架构](./notes/03-Agent核心架构) | `./start.sh 03` | 规划 / 记忆 / 工具三要素、感知-决策-行动循环、架构选型 |
| 4 | [04-ReAct推理范式](./notes/04-ReAct推理范式) | `./start.sh 04` | Thought-Action-Observation 循环、完整 trace、失败模式 |
| 5 | [05-FunctionCalling与MCP](./notes/05-FunctionCalling与MCP) | `./start.sh 05` | 完整协议、并行/流式调用、工具设计、MCP 接入 |
| 6 | [06-LangGraph状态机](./notes/06-LangGraph状态机) | `./start.sh 06` | StateGraph、条件分支、Human-in-the-loop、断点续跑 |
| 7 | [07-记忆与上下文管理](./notes/07-记忆与上下文管理) | `./start.sh 07` | 短期记忆截断与摘要、长期记忆、上下文预算分配 |
| 8 | [08-多Agent协作](./notes/08-多Agent协作) | `./start.sh 08` | 主管-工人/辩论/流水线、Supervisor 实现、成本控制 |
| 9 | [09-生产工程化与评估](./notes/09-生产工程化与评估) | — | 可观测、离线/在线评估、护栏、成本、发布与 SLO |
| 10 | [10-企业级实战：智能投研平台](./notes/10-企业级实战智能投研平台) | `./start.sh 10` | 多租户、权限、工具网关、审批、合规、部署与运维 |

## 与其他主题的关系

```
Agent 智能体（本主题） ← 能力集成层
   ├─ 输入输出规范 → 提示词工程（结构化输出 / Function Calling）
   ├─ 知识检索工具 → RAG 检索增强生成
   ├─ 向量记忆 → 向量数据库与 Embedding
   └─ 业务落地 → AI 应用 / 金融技术（投研平台、财富管理）
```

## 如何启动演示

```bash
cd notes/agent
./start.sh          # 浏览器可视化交互
./start.sh 04       # 直达 ReAct 循环步进演示
./start.sh 10       # 企业级投研平台案例演示
./start.sh --cli    # 备用终端文字版
```

也可：`python3 main.py agent` / `python3 main.py agent 04`。

## 推荐学习方式

1. **先跑再读**：第 02 章的代码可以直接复制运行，没有 API Key 也能用内置离线模型跑通消息流。
2. **每章动手改一处**：加一个工具、改一次路由、加一条护栏，比只看不写有效得多。
3. **带着问题读第 09/10 章**：如果你要上线，先看上线检查清单，再回头看前面哪些机制还没补。

## 参考与官方文档

- [ReAct 论文](https://arxiv.org/abs/2210.03629)
- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [AutoGen 官方文档](https://microsoft.github.io/autogen/)
- [Anthropic: Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
