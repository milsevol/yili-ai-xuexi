# RAG 检索增强生成

RAG（Retrieval-Augmented Generation）解决大模型最要命的两个问题：**不知道你的私有知识**、**会一本正经地编**。做法很朴素——先去你的知识库里捞出相关片段，再让模型基于这些片段回答。但工程上，难点几乎全在「怎么捞得准」：解析、切块、召回、重排、评估，每一环都能让效果掉一半。本主题用中文笔记 + **浏览器可视化交互演示**，把整条链路拆开讲透。

> 版本参考：LangChain 0.3+ / LlamaIndex、RAGAS 0.2+、bge-m3 / bge-reranker。演示不连接真实模型与向量库；默认打开 `demos/index.html`。

## 先决知识

- 会调用大模型 API（理解上下文窗口与 token 计费）
- 已完成[向量数据库与 Embedding](/vector-db/) 主题（理解 Embedding 与 ANN 检索）
- Python 基础（能读 LangChain 或纯 Python 示例）
- 了解基本的文本处理（正则、编码、分句）

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位) | `./start.sh 01` | 幻觉与知识截止、RAG vs 微调、适用场景 |
| 2 | [02-RAG核心流程](./notes/02-RAG核心流程) | `./start.sh 02` | 索引期 + 查询期两阶段、各环节输入输出 |
| 3 | [03-文档解析与Chunking](./notes/03-文档解析与Chunking) | `./start.sh 03` | PDF/Word 解析坑、切块策略、大小与重叠权衡 |
| 4 | [04-检索优化与多路召回](./notes/04-检索优化与多路召回) | `./start.sh 04` | 查询改写、HyDE、向量+关键词多路召回 |
| 5 | [05-重排序Rerank](./notes/05-重排序Rerank) | `./start.sh 05` | Cross-Encoder 原理、bge-reranker、Top-K 截断 |
| 6 | [06-RAG评估RAGAS](./notes/06-RAG评估RAGAS) | `./start.sh 06` | 忠实度/相关性/召回评估、评估集与 badcase |
| 7 | [07-高级RAG架构](./notes/07-高级RAG架构) | `./start.sh 07` | GraphRAG、Agentic RAG、Self-RAG、多模态 |
| 8 | [08-企业知识库实战与FAQ](./notes/08-企业知识库实战与FAQ) | `./start.sh 08` | 端到端最小可用 RAG、生产化要点、面试 FAQ |

## 与其他主题的关系

```
RAG（本主题）= 检索 + 生成
   ├─ 存储与召回 → 向量数据库与 Embedding
   ├─ 生成质量 → Transformer 原理 + 提示词工程
   ├─ 更进一步的自主检索 → Agent 智能体（Agentic RAG）
   └─ 数据侧 → 大数据主题（离线清洗、Chunk 预处理管道）
```

## 如何启动演示

```bash
cd notes/rag
./start.sh          # 浏览器可视化交互
./start.sh 03       # 直达 Chunking 切块演示
./start.sh --cli    # 备用终端文字版
```

也可：`python3 main.py rag` / `python3 main.py rag 03`。

## 参考与官方文档

- [RAG 原始论文](https://arxiv.org/abs/2005.11401)
- [LangChain RAG 教程](https://python.langchain.com/docs/tutorials/rag/)
- [RAGAS 评估框架](https://docs.ragas.io/)
- [bge-reranker 模型](https://huggingface.co/BAAI/bge-reranker-v2-m3)
