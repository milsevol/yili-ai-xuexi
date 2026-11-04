# 03 ANN 算法原理

## 一句话

**ANN（近似最近邻）用「牺牲一点点召回率」换「数量级的速度提升」**：暴力检索 100 万条 768 维向量单次约需几百毫秒，HNSW 把它压到几毫秒（召回率仍有 95%+）。三大主流思路：**HNSW 图索引**（高召回高内存）、**IVF 倒排聚类**（均衡）、**PQ 乘积量化**（极致压缩）。

## 暴力检索的问题

```python
import numpy as np, time

N, D = 1_000_000, 768
db = np.random.default_rng(0).normal(size=(N, D)).astype(np.float32)
q = np.random.default_rng(1).normal(size=(D,)).astype(np.float32)

t0 = time.perf_counter()
scores = db @ q                      # 100万次×768次乘加 = 7.7 亿次浮点运算
topk = np.argsort(-scores)[:10]
print(f"暴力检索耗时: {(time.perf_counter()-t0)*1000:.0f} ms")  # 通常 100~500 ms
```

**复杂度 O(N·D)**：N 翻倍延迟翻倍。QPS 稍高就顶不住，且无法利用「提前建好索引」的思想。ANN 的思路：**建索引时多花时间组织数据，查询时只访问一小部分候选**。

## HNSW：分层可导航小世界图（目前最流行）

### 直觉：分层跳表 + 就近图

想象在一个国家找离目标最近的城市：
- **高层（稀疏）**：先看国家级地图，几个大跳快速接近目标区域
- **中层**：省级地图，缩小范围
- **底层（稠密）**：市级地图，精确找到最近城市

HNSW 就是向量空间的「分层跳表」：每个节点随机分配到若干层，层越高节点越少；查询从最高层的入口点开始，每层贪心走到当前层最近邻，再下到下一层，直到第 0 层精细搜索。

```
Layer 2:  A --------------------> 入口附近
            \
Layer 1:  A ---> B ---------> C    每下降一层，候选更密集
                    \
Layer 0:  ... -> B -> D -> E -> F -> 目标最近邻（精细层全连接）
```

### 核心参数

| 参数 | 含义 | 调大 | 调小 |
| --- | --- | --- | --- |
| **M** | 每个节点的最大邻居数 | 图更连通，召回↑，内存↑ | 省内存，可能孤岛 |
| **efConstruction** | 建索引时候选列表大小 | 图质量↑，建库慢 | 建库快，质量差 |
| **efSearch** | 查询时候选列表大小 | 召回↑，延迟↑ | 快但可能漏 |

**经验值**：M=16~48，efConstruction=200，efSearch 按召回要求从 64 往上调。

### 复杂度

查询 **O(log N)** 级别——这是它成为 Milvus/Qdrant/pgvector 默认索引的原因。代价：内存开销大（图结构 + 原始向量全在内存）。

## IVF：倒排文件索引（聚类分桶）

### 原理

1. **训练**：对全部向量跑 K-Means，得到 `nlist` 个聚类中心
2. **入库**：每个向量挂到最近中心对应的「桶」里
3. **查询**：query 只与 `nprobe` 个最近中心比，然后**只扫这几个桶**里的向量

```python
import numpy as np
from sklearn.cluster import KMeans

rng = np.random.default_rng(0)
N, D = 100_000, 128
db = rng.normal(size=(N, D)).astype(np.float32)

# 1. 建索引：nlist=256 个桶
nlist, nprobe = 256, 8
km = KMeans(n_clusters=nlist, n_init=1).fit(db)
labels = km.labels_
buckets = [db[labels == i] for i in range(nlist)]

# 2. 查询：只探查最近的 nprobe 个桶
q = rng.normal(size=(D,)).astype(np.float32)
dist_to_center = ((km.cluster_centers_ - q) ** 2).sum(axis=1)
probe = np.argsort(dist_to_center)[:nprobe]
cand = np.concatenate([buckets[i] for i in probe])     # 只扫约 N*nprobe/nlist 条
scores = cand @ q
print(f"候选数: {len(cand)} / {N}（只扫 {len(cand)/N:.1%}）")
```

**nprobe 是召回/延迟旋钮**：nprobe=1 最快但容易漏（真邻居恰好在隔壁桶）；nprobe=nlist 退化为暴力。

### 适用场景

- 内存有限（可放磁盘，只加载命中桶）
- 向量量超大（亿级）且能接受 95% 左右召回
- 常与 PQ 组合成 **IVF_PQ**（FAISS 经典配置）

## PQ：乘积量化（极致压缩）

### 原理

把 D 维向量切成 m 段（如 768 维切 96 段 × 8 维），每段独立跑 K-Means（k=256），于是**每段用 1 个字节（中心编号）表示**：

```
原向量: [8维] [8维] [8维] ... [8维]   (768维 × 4字节 = 3072 字节)
量化后:  #17   #203  #45   ...  #91   (96 段 × 1字节 = 96 字节)  ← 压缩 32 倍
```

距离计算变成查表：预先算好 query 每段与 256 个中心的距离，累加 m 段即可（ADC 非对称距离）。

### 代价与组合

- **精度损失**：量化误差 → 召回率下降，通常搭配**重排**（PQ 粗筛 Top-100，再用原始向量精排 Top-10）
- **OPQ**（Optimized PQ）：先对向量做旋转变换再切分，段间方差更均衡，精度更高
- 经典组合：**IVF_PQ**（先分桶减少候选，再桶内 PQ 压缩）——1 亿向量可压到几 GB

```python
# FAISS 中的 IVF_PQ（第 04 章详解）
import faiss
quantizer = faiss.IndexFlatIP(768)
index = faiss.IndexIVFPQ(quantizer, 768, 256, 96, 8)  # nlist=256, 96段, 每段8bit
index.train(vectors)
index.add(vectors)
index.nprobe = 16
D, I = index.search(query, 10)
```

## 三种算法对比

| 维度 | HNSW | IVF | PQ |
| --- | --- | --- | --- |
| 核心思想 | 分层图导航 | 聚类分桶 | 分段量化压缩 |
| 查询复杂度 | ~O(log N) | O(nprobe·N/nlist·D) | 查表 O(m·k) |
| 召回率 | 95~99% | 90~97% | 单独用较低，需重排 |
| 内存占用 | **高**（图+原向量） | 中 | **极低**（1/32） |
| 建库速度 | 慢 | 中（要训 K-Means） | 快 |
| 支持增删 | 较好 | 好 | 一般 |
| 典型场景 | 在线服务首选 | 大规模+内存受限 | 超大规模压缩 |

**实战默认**：
- 千万级以内、内存够 → **HNSW**
- 亿级、内存吃紧 → **IVF_PQ + 重排**
- 想要简单 → 直接用库默认（Milvus/Qdrant 默认 HNSW）

## 召回率与延迟的权衡（Recall@K）

评估方法：ANN 返回的 Top-K 与暴力真值 Top-K 的交集占比。

```python
def recall_at_k(ann_ids, truth_ids, k=10):
    return len(set(ann_ids[:k]) & set(truth_ids[:k])) / k
```

经验曲线（HNSW 为例）：

| efSearch | 召回@10 | 相对延迟 |
| --- | --- | --- |
| 16 | ~85% | 1x |
| 64 | ~95% | 2x |
| 128 | ~98% | 4x |
| 512 | ~99.5% | 10x |

**口诀**：召回和延迟不可兼得，按业务定指标（RAG 通常要求 Recall@10 ≥ 95%），再用参数去够线。延迟还受维度、数据分布（聚簇程度）影响，**永远用自己的数据实测**。

## 常见问题

**Q：HNSW 为什么比暴力快这么多？**
A：暴力要算全部 N 个距离，HNSW 靠分层图「贪心导航」，实际只访问几百到几千个节点（log 级别），其余 99.9% 的数据根本不碰。

**Q：IVF 的 nlist 怎么定？**
A：经验公式 `nlist ≈ 4 × sqrt(N)`。100 万 → 约 4000（FAISS 官方建议 1024~4096 即可）；1 亿 → 数万。太大训练慢，太小每桶太粗。

**Q：PQ 会损失多少精度？**
A：取决于数据和段数。通常 Recall@10 掉 3~10 个百分点，所以生产上几乎总是「PQ 粗筛 + 原向量重排」两段式，把精度补回来。

**Q：为什么新建索引后要等一会才能查到新数据？**
A：图/聚类索引需要**构建/合并**过程。HNSW 是增量插入的（实时可查但图质量渐进优化）；IVF 新增向量只挂桶不重建，但新数据分布偏移大时需要 retrain——这也是「增量更新」话题，见第 06 章。

## 自测

1. 画出 HNSW 的分层结构并解释查询路径。M、efConstruction、efSearch 各自影响什么？
2. IVF 的 nlist 和 nprobe 分别在建库和查询的哪一步起作用？
3. PQ 为什么能把存储压缩 32 倍？为什么要搭配重排？
4. 亿级向量、单机内存 64GB，你选什么索引组合？

## 参考与官方链接

- [HNSW 论文](https://arxiv.org/abs/1603.09320)
- [FAISS 索引选择指南](https://github.com/facebookresearch/faiss/wiki/Guidelines-to-choose-an-index)
- [PQ 原始论文](https://lear.inrialpes.fr/pubs/2011/JDS11/jegou_searching_with_quantization.pdf)
- [ANN Benchmarks](https://ann-benchmarks.com/)
