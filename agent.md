# Agent 工作指南

本仓库是个人技术知识学习仓库：笔记 + 可运行演示。读者包括作者本人与朋友/公开读者。

内容方向：大数据平台、AI、量化交易等。演示以 Python 为主。对外总入口为 **VitePress（`web/`）**，已部署到 **GitHub Pages**。

Pages 更新方式与兼容清单见 [github-pages.md](./github-pages.md)。

## 导航结构

```
Web 总入口 (web/)     → 选主题、读笔记、看「如何运行演示」
  └─ 主题/demos/      → 本地 Python：选章节跑演示
根 main.py（可选）    → 本机 CLI 进主题
```

笔记源文件在 `主题/notes/`；`npm run dev/build` 前通过 `web/scripts/sync-notes.mjs` 同步到 `web/docs/<主题>/notes/`（该目录不入库）。

## 工作约定

1. 新增主题（必须同时兼容 Pages）：
   - 建主题目录、`README.md`、`notes/`、`demos/main.py`；按需 `requirements.txt`；
   - 建 `web/docs/<主题>/index.md`；
   - 在 `web/docs/.vitepress/topics.ts` 登记主题（首页网格数据源）；
   - 更新 `web/docs/.vitepress/config.mts` 的 `nav` / `sidebar`；
   - 更新根 `main.py` 的 `TOPICS` 与根 `README.md` 主题索引；
   - 主题目录名用英文/短横线，与站点路径一致。
2. 新增章节：写 `主题/notes/0x-xxx.md`；更新 sidebar；若需演示则改 `demos/` 并注册；**不要手改** `web/docs/*/notes/`。
3. 一主题一 Python 程序；禁止默认每章独立工程。
4. Web 负责阅读与导航；不要默认把演示改成必须在浏览器里跑。
5. 允许依赖，保持最小；安装与启动写进主题 README 与 Web 主题页。
6. 提交并保留 `web/package-lock.json`，保证 Actions `npm ci` 可用。
7. 密钥用环境变量 / `.env`，不入库。
8. 不需要进度系统。笔记、注释、沟通使用中文。
9. 内容合并到 `main`/`master` 后由 Actions 自动发布 Pages；细节见 github-pages.md。

## 技术环境

- Python：3.11.11，`python3`。
- Node.js：nvm，v24.19.0（在 `web/` 下 npm 构建）。
- Java：若写 Java 须兼容 Java 8；优先 Python 演示。

详见 [开发环境信息.md](./开发环境信息.md)。
