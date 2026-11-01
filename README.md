# yili-ai-xuexi

个人技术知识学习仓库：整理笔记 + 配套可运行演示。主要给自己学，也方便朋友/读者阅读跟做。

大类：**基础语言、大数据、AI 技术、AI 应用、金融技术**（详见 [知识框架.md](./知识框架.md)）。演示以 **Python** 为主。对外总入口为 **VitePress 站点**（可静态部署）。

## 怎么用

**阅读（Web）**

```bash
./start.sh           # 一键启动（nvm 切 Node 24.19、装依赖、开浏览器）
```

或手动：

```bash
cd web
npm install
npm run dev          # http://localhost:5173
```

**在线阅读（已部署）**：https://milsevol.github.io/yili-ai-xuexi/

更新代码后重新部署：推送到 `main` 即可（Actions 自动发布）。  
详见 **[github-pages.md](./github-pages.md)**（含后续主题如何兼容 Pages）。

本地打包：

```bash
./deploy.sh              # 本地打包（默认 GitHub Pages 路径）
./deploy.sh --preview    # 打包并预览产物
```

其它托管见 [部署说明.md](./部署说明.md)。

**动手（Python 演示）**

```bash
python3 main.py                              # CLI 选主题
python3 main.py dolphin-scheduler 04         # 直达某主题某章
python3 dolphin-scheduler/demos/main.py 04   # 等价
```

## 项目结构

| 层级 | 形态 | 作用 |
| --- | --- | --- |
| 仓库总入口 | `web/` VitePress | 主题导航、在线读笔记、说明如何跑演示 |
| 主题演示 | `主题/demos/` Python | 章节动手实验（本地运行） |
| 可选 | 根 `main.py` | 本机 CLI 快速进主题 |

```
yili-ai-xuexi/
  main.py
  web/                         # VitePress：npm run dev / build
    docs/
    scripts/sync-notes.mjs     # 构建前把各主题 notes 同步进站点
  主题目录/
    README.md
    notes/                     # 笔记源文件（站点同步自此处）
    demos/
      main.py
      requirements.txt
      chapters/
```

新增主题时：建主题目录与演示 → 在 `web/docs/` 增加主题页并改 `.vitepress/config.mts` 导航 → 登记根 `main.py` 的 `TOPICS` → `git push origin main` 自动更新 Pages（清单见 github-pages.md）。

## 主题索引

| 主题 | 说明 |
| --- | --- |
| [海豚调度](./dolphin-scheduler/) | Apache DolphinScheduler：DAG 调度概念与本地 Python 演示 |

## 约定摘要

- Web 负责阅读与导航；Python 负责跑演示。
- 一主题一 Python 程序；章节往里加模块。
- 允许主题级依赖；密钥不入库。
- 不需要学习进度功能。
- **大类可扩展**：内容放不进现有大类时可新增，并由 Agent 自动判断主题/章节结构（见 [agent.md](./agent.md)、[知识框架.md](./知识框架.md)）。
- **问答可沉淀**：学习中的问题若已有明确解答，可判断是否写入知识库（笔记/演示）。

## 本地开发环境

- Python：3.11.11（`python3`）
- Node.js：v24.19.0（Web 构建）
- Java：若写示例须兼容 Java 8；优先 Python 演示

详见 [开发环境信息.md](./开发环境信息.md)。Agent 约定见 [agent.md](./agent.md)。
