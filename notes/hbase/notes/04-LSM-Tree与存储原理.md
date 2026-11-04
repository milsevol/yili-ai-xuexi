# 04 LSM-Tree与存储原理

## 一句话

**LSM-Tree（Log-Structured Merge-Tree）** 是 HBase 随机写高性能的秘密：写操作直接追加到内存里的 **MemStore**（O(1)），满了就**顺序 Flush** 成 HFile（O(n)），多个 HFile 再通过 **Compaction** 合并成一个——牺牲一点读路径（要查多个文件 + Merge），换来了极低的写放大。

## 为什么需要 LSM-Tree

传统 B+ 树写一条数据：

```
写 user001:name="Alice"
  → 找到叶子节点（可能要遍历多层索引）
  → 插入或更新（可能触发页分裂）
  → 随机磁盘 IO
  → 写放大高（一次写可能改多个页）
  → 高并发写时磁盘随机 IO 成为瓶颈
```

LSM-Tree 的思路：

```
写 user001:name="Alice"
  → 追加到内存 MemStore（O(1)，无磁盘 IO）
  → 返回 Ack 给客户端

MemStore 满了（默认 128MB）
  → 顺序写出一个 HFile（O(n)，磁盘顺序写）
  → 新 HFile 加入 Region 的 StoreFile 列表
  → 清空 MemStore

多个 HFile 累积后
  → Compaction 合并成一个新 HFile
  → 清理旧 HFile
```

**核心思想**：把随机写变成**内存追加 + 顺序刷盘**，用后续的合并来保证读性能。

## LSM-Tree 与 B+ 树对比

| 维度 | B+ 树（传统关系库） | LSM-Tree（HBase/RocksDB） |
| --- | --- | --- |
| 写延迟 | 高（随机 IO、页分裂） | 低（内存追加、顺序 Flush） |
| 读延迟 | 稳定（索引定位） | 可能抖动（多个文件 + Merge） |
| 写吞吐 | 低 | 高 |
| 空间放大 | 低 | 中（Compaction 前有冗余文件） |
| 读放大 | 低 | 中（要查多个 SSTable/HFile） |
| 崩溃恢复 | 靠 WAL + redo | 靠 WAL + 回放 MemStore |

## HBase 的 LSM-Tree 变体

HBase 对经典 LSM-Tree 做了分层：

```
MemStore（内存，每个 CF 一个）
  │ Flush（满了或周期到）
  ▼
StoreFile / HFile 层（在 HDFS 上，有序 KV 文件）

HFile 按 Compaction 历史分层：

Level 0: 刚 Flush 出来的 HFile（大小不一，可能有重叠）
  │
  │ Minor Compaction（挑选几个合并）
  ▼
Level 1: 合并后的大 HFile（同层不重叠，通常 1 个）
  │
  │ Major Compaction（全部合并）
  ▼
Level 1（更干净）

关键差异：经典 LSM-Tree 是多层次（L0→L1→L2→...），HBase 默认是单层（L0→L1）
  但 2.x 引入了分层 Compaction（ExploringCompactionPolicy），可配多层
```

## MemStore

MemStore 是 Region 内每个 CF 的**内存写缓冲**：

| 配置 | 默认 | 说明 |
| --- | --- | --- |
| `hbase.hregion.memstore.flush.size` | 134217728 (128MB) | 单个 CF 的 MemStore 触发 Flush 的阈值 |
| `hbase.regionserver.global.memstore.size` | 0.40（堆的 40%） | RegionServer 所有 CF 的总 MemStore 上限 |
| `hbase.hregion.memstore.block.multiplier` | 4 | 当总 MemStore 超过 `flush.size × multiplier` 时，**阻塞写入** |
| `hbase.regionserver.flush.perchange` | 10 | 每次 Flush 最多 Flush 多少个 CF |

- **阻塞写入**：当 RS 总 MemStore 超过 4 × 单个 Flush 阈值时，新的 Put 请求会被阻塞，直到部分 MemStore Flush 完毕。这是**背压机制**，防止 RS 内存溢出。
- **多段 Flush（2.5+）**：一个 MemStore 内部可以分成多段（segment），Flush 时可以只 Flush 已经"冻结"的段，写不被完全阻塞。
- **MemStore 的数据结构**：默认是 `DefaultMemStore`（基于 CellChunkMap + Segment）；也可以用 `BucketCache` 堆外内存。

## HFile —— LSM-Tree 的磁盘文件

HFile 是 HBase 自有的有序 KV 文件格式（类似 SSTable），存在 HDFS 上：

```
HFile 结构：
┌─────────────────────────────────────┐
│  Data Block 1（RowKey 有序）         │
│    key → value                       │
│    key → value                       │
│    ...                               │
├─────────────────────────────────────┤
│  Data Block 2                        │
│    ...                               │
├─────────────────────────────────────┤
│  Meta Blocks（可选）                 │
│    BloomFilter                       │
├─────────────────────────────────────┤
│  FileInfo（元数据）                   │
│    LASTKEY, AVG_KEY_LEN, ...        │
├─────────────────────────────────────┤
│  Data Block Index（块级索引）         │
│    "row123" → Data Block 1 offset   │
├─────────────────────────────────────┤
│  BloomFilter                         │
├─────────────────────────────────────┤
│  Trailer（版本、数据块数等）          │
└─────────────────────────────────────┘
```

- **Data Block**：默认 64KB，RowKey 有序；读时整块加载进 BlockCache。
- **Data Block Index**：每个索引项对应一个 Data Block 的起始 RowKey；读时先查索引定位 Block 位置。
- **BloomFilter**：快速判断「某个 RowKey 大概率在/不在这个 HFile」，避免不必要的 Block 读取。
- **压缩**：SNAPPY（推荐，快）、GZ（省空间）、LZ4、ZSTD（高压缩+快）。
- **编码**：DIFF / FAST_DIFF / PREFIX 等列族编码，减少 HFile 存储空间。

## Flush 流程

```
触发条件（任一满足即触发）：
  ① MemStore 大小 ≥ flush.size（128MB）
  ② RegionServer 级总 MemStore 超全局上限
  ③ Region 关闭前（Split/迁移）
  ④ 手动调 flush 命令

Flush 流程：
  ① 冻结 MemStore（新建一个空的接收后续写）
  ② 把冻结的 MemStore 数据写入 HDFS 临时路径（.tmp 后缀）
  ③ 写 Data Block + Data Block Index + BloomFilter
  ④ fsync 到 HDFS
  ⑤ 重命名临时文件为正式 StoreFile
  ⑥ 清空冻结 MemStore
  ⑦ WAL 标记可回收
  ⑧ （可选）触发 Minor Compaction
```

- **Flush 不阻塞写**：冻结后新的写入进新 MemStore，旧 MemStore 在后台 Flush。
- **Flush 是 Region 级**：一个 Region 有多个 CF，每个 CF 各有一个 MemStore；Flush 时每个 CF 各生成一个 HFile。

## Compaction —— LSM-Tree 的关键

多个 HFile 累积后，读路径要查每个文件的 BloomFilter + Index，文件越多越慢。**Compaction 就是合并多个 HFile 成一个干净的大 HFile**：

### 两种类型

| 类型 | 触发 | 作用 | 耗时/IO |
| --- | --- | --- | --- |
| **Minor Compaction** | 自动（定期或文件数达阈值） | 合并选中的几个 HFile 成一个 | 较小 |
| **Major Compaction** | 手动或自动（周期到） | 合并**所有** HFile 成一个；清理墓碑标记、过期版本、删除行 | 大（全量读写） |

### Compaction 策略

| 策略 | 说明 | 适用 |
| --- | --- | --- |
| **ExploringCompactionPolicy**（默认 2.5+） | 分层合并，先合并小文件，再逐层向上 | 大多数场景，IO 平滑 |
| **RatioBasedCompactionPolicy**（旧默认） | 按大小比挑选文件，小文件优先 | 老版本兼容 |
| **FIFOCompactionPolicy** | 按时间淘汰最老的文件 | 时序数据、纯追加写、不读旧数据 |
| **DateTieredCompaction** | 按时间分 Tier 合并 | 时序数据、冷热分层 |

### 触发阈值

| 配置 | 默认 | 说明 |
| --- | --- | --- |
| `hbase.hstore.compactionThreshold` | 3 | 同一 CF 至少 3 个 HFile 才触发 Minor |
| `hbase.hstore.compaction.max` | 10 | 一次 Minor 最多合并多少个 HFile |
| `hbase.hstore.compaction.min.size` | 128MB | 小于这个大小的 HFile 优先被选中 |
| `hbase.hstore.compaction.max.size` | LONG.MAX_VALUE | 大于这个大小的 HFile 不参与合并 |
| `hbase.hregion.majorcompaction` | 7 天（604800000ms） | Major Compaction 周期（0 = 关闭自动 Major） |

### Compaction 如何影响性能

```
Compaction 过程：
  ① 读多个旧 HFile 的全部数据
  ② Merge：按 RowKey 排序合并，去重、清理墓碑、清理过期版本
  ③ 写出新 HFile 到 HDFS
  ④ fsync
  ⑤ 把新 HFile 加进 Region 的 StoreFile 列表
  ⑥ 删除旧 HFile

性能影响：
  ✅ 好处：读路径变短（HFile 数量 ↓），清理垃圾（墓碑、过期版本）
  ❌ 坏处：写放大（读 N 个大文件 + 写 1 个更大的）、HDFS IO 吃满、可能影响读写延迟
```

> **写放大**：一个 Cell 从写入到最终稳定，可能经历 `Flush（写 1 次） + Minor（合并多次） + Major（全量合并 1 次）`。写放大倍数通常在 **3–10 倍**，取决于 Compaction 策略。

## BloomFilter —— 读路径的加速器

BloomFilter 是一个**概率性数据结构**：用极小空间判断「一个 key 大概率在/不在集合中」。

| 属性 | 说明 |
| --- | --- |
| 无假阴性 | key 真在集合里 → BloomFilter 一定说在（或说大概率在） |
| 有假阳性 | key 不在集合里 → BloomFilter **可能**说在（但概率很低） |
| HBase 粒度 | `ROW`（默认，按 RowKey）或 `ROWCOL`（按 RowKey+Qualifier） |
| False Positive Rate | 默认约 1%，可通过调整空间大小控制 |

```
Get user001:name
  → BloomFilter 查 HFile A：大概率不在 → 跳过 A ✅（省了一次 Block 读）
  → BloomFilter 查 HFile B：大概率在  → 继续查 Data Block Index → 读 Block
  → 找着了 ✅

Get user999:name（不存在）
  → BloomFilter 查 HFile A：大概率不在 → 跳过 A ✅
  → BloomFilter 查 HFile B：大概率不在 → 跳过 B ✅
  → BloomFilter 查 HFile C：大概率在（假阳性！）→ 还是要查 C 的 Data Block Index → 没找到
  → 全部查完 → 返回不存在
```

## 完整读路径（覆盖所有层）

```
Client Get/Scan → RegionServer
  │
  ├── Layer 1: BlockCache（堆外内存，缓存 HFile Data Block）
  │   命中 → 直接返回 Block → Filter/版本合并 → 结束（最快）
  │   未命中 → 继续
  │
  ├── Layer 2: MemStore（内存，Region 级）
  │   命中 → 记录；还需要查 HFile（更新版本可能在 MemStore，旧版本在 HFile）
  │   未命中 → 继续
  │
  ├── Layer 3: HFile 列表（L0 + L1）
  │   对每个 HFile：
  │     a. BloomFilter → 不在 → 跳过
  │     b. Data Block Index → 定位 Block offset
  │     c. HDFS 读 Block → 放入 BlockCache
  │     d. Block 内查找
  │
  └── Layer 4: Merge（按时间戳倒序取最新版本）
      MemStore 命中 + HFile 命中 → 取最新 → 返回
      全部未命中 → 返回 Not Found
```

## BlockCache

| 配置 | 默认 | 说明 |
| --- | --- | --- |
| `hfile.block.cache.size` | 0.40（RS 堆的 40%） | Data Block 缓存占堆比例 |
| `hbase.bucketcache.ioengine` | heap（2.5） | BucketCache 类型：heap/offheap/file |
| `hbase.bucketcache.size` | 0 | BucketCache 大小（MB），0 = 关闭 |
| `hbase.bucketcache.percentage.in.combinedcache` | 0.9 | CombinedCache 中 BucketCache 占比 |

- **LruBlockCache**：老版，纯堆内存。
- **BucketCache**：堆外内存或文件内存映射，默认 0（关闭）。大集群建议开 BucketCache 用堆外，省堆 GC。
- 命中率：生产集群 BlockCache 命中率通常 > 90%；< 70% 就要看 HFile 数量或 RS 内存。

## 存储层的 GC

HBase RegionServer 是 JVM，GC 直接影响性能：

| 区域 | 推荐 GC | 说明 |
| --- | --- | --- |
| RS 堆（MemStore + BlockCache） | G1GC / ZGC | CMS 已被废弃；G1 默认，2.5 支持 ZGC |
| 堆外 | N/A | BucketCache、DirectBuffer 不受 JVM GC 管 |
| 常见问题 | Full GC | 长时间 Stop-The-World（STW）导致 RegionServer 无法心跳 → HMaster 以为它挂了 → 触发 Region 重分配 |

## 易错点清单

1. **Compaction 不是坏事**：它是 LSM-Tree 保证读性能的机制，但 Major Compaction 很重；观察 IO 利用率和延迟来调策略。
2. **Minor Compaction 不等于 Major**：Minor 只合并选中的几个，Major 合并全部并清理墓碑。
3. **Flush 不生成墓碑**：只有 Delete 操作才写墓碑标记，Flush 只是把 MemStore 写进 HFile。
4. **BloomFilter 有假阳性**：不会漏，但会偶尔让你多查一次 HFile；默认 ROW 粒度够用。

## 自测

1. LSM-Tree 和 B+ 树的核心差异是什么？为什么 LSM 写性能好？
2. Flush 和 Compaction 分别解决什么问题？如果关掉自动 Major Compaction 会怎样？
3. BloomFilter 有假阳性没有假阴性，这对 HBase 读路径意味着什么？
4. 一条数据经历 3 次 Minor + 1 次 Major Compaction，它在磁盘上被「写」了几次？（写放大）

## 参考与官方文档

- [HBase 存储原理（Region/Store/HFile）](https://hbase.apache.org/2.5/book.html#regions.arch)
- [Compaction 指南](https://hbase.apache.org/2.5/book.html#compaction)
- [HFile 格式](https://hbase.apache.org/2.5/book.html#hfile)
- [LSM-Tree 论文](https://www.cs.umb.edu/~poneil/lsmtree.pdf)
