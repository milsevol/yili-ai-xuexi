/**
 * 站点主题清单（首页展示的唯一数据源）。
 * 大类定义见仓库根目录「知识框架.md」。
 * 新增主题时：在此登记，并同步 config.mts 导航 / web/docs/<主题>/index.md。
 */
export type TopicCategory =
  | '基础语言'
  | '大数据'
  | 'AI技术'
  | 'AI应用'
  | '金融技术'

export type Topic = {
  id: string
  title: string
  category: TopicCategory
  description: string
  link: string
  /** 章数由 sync-notes 扫描 notes/<主题>/notes/*.md 自动生成，勿在此手写 */
  status?: 'ready' | 'coming'
}

/** 大类顺序（首页筛选与分组固定按此顺序） */
export const categoryOrder: TopicCategory[] = [
  '基础语言',
  '大数据',
  'AI技术',
  'AI应用',
  '金融技术',
]

export const categoryHints: Record<TopicCategory, string> = {
  基础语言: 'Python、Java、SQL、Shell 等语言基础',
  大数据: '调度、数仓、消息队列、计算引擎等',
  AI技术: '模型、RAG、向量库、Agent 等技术能力',
  AI应用: '业务场景与落地用法',
  金融技术: '量化交易、财富管理等金融域',
}

export const topics: Topic[] = [
  {
    id: 'hadoop',
    title: 'Hadoop',
    category: '大数据',
    description:
      'Apache Hadoop：HDFS、YARN、MapReduce 与生态组件。大数据栈的底座。10 章笔记 + 浏览器可视化交互演示。',
    link: '/hadoop/',
    status: 'ready',
  },
  {
    id: 'hive',
    title: 'Hive',
    category: '大数据',
    description:
      'Apache Hive：HDFS 上的数仓 SQL 层。Metastore、执行引擎切换（MR/Tez/Spark）、分区管理、数仓分层（ODS/DWD/DWS/ADS）。10 章笔记 + 浏览器可视化交互演示。',
    link: '/hive/',
    status: 'ready',
  },
  {
    id: 'spark',
    title: 'Spark',
    category: '大数据',
    description:
      'Apache Spark：PySpark 从 RDD/SQL 到 Shuffle、调优、流处理。批计算主力，可连 Hive Metastore。10 章笔记 + 浏览器可视化交互演示。',
    link: '/spark/',
    status: 'ready',
  },
  {
    id: 'flink',
    title: 'Flink',
    category: '大数据',
    description:
      'Apache Flink：真正的流计算引擎。DataStream、Watermark、Window、State/Checkpoint、Flink SQL、CDC。10 章笔记 + 浏览器可视化交互演示。',
    link: '/flink/',
    status: 'ready',
  },
  {
    id: 'kafka',
    title: 'Kafka',
    category: '大数据',
    description:
      'Apache Kafka：实时链路标配消息队列。Producer/Consumer 原理、分区副本、ISR、零拷贝、Rebalance、KRaft。10 章笔记 + 浏览器可视化交互演示。',
    link: '/kafka/',
    status: 'ready',
  },
  {
    id: 'iceberg',
    title: '湖仓一体',
    category: '大数据',
    description:
      'Apache Iceberg：开放表格式，解决 Hive 表无 ACID、分区难演进、无时间旅行的痛点。元数据三层、快照隔离、隐藏分区、Schema 演进与表维护。10 章笔记 + 浏览器可视化交互演示。',
    link: '/iceberg/',
    status: 'ready',
  },
  {
    id: 'hbase',
    title: 'HBase',
    category: '大数据',
    description:
      'Apache HBase：海量数据随机点查的 LSM-Tree 数据库。RowKey 设计、Compaction、Region 管理与运维调优。10 章笔记 + 浏览器可视化交互演示。',
    link: '/hbase/',
    status: 'ready',
  },
  {
    id: 'clickhouse',
    title: 'ClickHouse',
    category: '大数据',
    description:
      'ClickHouse：列式 OLAP 数据库。MergeTree 引擎家族、向量化执行、分区排序键、分布式集群、物化视图与 CDC。10 章笔记 + 浏览器可视化交互演示。',
    link: '/clickhouse/',
    status: 'ready',
  },
  {
    id: 'dolphin-scheduler',
    title: '海豚调度',
    category: '大数据',
    description:
      'Apache DolphinScheduler：从概述到部署运维与选型。理解 Hadoop/Spark/Flink 后再学调度编排最自然。浏览器可视化交互演示。',
    link: '/dolphin-scheduler/',
    status: 'ready',
  },
  {
    id: 'llm-foundations',
    title: 'Transformer 与大模型原理',
    category: 'AI技术',
    description:
      '大模型的地基：Self-Attention、位置编码、Tokenizer、预训练与 Scaling Law、SFT/RLHF/DPO 对齐、开源模型选型、采样与 KV Cache。8 章笔记 + 浏览器可视化交互演示。',
    link: '/llm-foundations/',
    status: 'ready',
  },
  {
    id: 'prompt-engineering',
    title: '提示词工程',
    category: 'AI技术',
    description:
      '不训练模型、只改输入的那一层：Prompt 四要素、Few-shot、思维链与 ToT、结构化输出与 Function Calling、评估迭代与 Prompt 注入防护。6 章笔记 + 浏览器可视化交互演示。',
    link: '/prompt-engineering/',
    status: 'ready',
  },
  {
    id: 'vector-db',
    title: '向量数据库',
    category: 'AI技术',
    description:
      '语义检索的底座：Embedding 原理与模型选型、HNSW/IVF/PQ 近似最近邻算法、FAISS 与 Milvus 实战、混合检索与参数调优。6 章笔记 + 浏览器可视化交互演示。',
    link: '/vector-db/',
    status: 'ready',
  },
  {
    id: 'rag',
    title: 'RAG 检索增强生成',
    category: 'AI技术',
    description:
      '给大模型接私有知识：索引与查询两阶段、文档解析与 Chunking、多路召回、Rerank 重排、RAGAS 评估、GraphRAG 与 Agentic RAG。8 章笔记 + 浏览器可视化交互演示。',
    link: '/rag/',
    status: 'ready',
  },
  {
    id: 'agent',
    title: 'Agent 智能体',
    category: 'AI技术',
    description:
      '让模型自己干活：从零手写 Agent 循环、规划/记忆/工具三要素、ReAct、Function Calling 与 MCP、LangGraph 状态机、多 Agent、生产工程化与企业级智能投研平台。10 章笔记 + 浏览器可视化交互演示。',
    link: '/agent/',
    status: 'ready',
  },
  {
    id: 'quant-trading',
    title: '量化交易',
    category: '金融技术',
    description:
      '从市场规则到实盘工程：订单簿与 A 股规则、因子研究与 IC、趋势/回归/多因子/套利策略、回测偏差与绩效、组合优化与风险、TWAP/VWAP 执行、实盘架构与 AI 投研。10 章笔记 + 浏览器可视化交互演示。',
    link: '/quant-trading/',
    status: 'ready',
  },
]
