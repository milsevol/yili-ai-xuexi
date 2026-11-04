# 06 语义搜索实战与 FAQ

## 一句话

**一个生产可用的语义搜索 = 切块 → Embedding → 入库 → 混合检索 → 重排**，五步缺一不可。本章把前五章串成一个完整可跑的实战，并总结新手最常踩的坑（维度不一致、忘归一化、增量更新）和高频面试题。

## 完整实战：FAQ 知识库语义搜索

### 第 1 步：文档切块（Chunking）

Embedding 模型有长度上限（512/8192 token），且**块越细检索越准**——整篇文档的向量会被多个主题「平均」掉。

```python
def split_text(text: str, chunk_size: int = 300, overlap: int = 50) -> list[str]:
    """按字符滑窗切块，相邻块保留重叠避免切断语义"""
    chunks, start = [], 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return [c for c in chunks if c.strip()]
```

**切块策略对比**：

| 策略 | 做法 | 优点 | 缺点 |
| --- | --- | --- | --- |
| 定长切块 | 每 300~500 字 + 50 字重叠 | 简单稳定 | 可能切断句子/表格 |
| 按结构切 | 按标题/段落/Markdown 层级 | 语义完整 | 实现复杂、块长不均 |
| 语义切块 | 相邻句向量距离突变处切 | 语义最完整 | 计算成本高 |

**经验**：通用文档先「按标题分节 + 节内定长 300~500 字 + 50 重叠」，覆盖 80% 场景。块太大检索不精，太小缺上下文——300~500 字是中文 RAG 的甜区。

### 第 2 步：Embedding

```python
from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer("BAAI/bge-m3")

chunks = ["退货流程：签收后 7 天内可在订单页申请退货退款。",
          "退款时效：审核通过后 1-3 个工作日原路退回。",
          "运费规则：满 99 元包邮，不足收取 8 元运费。",
          "会员体系：消费累计积分，100 积分抵 1 元。"]

doc_vecs = model.encode(chunks, normalize_embeddings=True).astype(np.float32)
print(doc_vecs.shape)   # (4, 1024)
```

### 第 3 步：入库（FAISS 版）

```python
import faiss

D = doc_vecs.shape[1]
index = faiss.IndexFlatIP(D)        # 已归一化 → 内积即余弦
index.add(doc_vecs)

# 自建 id → 原文映射（FAISS 不存文本）
id2doc = {i: c for i, c in enumerate(chunks)}
```

数据量上来后换成 HNSW + Milvus（第 04 章），API 形状一致。

### 第 4 步：检索

```python
def search(query: str, top_k: int = 3):
    qv = model.encode([query], normalize_embeddings=True).astype(np.float32)
    scores, ids = index.search(qv, top_k)
    return [(id2doc[i], float(s)) for i, s in zip(ids[0], scores[0])]

for doc, s in search("退货后钱多久能退回"):
    print(f"{s:.3f}  {doc}")
# 期望：「退款时效」和「退货流程」排在前面
```

### 第 5 步：重排（Rerank，质量跃升的关键）

向量检索是「粗排」（双塔模型，query 和 doc 独立编码，快但交互浅）。**Rerank 模型（交叉编码器）**把 query+doc 拼在一起打分，准但慢——只用于对 Top-50 精排：

```python
from sentence_transformers import CrossEncoder

reranker = CrossEncoder("BAAI/bge-reranker-v2-m3")

candidates = search("退货后钱多久能退回", top_k=4)
pairs = [["退货后钱多久能退回", doc] for doc, _ in candidates]
scores = reranker.predict(pairs)
final = sorted(zip([d for d, _ in candidates], scores), key=lambda x: -x[1])
```

**标准两段式**：向量召回 Top-50（快、全）→ Rerank 精排 Top-5（准）。生产上 RAG 准确率提升 10~20% 主要来自这一步。

## 常见坑（Top 5）

### 坑 1：维度不一致
```
Faiss assertion 'd == index->d' failed
```
入库是 1024 维（bge-m3），查询用 768 维（m3e）——**换模型必须全量重建索引**，向量空间不可混用。

### 坑 2：忘记归一化
用 COSINE/IP 索引但忘了 `normalize_L2`，或归一化了入库向量却忘了归一化查询向量——相似度全乱，且 bug 隐蔽（结果「看起来差不多」）。**入库和查询用同一个 encode 函数**，从源头杜绝。

### 坑 3：增量更新导致索引质量退化
IVF 建库后持续插入新分布数据（如新类目商品），聚类中心过时 → 召回缓慢下降。对策：
- 监控 Recall@10 周趋势，低于阈值触发 **retrain + 重建索引**
- HNSW 对此不敏感（增量插入天然支持），但删除多会产生「墓碑节点」，定期重建也有收益
- 大规模系统常用「增量小库 + 定期合并」：新数据先进小 Flat 库，查询时两路合并，夜间合并重建

### 坑 4：超长文本被静默截断
512 token 上限的模型喂 2000 字文档，后半部分**无声丢失**——检索永远查不到后半段内容。切块（第 1 步）就是解药；入库前打印 token 长度分布，P99 应在模型上限内。

### 坑 5：把「距离」当「相似度」直接用
L2 距离越小越相似，余弦/IP 越大越相似——两路融合或设阈值时搞反方向，结果全错。统一约定：内部一律转成「分数越大越好」再融合（第 05 章 RRF 只看排名可绕开此坑）。

## 面试 FAQ

**Q1：向量数据库和全文检索（ES）的核心区别？为什么生产上常混用？**
A：向量库按**语义距离**检索（Embedding 近邻），ES 按**词项匹配**（BM25）。语义查询（「怎么退货」）向量强，精确词项（型号/编号/人名）BM25 强。生产混用：两路召回 + RRF 融合，互补短板，这就是混合检索。

**Q2：HNSW 的原理？M、efConstruction、efSearch 分别影响什么？**
A：HNSW 是分层可导航小世界图——高层稀疏用于快速接近目标区域，底层稠密精细查找，查询复杂度约 O(log N)。M 是每节点最大边数（内存与连通性）；efConstruction 是建库候选集大小（图质量与建库耗时）；efSearch 是查询候选集大小（召回与延迟的**运行时**旋钮，调优先调它）。

**Q3：IVF 和 PQ 分别解决什么问题？为什么常组合成 IVF_PQ？**
A：IVF 用 K-Means 分桶把候选集缩到 nprobe 个桶，解决「少算距离」；PQ 把向量分段量化成字节码，解决「存储压缩 + 查表快算」。组合后：IVF 先粗筛掉 99% 数据，PQ 把剩余数据的距离计算变成查表——1 亿向量可压到几 GB 内存，召回损失用原向量重排补回。

**Q4：RAG 的标准流程？每个环节最容易出什么质量问题？**
A：流程：切块 → Embedding → 入库 → 检索（混合检索）→ Rerank → 拼 Prompt → LLM 生成。质量问题：切块切断语义（用结构切块+重叠）、Embedding 领域不匹配（换领域微调模型）、检索漏召回（混合检索+调 ef）、Top-K 噪音（Rerank）、Prompt 塞超（控制 token 预算）。

**Q5：为什么向量检索后还要 Rerank？用的什么模型？**
A：向量检索是双塔架构（query/doc 独立编码），为速度牺牲了交互深度；Rerank 用交叉编码器把 query+doc 拼接输入，能捕捉细粒度语义匹配，精度显著更高但慢 100 倍——所以只精排召回的 Top-50~200，输出 Top-5~10。代表模型：bge-reranker、Cohere Rerank。

**Q6：余弦相似度和欧氏距离怎么选？**
A：文本语义检索主流用**余弦**（关注方向不关注模长，对文本长度鲁棒）；且向量归一化后余弦 = 内积，计算更快。欧氏距离在向量模长有物理意义时用（如某些图像特征）。注意：归一化后 L2 与余弦的排序**等价**（L2² = 2 - 2cos），选哪个排序结果一样。

**Q7：亿级向量检索系统怎么设计？**
A：① 索引：IVF_PQ 或 HNSW+量化，内存估算后定分片数；② 架构：存算分离（数据落对象存储）、查询节点无状态可水平扩、副本扛 QPS；③ 更新：增量小库+定期合并重建；④ 质量：混合检索+Rerank；⑤ 监控：Recall@10、P99 延迟、副本滞后。

**Q8：Embedding 模型怎么选？怎么评估效果？**
A：中文自部署选 bge-m3/bge-large-zh，省心用 text-embedding-3。评估不看榜单看自己数据：构建「query-相关文档」评估集（可让 LLM 辅助生成），算 Recall@10 / MRR，对比候选模型；上线后看业务指标（点击率、RAG 回答采纳率）。

**Q9：标量过滤（如「只搜某类目」）在 ANN 里怎么实现？过滤太狠变慢怎么办？**
A：主流是 In-search 过滤（HNSW 遍历时跳过不满足条件的节点）。过滤条件命中 < 1% 时图遍历退化，对策：标量字段建索引、显式 Pre-filter、或按业务键直接分 collection/分区（物理隔离最优）。

**Q10：向量库支持更新和删除吗？有什么代价？**
A：支持但不廉价。更新 = 删旧插新；删除在 HNSW 里只是打墓碑标记，图连通性逐渐退化。高频更新场景设计：增量小库承接新数据 + 定期（夜间）全量重建合并；删除比例 > 20% 时建议触发重建。

## 自测

1. 动手跑通本章五步实战（可用随机向量代替真实 Embedding 验证管线）。
2. 为什么「切块」是 RAG 质量的第一道关口？300~500 字甜区背后的原因？
3. 说出向量检索双塔与 Rerank 交叉编码器的架构差异及其对速度/精度的影响。
4. 设计一个周级运行的索引健康度监控：监控什么指标、阈值多少、触发什么动作？

## 参考与官方链接

- [BGE Reranker](https://github.com/FlagOpen/FlagEmbedding)
- [LangChain Text Splitters](https://python.langchain.com/docs/concepts/text_splitters/)
- [RAG 评估框架 RAGAS](https://docs.ragas.io/)
- [Milvus 一致性级别](https://milvus.io/docs/consistency.md)
- [C-MTEB 中文 Embedding 榜单](https://github.com/FlagOpen/FlagEmbedding/tree/master/C_MTEB)
