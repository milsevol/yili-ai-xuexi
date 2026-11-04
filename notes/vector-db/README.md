# vector-db · 向量数据库与 Embedding

个人学习知识库的 AI 主题笔记：向量数据库、Embedding、ANN 索引算法与 RAG 语义搜索实战。

## 章节

| 章节 | 内容 |
| --- | --- |
| 01 概述与定位 | 为什么需要向量数据库、与 ES/关系库差异、应用场景、产品一览 |
| 02 Embedding 原理与模型 | Word2Vec→BERT→对比学习，bge/m3e/text-embedding-3 对比，维度与精度权衡 |
| 03 ANN 算法原理 | HNSW 分层图、IVF 倒排聚类、PQ 乘积量化、召回率与延迟权衡 |
| 04 FAISS 与 Milvus 实战 | FAISS 索引选择、Python 代码、Milvus 架构部署、选型对比 |
| 05 混合检索与调优 | 向量+BM25、RRF 融合、标量过滤、参数调优、分片副本 |
| 06 语义搜索实战与 FAQ | 完整五步管线、常见坑、10 个面试问答 |

## 使用

```bash
./start.sh           # 浏览器打开可视化交互演示
./start.sh 03        # 直达第 3 章
./start.sh --cli     # 终端摘要版
```

- 笔记：`notes/`
- 演示：`demos/`（`index.html` 纯前端无依赖，支持 `?c=03` 直达章节）
