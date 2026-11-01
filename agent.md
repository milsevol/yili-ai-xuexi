# Agent 工作指南

个人技术知识库：中文笔记 + Python 演示；Web（VitePress）可读可部署。细节：[知识框架.md](./知识框架.md)、[github-pages.md](./github-pages.md)、[开发环境信息.md](./开发环境信息.md)。

```
notes/<主题>/          ← 所有学习内容统一在此（勿在仓库根再建主题目录）
  README.md
  notes/               ← 章节 Markdown
  demos/ + start.sh    ← 按需
web/                   ← 站点；构建时 sync 章节进 web/docs/<主题>/notes/
```

只改 `notes/<主题>/notes/`；勿手改 `web/docs/*/notes/`。

## 必做约定

1. **新主题**：建在 `notes/<主题>/`（英文短横线）→ 配 README、章节、`demos`/`start.sh`（按需）→ 登记 `web/docs/<主题>/`、`topics.ts`、`config.mts`、根 `main.py` / README。有演示：`./start.sh` / `./start.sh 04`；根 `./start.sh` 只启网站。
2. **新章节**：写细（入门→精通）；sidebar；文末「参考与官方文档」；演示挂到该主题 `demos`（选型见下）。首页「N 章」由 `npm run sync` 扫描 `notes/<主题>/notes/*.md` 自动生成，不必手改。
3. **一主题一入口**（`start.sh`）；依赖写进 `requirements.txt` / 说明；提交 `package-lock.json`；密钥不入库；中文。
4. **推 main** → Pages。

## Demo 怎么选（重要）

目的都是**快速理解概念、逻辑与知识**；形态按知识类型选，不要一刀切。

| 知识类型 | 优先形态 | 说明 |
| --- | --- | --- |
| **概念 / 机制 / 流程**（如调度 DAG、架构职责） | **可视化 + 交互** | 简单 HTML/JS：点选、单步、调参看状态；少黑盒长日志 |
| **真实框架 / 要动手写的程序**（如 LangChain、SDK、API） | **真库 Python 例子** | 直接用该框架写可运行示例：`.py` 脚本或 **Jupyter Notebook**；`requirements.txt` 写清依赖；`start.sh` 负责起环境/打开 notebook 或跑入口脚本 |

补充：

- 概念演示：能「看见」优于干讲；交互服务于理解，不做成复杂产品（例：海豚调度 `demos/index.html`）。
- 框架演示：用真实依赖跑通最小链路（装 → 配 key → 跑通一句调用/一条链），代码短、注释对照笔记；Notebook 适合逐步实验，脚本适合一键复现。
- 同一主题可组合：先可视化讲清概念，再上 Python/Notebook 真写；仍尽量一个 `start.sh` 入口并在 README 写清用法。

## 写作与扩展

- **章节深度**：入门 → 进阶 → 精通向；宁长勿空。结构：问题 → 概念 → 机制 → 实践 → 进阶 → 参考文档 → 自测。
- **参考文档**：主题页 + 每章都要有。
- **大类**：见知识框架；塞不进可新增（`topics.ts` + 知识框架），并自动定结构。
- **问答沉淀**：可复用解答再入库；拿不准先问。

## 环境

Python 3.11 / `python3`；Node 24.19（web）；Java 若写须兼容 8，优先 Python。
