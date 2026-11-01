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

新增内容要能出现在网站上，按「主题目录 + Web 登记」做，不要绕过 `web/`。

### 新增主题（清单）

| 步骤 | 做什么 |
| --- | --- |
| 1 | 建 `主题名/`：`README.md`、`notes/`、`demos/main.py`（按需 `requirements.txt`） |
| 2 | 建 `web/docs/主题名/index.md`（主题入口页，含如何跑演示） |
| 3 | 在 `web/docs/.vitepress/topics.ts` 登记（首页按分类网格展示） |
| 4 | 改 `web/docs/.vitepress/config.mts`：加 `nav`、该主题 `sidebar` |
| 5 | 改根 `main.py` 的 `TOPICS`、根 `README.md` 主题索引 |
| 6 | `git push origin main` → 等 Actions 成功 |

首页展示：固定五大类筛选（基础语言 / 大数据 / AI技术 / AI应用 / 金融技术），「全部」下按大类分组；空类显示占位。大类说明见 [知识框架.md](./知识框架.md)。`status: 'coming'` 可占位「即将推出」。

笔记源文件放在 `主题名/notes/*.md`。构建时 `web/scripts/sync-notes.mjs` 会同步到 `web/docs/主题名/notes/`（同步结果不入库）。

### 新增章节（清单）

| 步骤 | 做什么 |
| --- | --- |
| 1 | 写 `主题名/notes/0x-xxx.md` |
| 2 | 在 `config.mts` 对应主题的 `sidebar` 加链接 |
| 3 | 若有演示：`demos/chapters/` 加模块 + 主题 `demos/main.py` 注册 |
| 4 | 推送 `main` 自动部署 |

### 兼容约束（写内容时遵守）

1. **主题目录名 = Web 路径名**  
   例如 `dolphin-scheduler/` ↔ 站点 `/dolphin-scheduler/`。不要用中文作目录名（URL/CI 更省事）。
2. **笔记只维护一份源**  
   只改 `主题/notes/`，不要手改 `web/docs/*/notes/`（会被 sync 覆盖且已 gitignore）。
3. **链接用站点相对路径**  
   Web 页里链笔记用 `./notes/01-xxx` 这类路径；勿写死 `http://localhost`。
4. **记住 base 是 `/yili-ai-xuexi/`**  
   项目站不在域名根上。本地 `./start.sh` 用 `/`；CI / `./deploy.sh` 默认用 `/yili-ai-xuexi/`。自定义时设 `VITEPRESS_BASE`。
5. **演示说明写进主题页**  
   Pages 上无法执行 Python；在 `web/docs/<主题>/index.md` 写清本地命令即可。
6. **锁文件要提交**  
   保留并提交 `web/package-lock.json`，否则 Actions 里 `npm ci` 可能失败。

---

## 常见问题

| 现象 | 处理 |
| --- | --- |
| Actions 红了 | 打开失败 run 看日志；Pages Source 是否仍为 GitHub Actions |
| 推了但网页没变 | 等流水线结束；强刷；确认改的是已挂到 `web/` 的内容 |
| 新笔记网站上没有 | 是否放在 `主题/notes/`；sidebar / 主题页是否已加链接 |
| 样式或子页面 404 | base 是否应为 `/yili-ai-xuexi/`；勿把本地 `/` 产物直接当 Pages 上传 |

其它托管方式见 [部署说明.md](./部署说明.md)。Agent 约定见 [agent.md](./agent.md)。
