# GitHub Pages 说明

站点已部署。在线地址：

**https://milsevol.github.io/yili-ai-xuexi/**

本页说明：Pages 怎么工作、**更新代码后怎么重新部署**、以及后续加主题/章节时如何兼容站点发布。

> 站点只发布「笔记与导航」。Python 演示仍在本地跑，不会、也不需要部署到 Pages。

---

## 更新代码后怎么部署？

**日常做法：推送到 `main`（或 `master`）即可自动部署。**

```bash
git add .
git commit -m "说明本次改动"
git push origin main
```

然后：

1. 打开仓库 **Actions**，看工作流 **Deploy VitePress** 是否变绿  
2. 约 1～2 分钟后刷新：https://milsevol.github.io/yili-ai-xuexi/  
3. 若页面像没变，强制刷新（macOS：`Cmd+Shift+R`）

也可以在 Actions 里对该工作流点 **Run workflow** 手动再发一次（不改代码也能重部署）。

本地只验证打包、不发布：

```bash
./deploy.sh           # 按 Pages 路径打包
./deploy.sh --preview # 预览产物
```

流水线：`.github/workflows/deploy-web.yml`  
（`web/` 安装依赖 → sync 笔记 → build → 发布 `docs/.vitepress/dist`）

---

## 首次配置（已完成可跳过）

仓库 **Settings → Pages → Source** 必须为 **GitHub Actions**。  
若 Source 不对，会出现 `Failed to create deployment (status: 404)`。

设置页：https://github.com/milsevol/yili-ai-xuexi/settings/pages

---

## 后续知识框架如何兼容 Pages

新增内容按「`notes/<主题>` + Web 登记」做，不要绕过 `web/`，也不要在仓库根再建主题目录。

### 新增主题（清单）

| 步骤 | 做什么 |
| --- | --- |
| 1 | 建 `notes/主题名/`：`README.md`、`notes/`、`demos`（按需）+ `start.sh` |
| 2 | 建 `web/docs/主题名/index.md`（启动说明 + 参考文档） |
| 3 | 登记 `topics.ts`、`config.mts` nav/sidebar |
| 4 | 改根 `main.py` 的 `TOPICS`、根 README 索引 |
| 5 | `git push origin main` |

章节源文件：`notes/<主题>/notes/*.md` → 构建 sync 到 `web/docs/<主题>/notes/`（不同步入库）。大类见 [知识框架.md](./知识框架.md)。

### 新增章节

写 `notes/<主题>/notes/0x-xxx.md` → sidebar → 按需 `demos` → push。

### 兼容约束

1. 主题目录名 = 站点路径（如 `notes/dolphin-scheduler` ↔ `/dolphin-scheduler/`）。
2. 只改 `notes/<主题>/notes/`，勿手改 `web/docs/*/notes/`。
3. Web 相对链接；Pages base 为 `/yili-ai-xuexi/`。
4. 演示命令写在主题页；提交 `web/package-lock.json`。

---

## 常见问题

| 现象 | 处理 |
| --- | --- |
| Actions 红了 | 看日志；Pages Source 是否为 GitHub Actions |
| 推了网页没变 | 等流水线；强刷 |
| 新笔记网站没有 | 是否在 `notes/<主题>/notes/`；sidebar 是否登记 |
| 子页 404 | base 是否 `/yili-ai-xuexi/` |

其它托管方式见 [部署说明.md](./部署说明.md)。Agent 约定见 [agent.md](./agent.md)。
