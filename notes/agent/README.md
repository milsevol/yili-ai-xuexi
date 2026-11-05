# agent · Agent 智能体

个人学习知识库的 AI 主题笔记：从零手写一个 Agent，到 ReAct、Function Calling/MCP、LangGraph、记忆与多 Agent，最后补齐生产工程能力并落地一个企业级智能投研平台案例。

## 章节

| 章节 | 内容 |
| --- | --- |
| 01 概述与定位 | Agent 是什么、Agent 的一天、适用边界、常见误解 |
| 02 从零跑通第一个 Agent | 环境准备、v0→v1→v2、手写 Function Calling 循环、调试排错 |
| 03 Agent 核心架构 | 规划 / 记忆 / 工具三要素、循环控制、架构选型 |
| 04 ReAct 推理范式 | Thought-Action-Observation trace、循环检测、失败模式 |
| 05 Function Calling 与 MCP | 完整协议、并行/流式调用、工具设计、MCP 生态 |
| 06 LangGraph 状态机 | StateGraph、条件边、Human-in-the-loop、断点续跑 |
| 07 记忆与上下文管理 | 历史摘要、长期记忆、上下文预算与工具结果压缩 |
| 08 多 Agent 协作 | 主管-工人 / 辩论 / 流水线、Supervisor 实现、成本控制 |
| 09 生产工程化与评估 | 可观测、离线/在线评估、护栏、成本、发布与 SLO |
| 10 企业级实战：智能投研平台 | 多租户、权限、工具网关、审批、合规、部署与运维 |

## 启动演示

```bash
./start.sh          # 启动本地服务并打开交互页
./start.sh 04       # 直达 ReAct 真实循环演示
./start.sh 10       # 企业级投研平台案例演示
./start.sh --port 9000  # 指定本地服务端口
./start.sh --cli    # 终端摘要版
```

第 04/10 章的「真实运行」会由 DeepSeek 自主选择工具并生成真实 trace，Key 通过环境变量 `DEEPSEEK_API_KEY` 提供。

第 02 章的代码不依赖交互页，可单独复制运行；没有 API Key 时使用内置离线模型，仍可跑通完整消息流。

也可在仓库根目录：`python3 main.py agent`。
