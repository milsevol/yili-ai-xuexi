# 05 重排序Rerank

## 一句话

**Rerank 是检索后的「精排裁判」**：向量检索（Bi-Encoder）为了快，把问题和文档**分别**编码取向量相似度，丢失了细粒度交互信息；Rerank 模型（Cross-Encoder）把「问题 + 文档」**拼在一起**过模型，逐对算相关性——精度高一个档次，但只能处理几十条候选。两者是「海选 → 决赛」的分工。

## 为什么需要 Rerank

### Bi-Encoder（检索用）vs Cross-Encoder（精排用）

```
Bi-Encoder（向量检索）：              Cross-Encoder（Rerank）：

问题 → Encoder → 向量A                [CLS] 问题 [SEP] 文档 [SEP]
                    ↘                                  ↓
                     余弦相似度 → 分数           Encoder 全交互 → 分数
                    ↗                                  ↑
文档 → Encoder → 向量B                问题和文档的每个 token 互相看见

特点：文档向量可离线预计算，            特点：无法预计算，每对都要在线跑，
      百万级检索毫秒返回                      精度高但只能算几十对
```

| 维度 | Bi-Encoder | Cross-Encoder |
| --- | --- | --- |
| 精度 | 中（向量压缩损失交互信息） | **高**（token 级全交互） |
| 延迟 | 毫秒级（ANN 索引） | 每对 5~20ms，Top-50 需 0.3~1s |
| 能否扫全库 | 能（预计算 + 索引） | **不能**（O(N) 推理不可接受） |
| 角色 | 召回（Top-50，宁多勿漏） | 精排（Top-5，宁缺毋滥） |

**结论：Rerank 不是可选项，是检索质量的放大器。** 工业界 RAG 的默认链路就是「粗排 Top-50 → Cross-Encoder 精排 Top-5」。

## Cross-Encoder 原理速览

- 输入：`[CLS] query [SEP] passage [SEP]`，拼接后整段过 Transformer
- 输出：取 `[CLS]` 位置的表示接一个线性层，产出相关性分数（回归或二分类）
- 训练数据：(query, 正样本, 负样本) 三元组，难点负例（hard negative）决定上限
- 推理：分数天然可比，直接排序截断

```python
# bge-reranker 最小使用示例（本地推理）
from sentence_transformers import CrossEncoder

reranker = CrossEncoder("BAAI/bge-reranker-v2-m3")   # 中文场景推荐 v2-m3

pairs = [
    ("年假有多少天", "正式员工每年享有 15 天年假，入职满一年后可申请……"),
    ("年假有多少天", "公司食堂午餐供应时间为 11:30-13:00……"),
]
scores = reranker.predict(pairs)      # [8.73, -2.15] 之类，越大越相关
ranked = sorted(zip(pairs, scores), key=lambda x: x[1], reverse=True)
```

生产部署建议：用 TEI（Text Embeddings Inference）、vLLM 或 ONNX 加速，batch 推理 Top-50 控制在 300ms 内。

## Rerank vs 直接向量排序：效果对比

典型场景实测（示意，具体数字以你的评估集为准）：

| 方案 | Recall@5 | 答案正确率 | 延迟 |
| --- | --- | --- | --- |
| 仅向量检索 Top-5 | 62% | 55% | 30ms |
| 向量 Top-50 + Rerank Top-5 | **81%** | **74%** | 30ms + 300ms |
| 多路召回 Top-50 + Rerank Top-5 | **88%** | **80%** | 350ms |

**结论**：
- 向量直接取 Top-5 → 相关文档经常被压在 6~20 名，LLM 根本看不到
- 放宽到 Top-50 再过 Rerank → 把被埋没的相关文档捞回前 5，收益巨大
- 代价是 200~500ms 的精排延迟——绝大多数知识库场景值得

## bge-reranker 实战要点

| 项 | 建议 |
| --- | --- |
| 模型选择 | 中文：bge-reranker-v2-m3；英文：bge-reranker-v2-gemma / Cohere Rerank API |
| 输入长度 | 模型上限通常 512 token——Chunk 太长会被截断，和 03 章的块大小联动设计 |
| 候选数量 | Top-30~Top-100 进 Rerank，性价比甜区 50 |
| 分数阈值 | 设最低分（如 bge 的 sigmoid 后 < 0.3 视为不相关），全都不相关时让 LLM 明说「未找到」而不是硬答 |
| 批处理 | 50 对一次 batch 推理，不要逐对循环 |

## Top-K 截断策略

Rerank 之后留几个给 LLM？三个因素权衡：

1. **上下文窗口与成本**：每个 Chunk 512 token × Top-5 = 2500+ token 进 Prompt
2. **Lost in the Middle**：塞 20 段时 LLM 对中间段利用率骤降——Top-K 不是越大越好
3. **分数断崖**：观察 Rerank 分数分布，分数骤降处就是天然截断点

```python
def truncate(reranked: list[tuple[dict, float]],
             max_k: int = 5, min_score: float = 0.3,
             max_tokens: int = 3000) -> list[dict]:
    """三重截断：数量上限 + 分数下限 + token 预算。"""
    picked, budget = [], max_tokens
    for doc, score in reranked[:max_k]:
        if score < min_score:        # 分数断崖 → 后面不要了
            break
        if budget - doc["n_tokens"] < 0:
            break
        picked.append(doc)
        budget -= doc["n_tokens"]
    return picked
```

**经验值**：Top-3 ~ Top-8、总分 1000~3000 token。宁可少而精。

## 两级排序完整代码骨架

```python
def search_pipeline(question: str) -> list[dict]:
    # 第 1 级：多路召回（快，保召回）
    vec_hits  = vector_db.search(embed(question), top_k=30)
    bm25_hits = bm25.search(question, top_k=30)
    candidates = rrf_fuse([vec_hits, bm25_hits], top_k=50)

    # 第 2 级：Cross-Encoder 精排（准，保精度）
    pairs = [(question, c["text"]) for c in candidates]
    scores = reranker.predict(pairs)
    reranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)

    # 截断
    return truncate(reranked, max_k=5, min_score=0.3)
```

## 常见问题

**Q：能不能只用 Cross-Encoder 不用向量检索，精度不是更高？**
A：不能。Cross-Encoder 对每个 (query, doc) 对都要在线推理，百万级文档意味着百万次推理/查询，延迟和成本完全不可接受。正确姿势永远是「Bi-Encoder 海选 + Cross-Encoder 决赛」。

**Q：Rerank 模型和 Embedding 模型要配套吗？**
A：不需要配套，可以混用（bge 向量 + Cohere rerank 也行）。但中文场景建议都选中文友好的模型。换 Rerank 模型**不需要**重建索引——它是在线的，这也是它比 Embedding 模型好迭代的原因。

**Q：直接用 LLM（如 GPT-4）做 Rerank 行不行？**
A：行，叫 LLM Reranker（listwise 排序），精度可以很高，但延迟秒级、成本高。适合对延迟不敏感的离线场景或作为评估基准；在线链路首选小参数 Cross-Encoder。

**Q：Rerank 之后召回率会变化吗？**
A：**不会**。Rerank 只在候选集内部重排序，不会引入新文档。候选集里没有的，Rerank 救不回来——所以检索阶段的 Top-50 一定要保召回率。

**Q：多个 Chunk 分数相近时怎么办？**
A：分数相近说明相关性差不多，此时做**多样性去重**（MMR 思想）：同一个文档的相邻 Chunk 只保留分数最高的一两个，给不同来源的文档留位置，避免 Top-5 全是同一段落的车轱辘话。

## 自测

1. 画出 Bi-Encoder 和 Cross-Encoder 的结构差异，解释为什么后者精度高但慢。
2. 为什么换 Rerank 模型不用重建索引，换 Embedding 模型却要？
3. 设计 Top-K 截断策略时要考虑哪三个因素？
4. 线上 RAG 答案引用了一段不相关文档，按「检索 → 重排 → 拼装」链路，你先看哪一环？

## 参考与官方链接

- [bge-reranker（FlagEmbedding）](https://github.com/FlagOpen/FlagEmbedding)
- [Cohere Rerank 文档](https://docs.cohere.com/docs/rerank)
- [Sentence-Transformers Cross-Encoder](https://www.sbert.net/examples/cross_encoder/applications/README.html)
- [Lost in the Middle（长上下文位置偏见）](https://arxiv.org/abs/2307.03172)
- [ColBERT（Late Interaction，另一种精排思路）](https://arxiv.org/abs/2004.12832)
