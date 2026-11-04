# 向量数据库与 Embedding

向量数据库解决一个非常具体的问题：**在百万到十亿条向量里，用毫秒级时间找出最相似的几条**。暴力比对做不到，所以有了 HNSW、IVF、PQ 这些近似最近邻（ANN）算法。本主题从 Embedding 是怎么把语义变成向量讲起，到 ANN 索引原理、FAISS/Milvus 实战、混合检索与调优。它是 RAG 的存储与检索底座。

> 版本参考：FAISS 1.8+ / Milvus 2.4+ / Qdrant 1.x。演示不连接真实向量库；默认打开 `demos/index.html`。

## 先决知识

- Python 基础 + numpy（能读懂矩阵和余弦相似度）
- 了解向量、点积、归一化的几何含义
- SQL 基础（Milvus/Qdrant 的标量过滤类似 WHERE）

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位) | `./start.sh 01` | 为什么需要向量库、与 ES/关系库的差异、应用场景 |
| 2 | [02-Embedding原理与模型](./notes/02-Embedding原理与模型) | `./start.sh 02` | 从 Word2Vec 到现代 Embedding、模型对比与维度权衡 |
| 3 | [03-ANN算法原理](./notes/03-ANN算法原理) | `./start.sh 03` | HNSW 分层图、IVF 聚类、PQ 量化、召回率与延迟 |
| 4 | [04-FAISS与Milvus实战](./notes/04-FAISS与Milvus实战) | `./start.sh 04` | FAISS 索引选择与代码、Milvus 架构、产品选型对比 |
| 5 | [05-混合检索与调优](./notes/05-混合检索与调优) | `./start.sh 05` | 向量+BM25、RRF 融合、标量过滤、参数调优 |
| 6 | [06-语义搜索实战与FAQ](./notes/06-语义搜索实战与FAQ) | `./start.sh 06` | 端到端语义搜索、常见坑、面试 FAQ |

## 与其他主题的关系

```
向量数据库（本主题）
   ├─ 上游：Embedding 模型（把文本变向量）
   ├─ 下游：RAG（检索环节的存储与召回）
   ├─ 侧向：ClickHouse / ES（也能存向量，规模小时可用）
   └─ 侧向：ANN 算法本质是索引结构问题，和大数据索引思路相通
```

## 如何启动演示

```bash
cd notes/vector-db
./start.sh          # 浏览器可视化交互
./start.sh 03       # 直达 HNSW 分层检索演示
./start.sh --cli    # 备用终端文字版
```

也可：`python3 main.py vector-db` / `python3 main.py vector-db 03`。

## 参考与官方文档

- [FAISS 官方文档](https://faiss.ai/)
- [Milvus 官方文档](https://milvus.io/docs)
- [HNSW 论文](https://arxiv.org/abs/1603.09320)
- [MTEB Embedding 榜单](https://huggingface.co/spaces/mteb/leaderboard)
