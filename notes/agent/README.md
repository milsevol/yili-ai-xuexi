# agent · Agent 智能体

个人学习知识库的 AI 主题笔记：从 ReAct 循环到 LangGraph 编排与多 Agent 协作。

## 章节

| 章节 | 内容 |
| --- | --- |
| 01 概述与定位 | Prompt→RAG→Agent→多 Agent 演进、能力边界与风险 |
| 02 Agent 核心架构 | 规划 / 记忆 / 工具三要素与循环控制 |
| 03 ReAct 推理范式 | Thought-Action-Observation trace、失败模式 |
| 04 Function Calling 与 MCP | 工具设计原则、MCP 协议与生态 |
| 05 LangGraph 状态机 | StateGraph、条件边、Human-in-the-loop、断点续跑 |
| 06 多 Agent 协作 | 主管-工人 / 辩论 / 流水线、成本控制 |
| 07 记忆与上下文管理 | 历史摘要、长期记忆、上下文预算分配 |
| 08 投研助手实战与 FAQ | 金融投研 Agent 架构与关键代码、面试 FAQ |

## 启动演示

```bash
./start.sh          # 浏览器可视化交互
./start.sh 03       # 直达 ReAct 循环步进演示
./start.sh --cli    # 终端摘要版
```

也可在仓库根目录：`python3 main.py agent`。
