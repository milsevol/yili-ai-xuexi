# 金融 Agent 平台实战

这一主题不再是"再学一个框架"，而是**完整交付一个企业内部多租户的垂直 Agent 平台**：平台方提供模型、工具、知识库、运行时与审计，业务部门在其上注册 MCP、创建 Agent、提交审核、上线调用。

和 [Agent 智能体](/agent/) 的关系：Agent 主题讲"一个 Agent 怎么工作"，本主题讲"几十个 Agent 怎么在一个组织里被安全地生产和管理"。前者是发动机，后者是工厂。

本主题共 5 章，按真实项目顺序组织：需求 → 设计 → 架构 → 部署 → 验收。配套一个可运行 Demo（FastAPI + SQLite + Vue 3），内置两家租户、三种角色，可完整体验注册 MCP、上架 Agent、审批发布、真实模型调用、运行时鉴权与审计追溯。

> 版本参考：FastAPI 0.104+ / Vue 3.5 / MCP 2025 规范 / DeepSeek Function Calling。Demo 默认调用 DeepSeek 真实模型并执行真实工具逻辑（行情、财报、研报、合规、计算器为演示数据集，自定义 MCP 会真实请求注册端点）；未配置 `DEEPSEEK_API_KEY` 时自动降级为离线模拟，并在步骤中标注。

## 先决知识

- 完成 [Agent 智能体](/agent/) 主题（工具调用、ReAct、MCP 基本概念）
- 了解 [RAG 检索增强生成](/rag/)（知识库类 Agent 的常见形态）
- 会写基础 Python 与 Vue，能读懂 FastAPI 路由
- 了解 PostgreSQL 与 Docker 的基本用法

## 学习路径

| 顺序 | 笔记 | 内容 |
| --- | --- | --- |
| 1 | [01-项目需求与业务场景](./notes/01-项目需求与业务场景) | 平台定位、角色与权限、场景清单、功能与非功能需求、验收指标 |
| 2 | [02-平台设计与领域模型](./notes/02-平台设计与领域模型) | 领域模型与 ER、生命周期状态机、租户隔离、RBAC、接口与表结构 |
| 3 | [03-技术架构与核心链路](./notes/03-技术架构与核心链路) | 分层架构、Agent 运行时、MCP 网关、模型网关、可观测与安全 |
| 4 | [04-部署与运维](./notes/04-部署与运维) | 部署拓扑、依赖组件、K8s、监控告警、备份与升级回滚 |
| 5 | [05-上线验收与 FAQ](./notes/05-上线验收与FAQ) | 准入清单、压测与灰度、故障演练、常见问题与评审问答 |

## 与其他主题的关系

```
金融 Agent 平台（本主题） ← 工程与治理层
   ├─ 运行时与工具机制 → Agent 智能体
   ├─ 知识库工具 → RAG 检索增强生成 / 向量数据库
   ├─ 提示词与结构化输出 → 提示词工程
   └─ 业务场景 → 金融技术（投研、财富管理、风控）
```

## 演示内容

Demo 覆盖平台最关键的六条治理链路：

| 能力 | 在控制台怎么看 |
| --- | --- |
| 真实模型运行 | 调试台选 Agent 提问，查看模型自主选择的工具与多步 trace |
| 多租户隔离 | 切换「张敏（t-sec）」与「陈璐（t-am）」，数据完全隔离 |
| MCP 注册与启停 | 「MCP 注册」页新增服务；开发者注册待管理员启用 |
| Agent 上架 | 创建草稿 → 提交审核 → 管理员发布 / 驳回 |
| 运行时鉴权 | 用「王研（研究员）」调用含财报工具的 Agent，观察权限拦截 |
| 工具不可用降级 | 管理员停用某个 MCP 后再调用，查看运行记录 |
| 审计追溯 | 「审计」页查看发布、驳回、越权拦截全部留痕 |

## 如何启动演示

```bash
cd notes/agent-platform
python3 -m pip install -r demos/requirements.txt
./start.sh              # 启动后端并打开 Vue 控制台
./start.sh --reset      # 清空演示数据后重建
./start.sh --port 9000  # 指定端口
./start.sh --no-browser # 只启动服务
```

默认地址：`http://127.0.0.1:8787/`。

## 推荐学习方式

1. **先玩控制台再看文档**：用三个身份各操作一遍，理解"为什么开发者不能自己发布"。
2. **对照代码读第 02/03 章**：`demos/main.py` 里的 `tenant_agent()`、`submit_agent()`、`execute_run()` 就是文档里的状态机与鉴权。
3. **带着上线问题读第 04/05 章**：如果真要落地，先看准入清单和压测方案，再回头补架构。

## 参考与官方文档

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [Vue 3 官方文档](https://cn.vuejs.org/)
- [OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- [Anthropic: Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
