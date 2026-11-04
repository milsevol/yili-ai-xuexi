# 04 FAISS 与 Milvus 实战

## 一句话

**FAISS 是嵌入式算法库**（pip 装好就能用，索引算法最全，但只是「库」不是「数据库」）；**Milvus 是生产级分布式向量数据库**（持久化、分片副本、元数据过滤、REST 全套）。学习路径：先用 FAISS 理解索引行为，再用 Milvus/Qdrant 上生产。

## FAISS 快速上手

```bash
pip install faiss-cpu   # 或 faiss-gpu
```

### 最小例子

```python
import faiss
import numpy as np

rng = np.random.default_rng(42)
D = 128
xb = rng.normal(size=(100_000, D)).astype(np.float32)  # 库
xq = rng.normal(size=(5, D)).astype(np.float32)        # 查询

index = faiss.IndexFlatIP(D)        # 内积暴力索引
faiss.normalize_L2(xb)              # 归一化 → 内积 = 余弦
faiss.normalize_L2(xq)
index.add(xb)
print("库中向量数:", index.ntotal)

scores, ids = index.search(xq, 10)  # Top-10
print(ids.shape, scores.shape)      # (5, 10) (5, 10)
```

**两条铁律**：
1. `IndexFlatIP`（内积）/ `IndexFlatL2`（欧氏）——先用暴力索引拿**真值基线**
2. 用余弦相似度就先 `normalize_L2`，再选 IP 索引

## FAISS 索引类型选择

| 索引 | 类型 | 训练 | 内存 | 召回 | 适用 |
| --- | --- | --- | --- | --- | --- |
| `IndexFlatIP/L2` | 暴力 | 不需要 | 高（原向量） | 100% | < 10 万、拿真值 |
| `IndexIVFFlat` | IVF | K-Means | 高 | 90~97% | 百万级入门 |
| `IndexHNSWFlat` | HNSW | 不需要 | 高（图+向量） | 95~99% | **千万级首选** |
| `IndexIVFPQ` | IVF+PQ | 需要 | **低**（1/32） | 90~95% | 亿级、内存受限 |
| `IndexLSH` | 哈希 | 不需要 | 低 | 低 | 二值粗筛，少用于稠密向量 |

### IndexIVFFlat 完整示例

```python
D = 128
xb = rng.normal(size=(1_000_000, D)).astype(np.float32)

quantizer = faiss.IndexFlatIP(D)
index = faiss.IndexIVFFlat(quantizer, D, 1024, faiss.METRIC_INNER_PRODUCT)

index.train(xb)          # 必须！K-Means 学聚类中心
index.add(xb)
index.nprobe = 16        # 查询时探 16 个桶

scores, ids = index.search(xq, 10)
```

### IndexHNSWFlat 完整示例

```python
index = faiss.IndexHNSWFlat(D, 32)       # M=32
index.hnsw.efConstruction = 200          # 建库质量
index.hnsw.efSearch = 64                 # 查询召回/延迟旋钮
index.add(xb)                            # 无需 train
scores, ids = index.search(xq, 10)
```

### 索引持久化

```python
faiss.write_index(index, "my.index")
index = faiss.read_index("my.index")     # 重启后秒级加载
```

**注意**：FAISS 不存原始文本/元数据——需要自己维护 `id → 文档` 映射（sqlite/parquet 均可）。

## 用 GPU 加速（可选）

```python
res = faiss.StandardGpuResources()
gpu_index = faiss.index_cpu_to_gpu(res, 0, index)   # 迁到 GPU 0
scores, ids = gpu_index.search(xq, 10)              # 百万级 QPS 可提升 10x
```

## Milvus：生产级向量数据库

### 架构速览

```
                ┌─────────────┐
   SDK/REST ──> │  Proxy(接入) │
                └──────┬──────┘
        ┌──────────────┼──────────────┐
   Query Node      Data Node      Index Node
   (查询执行)      (数据写入)     (索引构建)
        └──────────────┼──────────────┘
                ┌─────────────┐
                │ 对象存储(S3) │  ← 存算分离：数据/索引落对象存储
                └─────────────┘
   RootCoord / QueryCoord / DataCoord  ← 协调层（元数据在 etcd）
```

**核心设计**：存算分离 + 无状态计算节点 → 查询节点可独立扩缩容，数据可靠性交给对象存储。

### 部署

```bash
# 单机版（学习/小流量）
docker run -d --name milvus -p 19530:19530 milvusdb/milvus:latest standalone

# 生产：docker-compose（含 etcd + minio）或 K8s + Helm Chart
```

### Python SDK 实战

```python
from pymilvus import MilvusClient, DataType

client = MilvusClient(uri="http://localhost:19530")

# 1. 建 collection（≈ 表）：向量字段 + 标量字段
schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
schema.add_field("id", DataType.INT64, is_primary=True)
schema.add_field("vector", DataType.FLOAT_VECTOR, dim=768)
schema.add_field("category", DataType.VARCHAR, max_length=64)  # 标量，可过滤

client.create_collection("docs", schema=schema)

# 2. 建索引：HNSW + COSINE
idx = client.prepare_index_params()
idx.add_index("vector", index_type="HNSW", metric_type="COSINE",
              params={"M": 32, "efConstruction": 200})
client.create_index("docs", idx)

# 3. 插入
client.insert("docs", data=[
    {"vector": vec1, "category": "refund"},
    {"vector": vec2, "category": "shipping"},
])

# 4. 检索：向量 + 标量过滤
res = client.search(
    "docs",
    data=[query_vec],
    limit=10,
    filter='category == "refund"',          # 标量过滤
    search_params={"params": {"ef": 64}},
    output_fields=["category"],
)
```

**要点**：
- `metric_type="COSINE"` 时 Milvus 内部自动归一化
- 标量过滤语法类似 SQL WHERE，过滤在 ANN 搜索的图遍历过程中生效（第 05 章详解）
- 集群模式水平扩展：加 QueryNode 提升并发，加 DataNode 提升写入

## Qdrant 与 Chroma 简评

### Qdrant（Rust，中小规模生产推荐）

```python
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

client = QdrantClient("localhost", port=6333)
client.create_collection("docs", vectors_config=VectorParams(size=768, distance=Distance.COSINE))
client.upsert("docs", [PointStruct(id=1, vector=vec, payload={"category": "refund"})])
res = client.search("docs", query_vector=vec, limit=10,
                    query_filter={"must": [{"key": "category", "match": {"value": "refund"}}]})
```

- 优点：单二进制部署极简单、payload 过滤强、Rust 性能稳、磁盘索引省内存
- 缺点：超大规模（10 亿+）案例少于 Milvus

### Chroma（嵌入式，原型首选）

```python
import chromadb
client = chromadb.PersistentClient(path="./chroma_db")
coll = client.create_collection("docs")
coll.add(documents=["退货流程说明", "运费计算规则"],
         embeddings=[vec1, vec2], ids=["d1", "d2"])
res = coll.query(query_embeddings=[qvec], n_results=5)
```

- 优点：零部署、API 极简、自动管理 Embedding
- 缺点：单机、规模上限低，**只适合原型和小项目**

## 选型对比表

| 维度 | FAISS | Milvus | Qdrant | Chroma | pgvector |
| --- | --- | --- | --- | --- | --- |
| 形态 | 嵌入式库 | 分布式服务 | 单机/分布式服务 | 嵌入式 | PG 插件 |
| 规模上限 | 单机内存 | **百亿级** | 十亿级 | 百万级 | 千万级 |
| 持久化 | 手动 dump | 对象存储 | 磁盘快照 | 本地文件 | 表 |
| 标量过滤 | 无（自实现） | 强 | **强** | 中 | SQL 全能力 |
| 高可用 | 无 | 分片+副本 | 副本 | 无 | 依赖 PG |
| 学习成本 | 低 | 中 | 低 | **极低** | 低（会 SQL 即可） |
| 典型场景 | 算法研究/嵌入 | 大规模生产 | 中小规模生产 | Demo/原型 | 已有 PG 栈 |

**决策树**：

```
数据量 < 10 万，嵌入式？        → FAISS / Chroma
已有 PostgreSQL，量 < 千万？     → pgvector
中小规模生产（千万级），要简单？  → Qdrant
大规模生产（亿级+），要分布式？   → Milvus
```

## 常见问题

**Q：FAISS 能直接上生产吗？**
A：可以但要自己补齐：文本存储、id 映射、并发锁、持久化、扩容。很多公司用「FAISS + 自研服务层」扛住了亿级流量——前提是团队有运维能力，否则直接用 Milvus/Qdrant 更省心。

**Q：Milvus 的 COSINE 距离需要我自己归一化吗？**
A：不需要，metric_type=COSINE 时内部处理。但 **FAISS 必须手动 normalize_L2**，两者别记混。

**Q：collection 和 index 是什么关系？**
A：collection ≈ 表（存数据），index ≈ 建在向量字段上的检索结构。同一 collection 查询走索引；没建索引也能查（退化为暴力，慢）。索引参数（M/ef）在建 index 和 search 时分别指定。

**Q：向量库支持 UPDATE 吗？**
A：支持但昂贵——向量变了等于「删旧插新 + 局部重建索引」。高频更新场景（用户实时行为）通常用「近期增量小库 + 定期合并到主库」的架构。

## 自测

1. FAISS 的 IndexFlatIP 为什么必须配合 normalize_L2 才能当余弦索引用？
2. IndexIVFFlat 的 train 步骤在学什么？不 train 直接 add 会怎样？
3. Milvus 的存算分离架构带来什么好处？
4. 你的场景：500 万文档、单机、要求部署简单——选哪个产品？

## 参考与官方链接

- [FAISS GitHub](https://github.com/facebookresearch/faiss) / [索引选择指南](https://github.com/facebookresearch/faiss/wiki/Guidelines-to-choose-an-index)
- [Milvus 文档](https://milvus.io/docs) / [pymilvus](https://milvus.io/api-reference/pymilvus/v2.4.x/About.md)
- [Qdrant 文档](https://qdrant.tech/documentation/)
- [Chroma 文档](https://docs.trychroma.com/)
- [pgvector](https://github.com/pgvector/pgvector)
