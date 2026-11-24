# yili-ai-xuexi

个人技术知识学习仓库：整理笔记 + 配套可运行演示。主要给自己学，也方便朋友/读者阅读跟做。

大类：**基础、大数据、AI 技术、AI 应用、金融技术**（详见 [知识框架.md](./知识框架.md)）。演示以 **Python** 为主。对外总入口为 **VitePress 站点**（可静态部署）。

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

按**学习路线图顺序**排列（依赖关系 → 认知顺序），详见 [知识框架.md#大数据学习路线图](./知识框架.md#大数据学习路线图)。

| 顺序 | 主题 | 层级 | 说明 |
| --- | --- | --- | --- |
| — | [OceanBase](./notes/oceanbase/) | 数据库基础 | 分布式关系型数据库：Paxos 多副本 / 多租户 / MySQL + Oracle 双模式 / Oracle 迁移 8 章 + 浏览器可视化交互演示 |
| 1 | [Hadoop](./notes/hadoop/) | 基础设施底座 | HDFS / YARN / MapReduce 10 章 + 浏览器可视化交互演示 |
| 2 | [Hive](./notes/hive/) | 数仓 SQL 层 | Metastore + 数仓分层 + ACID 10 章 + 浏览器可视化交互演示 |
| 3 | [Spark](./notes/spark/) | 计算引擎 | PySpark 10 章 + 浏览器可视化交互演示 |
| 4 | [Flink](./notes/flink/) | 计算引擎 | 流计算（Watermark/State/Checkpoint）10 章 + 浏览器可视化交互演示 |
| 5 | [Kafka](./notes/kafka/) | 实时管道 | 消息队列 10 章 + 浏览器可视化交互演示 |
| 6 | [湖仓一体](./notes/iceberg/) | 湖仓表格式 | Apache Iceberg：ACID + Time Travel 10 章 + 浏览器可视化交互演示 |
| 7 | [HBase](./notes/hbase/) | 数据访问 | LSM-Tree 点查数据库 10 章 + 浏览器可视化交互演示 |
| 8 | [ClickHouse](./notes/clickhouse/) | 数据访问 | 列式 OLAP 数据库 10 章 + 浏览器可视化交互演示 |
| 9 | [海豚调度](./notes/dolphin-scheduler/) | 调度编排 | DAG 调度概念 + 浏览器可视化交互演示 |
| 10 | [Transformer 与大模型原理](./notes/llm-foundations/) | AI 模型底座 | Attention / 预训练 / 对齐 / 采样 8 章 + 浏览器可视化交互演示 |
| 11 | [提示词工程](./notes/prompt-engineering/) | AI 输入控制 | 四要素 / CoT / 结构化输出 / 防注入 6 章 + 浏览器可视化交互演示 |
| 12 | [向量数据库](./notes/vector-db/) | AI 检索底座 | Embedding / HNSW / FAISS / Milvus 6 章 + 浏览器可视化交互演示 |
| 13 | [RAG 检索增强生成](./notes/rag/) | AI 知识增强 | Chunking / 多路召回 / Rerank / RAGAS 8 章 + 浏览器可视化交互演示 |
| 14 | [Agent 智能体](./notes/agent/) | AI 自主执行 | 手写 Agent / ReAct / MCP / LangGraph / 多 Agent / 企业级实战 10 章 + 浏览器可视化交互演示 |
| 15 | [量化交易](./notes/quant-trading/) | 金融技术 | 市场规则 / 因子 / 策略 / 回测 / 组合风险 / 执行 / 实盘工程 / AI 投研 10 章 + 浏览器可视化交互演示 |
| 16 | [金融 Agent 平台实战](./notes/agent-platform/) | AI 应用 | 企业多租户 Agent 平台：MCP 注册 / Agent 上架审核 / 运行时鉴权 / 审计 / 部署 5 章 + FastAPI + Vue 可运行控制台 |
| 17 | [飞书应用开发](./notes/feishu/) | 企业应用 | 飞书开放平台：App 凭证 / 三种 Token 与 OAuth / 消息与交互式卡片 / 多维表格 Bitable / 云文档与云空间 / 通讯录与扫码登录 / 日历会议审批 / 小程序 / 工作台详解 / 实战 FAQ 11 章 + 浏览器可视化交互演示 |

AI 技术路线的依赖关系与两条可选路径（应用侧 / 原理侧）见 [知识框架.md#ai-技术学习路线图](./知识框架.md#ai-技术学习路线图)。

金融技术（量化）路线的学习顺序与最小可行路线见 [知识框架.md#金融技术学习路线图](./知识框架.md#金融技术学习路线图)。

## 约定摘要

- 主题只建在 `notes/` 下；有 demos 必有 `start.sh`；章节写细（入门→精通，**章数按内容需要定，不固定 10 章**）；要有官方参考链接。
- **Demo 选型**：概念/机制 → 可视化交互；真实框架（如 LangChain）→ Python 脚本或 Jupyter，用真库写例子（见 [agent.md](./agent.md)）。
- 大类可扩展；问答可沉淀。

## 环境

Python 3.11（`python3`）；Node 24.19；Java 示例须兼容 8。见 [开发环境信息.md](./开发环境信息.md)。
