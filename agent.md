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
2. **新章节**：写细（入门→精通）；sidebar；文末「参考与官方文档」；演示挂到该主题 `demos`。
3. **一主题一程序**；Web 只读；依赖最小；提交 `package-lock.json`；密钥不入库；中文。
4. **推 main** → Pages。

## 写作与扩展

- **章节深度**：入门 → 进阶 → 精通向；宁长勿空。结构：问题 → 概念 → 机制 → 实践 → 进阶 → 参考文档 → 自测。
- **参考文档**：主题页 + 每章都要有。
- **大类**：见知识框架；塞不进可新增（`topics.ts` + 知识框架），并自动定结构。
- **问答沉淀**：可复用解答再入库；拿不准先问。

## 环境

Python 3.11 / `python3`；Node 24.19（web）；Java 若写须兼容 8，优先 Python。
