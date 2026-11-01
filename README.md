# yili-ai-xuexi

个人技术知识学习仓库：整理笔记 + 配套可运行演示。主要给自己学，也方便朋友/读者阅读跟做。

大类：**基础语言、大数据、AI 技术、AI 应用、金融技术**（详见 [知识框架.md](./知识框架.md)）。演示以 **Python** 为主。对外总入口为 **VitePress 站点**（可静态部署）。

## 怎么用

**阅读（Web）**

```bash
./start.sh           # 一键启动网站
```

**在线**：https://milsevol.github.io/yili-ai-xuexi/  
更新后推 `main` 即部署，见 [github-pages.md](./github-pages.md)。

**动手（主题演示）**

```bash
cd notes/dolphin-scheduler
./start.sh              # 浏览器可视化交互演示
./start.sh 04           # 直达 DAG 实验室
./start.sh --cli        # 备用终端版
```

也可：`python3 main.py dolphin-scheduler`。

打包：`./deploy.sh`（详见 [部署说明.md](./部署说明.md)）。

## 项目结构

学习内容统一在 **`notes/`**，避免在仓库根散落多个主题目录。

```
yili-ai-xuexi/
  notes/                       # 所有主题
    <主题>/
      README.md
      notes/                   # 章节 Markdown
      demos/ + start.sh        # 按需
  web/                         # VitePress；sync 自 notes/<主题>/notes
  main.py                      # CLI 进主题演示
  start.sh / deploy.sh         # 网站启动 / 打包
```

## 主题索引

| 主题 | 说明 |
| --- | --- |
| [海豚调度](./notes/dolphin-scheduler/) | Apache DolphinScheduler：DAG 调度概念与本地 Python 演示 |

## 约定摘要

- 主题只建在 `notes/` 下；有 demos 必有 `start.sh`；章节写细（入门→精通）；要有官方参考链接。
- **Demo 选型**：概念/机制 → 可视化交互；真实框架（如 LangChain）→ Python 脚本或 Jupyter，用真库写例子（见 [agent.md](./agent.md)）。
- 大类可扩展；问答可沉淀。

## 环境

Python 3.11（`python3`）；Node 24.19；Java 示例须兼容 8。见 [开发环境信息.md](./开发环境信息.md)。
