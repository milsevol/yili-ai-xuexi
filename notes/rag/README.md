# rag · RAG 检索增强生成

个人学习知识库的 AI 主题笔记：从两阶段链路到切块、召回、重排、评估与高级架构。

## 章节

| 章节 | 内容 |
| --- | --- |
| 01 概述与定位 | 幻觉与知识截止、RAG vs 微调的判断 |
| 02 RAG 核心流程 | 索引期 + 查询期两阶段各环节输入输出 |
| 03 文档解析与 Chunking | 解析坑、切块策略、大小与重叠权衡 |
| 04 检索优化与多路召回 | 查询改写、HyDE、向量+BM25 与 RRF 融合 |
| 05 重排序 Rerank | Cross-Encoder 原理、bge-reranker、Top-K 截断 |
| 06 RAG 评估 RAGAS | 四指标定义、评估集构建、badcase 分析 |
| 07 高级 RAG 架构 | GraphRAG、Agentic RAG、Self-RAG、分层检索 |
| 08 企业知识库实战与 FAQ | 最小可用实现、生产化清单、12 个面试问答 |

## 启动演示

```bash
./start.sh          # 启动本地服务并打开交互页
./start.sh 08       # 直达真实检索与生成 trace
./start.sh --port 9000  # 指定本地服务端口
./start.sh --cli    # 终端摘要版
```

第 08 章的「运行一次查询」会在本地知识库做 BM25 检索，再调用 DeepSeek 生成带引用的答案；Key 通过环境变量 `DEEPSEEK_API_KEY` 提供。

也可在仓库根目录：`python3 main.py rag`。
