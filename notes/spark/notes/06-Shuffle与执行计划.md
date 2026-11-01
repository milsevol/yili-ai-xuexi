# 06 Shuffle 与执行计划

## 一句话

**Shuffle = 跨节点按 key 重新分发数据**：它是 Spark 作业里最贵的操作（磁盘 IO + 网络 IO + 序列化），Stage 的分界线、性能的瓶颈点、数据倾斜的事故现场，全都围绕着它。

> 第 3 章讲了宽窄依赖的「概念」，本章讲 Shuffle 的「过程」和「怎么观测、怎么减少」。

## Shuffle 全过程拆解

以 `reduceByKey` 为例，200 → 100 分区的 Shuffle：

```
── Stage 1（Map 侧 / Shuffle Write）──────────────
分区1 → [map/combine] → 按 key 的 hash 分桶 → 写本地磁盘(spill) 
分区2 → [map/combine] → 按 key 的 hash 分桶 → 写本地磁盘(spill)
  ...
── Stage 边界 ────────────────────────────────
── Stage 2（Reduce 侧 / Shuffle Read）────────────
分区1 → 从所有上游分区拉属于自己的数据 → 排序/合并 → 聚合
分区2 → ...
```

| 阶段 | 做什么 | 代价 |
| --- | --- | --- |
| **Shuffle Write**（Map 侧） | 内存缓冲 → 溢写磁盘（spill）→ 归并成（数据文件 + 索引文件） | 磁盘 IO、序列化 |
| **数据传输** | Reduce Task 通过网络向各节点拉取属于自己的分片 | 网络 IO，节点越多越剧烈 |
| **Shuffle Read**（Reduce 侧） | 拉取 → （需要时）排序 → 聚合 | 内存压力大时也会 spill 磁盘 |

现代 Spark（≥2.0）统一使用 **Sort-Based Shuffle**：Map 侧按分区 id 排序写文件。`spark.shuffle.manager` 无需再配。

## 哪些算子触发 Shuffle（建立直觉）

| 触发 Shuffle | 不触发（窄依赖） |
| --- | --- |
| `groupBy` / `distinct` / `dropDuplicates` | `select` / `filter` / `withColumn` |
| `join`（未广播）/ `cogroup` | `map` / `flatMap` / `mapValues` |
| `orderBy` / `sort` / `sortBy`（全局排序） | `sortWithinPartitions`（仅区内排序） |
| `repartition(n)` / `partitionBy` | `coalesce`（默认） |
| 窗口函数（partition by 跨分区） | — |

## Shuffle 后分区数：最重要的一个参数

```python
spark.conf.set("spark.sql.shuffle.partitions", 200)   # 默认 200
```

- **Shuffle 后 Stage 的 Task 数 = 该值**。200 个 Task 算 10GB 数据 → 每 Task 50MB，合理。
- 数据量大（百 GB+）而保持 200 → 单 Task 处理数 GB → 慢 + 易 OOM/spill。
- 数据量小（几百 MB）而保持 200 → 200 个几 MB 的 Task → 调度开销 + 大量小文件。
- **经验值**：单 Task 处理 100~200MB 比较健康；开 AQE 后由它自动调，见下节。

## AQE（Adaptive Query Execution，3.x 默认开启）

AQE 让 Spark **在运行时根据实际 Shuffle 数据统计量调整计划**，三大能力：

```python
spark.conf.set("spark.sql.adaptive.enabled", True)                          # 3.2+ 默认 true
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", True)                 # 倾斜 Join 自动拆分
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", True)       # 自动合并小分区
spark.conf.set("spark.sql.adaptive.localShuffleReader.enabled", True)       # 减少拉取开销
```

| 能力 | 解决什么 | 效果 |
| --- | --- | --- |
| **自动合并 Shuffle 分区** | 固定 200 分区但数据量小 | 运行时把小分区合并，减少 Task 与小文件 |
| **Join 策略动态切换** | 统计信息不准，原计划 SMJ | 发现某侧实际很小 → 动态改成广播 Join |
| **倾斜 Join 自动拆分** | 个别 key 占 90% 数据 | 把倾斜分区拆成多份并行处理 |

> AQE 不是万能的：极端倾斜（单 key 数亿行）、UDF 阻塞、写盘阶段的小文件，仍需人工处理（第 8 章）。

## Join 策略全解析（面试 + 调优双重高频）

物理层三种主要 Join：

| 策略 | 原理 | 触发条件 | Shuffle | 适用 |
| --- | --- | --- | --- | --- |
| **Broadcast Hash Join** | 小表全量发到每个 Executor，与大表各分区本地 join | 一侧 ≤ `spark.sql.autoBroadcastJoinThreshold`（默认 10MB） | **无** | 大表 × 小表（维度表），首选 |
| **Sort Merge Join** | 双侧 Shuffle 到同 key 同分区 → 排序 → 归并 | 默认兜底策略 | 双侧各一次 | 大表 × 大表 |
| **Shuffled Hash Join** | 小侧按分区建 hash 表，避免排序 | 满足 `preferSortMergeJoin=false` 等条件 | 有 | 特定场景，较少见 |

```python
# 手动强制广播（小表 >10MB 但仍远小于大表时）
from pyspark.sql.functions import broadcast
big.join(broadcast(small), "id")

# 手动调高自动广播阈值（比如确认小表 200MB 且 Executor 内存够）
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", 200 * 1024 * 1024)
```

**Broadcast 注意事项**：

- 广播表是整体进每个 Executor 内存的，过大 → OOM（常见报错 `OutOfMemoryError: Java heap space` 于广播时）。
- 广播超时：`spark.sql.broadcastTimeout`（默认 300s），大表广播慢可调大。
- 判断是否真的广播了：`explain` 里看到 `BroadcastHashJoin` + `BroadcastExchange` 字样。

## 用 explain 识别 Shuffle 与 Join 选择

```python
big.join(small, "id").explain()
```

```
== Physical Plan ==
AdaptiveSparkPlan isFinalPlan=true       ← AQE 已产出最终计划
+- BroadcastHashJoin [id#10], [id#20], Inner, BuildRight    ← 广播 Hash Join
   :- FileScan parquet big[...]
   +- BroadcastExchange HashedRelationBroadcastMode(...)     ← 小表被广播
      +- FileScan parquet small[...]
```

若看到 `SortMergeJoin` 而你认为一侧是小表 → 检查统计信息、阈值、AQE 是否生效。

## Shuffle 的性能账单与优化清单

Shuffle 贵在哪：

1. **序列化/反序列化**：对象 → 字节 → 网络 → 字节 → 对象，全程 CPU 密集。
2. **磁盘 spill**：内存缓冲不够时反复溢写。
3. **网络**：全互联传输（all-to-all），集群规模越大越明显。
4. **文件句柄与元数据**：M 个 map × R 个 reduce 的中间分片管理。

优化清单（按优先级）：

| 手段 | 说明 |
| --- | --- |
| **减少 Shuffle 次数** | 多个聚合合并写；能 map 端做的别留到 reduce |
| **减少 Shuffle 数据量** | Shuffle 前先 `filter`、先列裁剪；`reduceByKey` 替代 `groupByKey`（预聚合） |
| **广播替代 Shuffle** | 小表 join 走 Broadcast，直接消灭一侧 Shuffle |
| **合理分区数** | 开 AQE；或手动调 `spark.sql.shuffle.partitions` |
| **调节 Shuffle 缓冲** | `spark.shuffle.file.buffer`、`spark.reducer.maxSizeInFlight` |
| **Kryo 序列化** | `spark.serializer=KryoSerializer`（Shuffle 默认用 Java 序列化，Kryo 快 10x） |
| **外排服务（ESS）** | YARN/K8s 开 `spark.shuffle.service.enabled`，配合动态资源不丢 Shuffle 数据 |

## 一个完整观测流程（把本章串起来）

```python
df = (spark.read.parquet("big/")
      .filter(F.col("dt") == "2026-10-31")     # ① 先过滤，缩小 Shuffle 量
      .select("uid", "gid", "amt")              # ② 列裁剪
      .groupBy("gid").agg(F.sum("amt").alias("s")))  # ③ 预聚合聚合（两阶段）

df.explain()   # 看 Exchange 次数、PushedFilters
df.write.parquet("out/")
# 运行后打开 UI：
# - Stages → 看 Shuffle Read/Write 总量是否符合预期（应远小于原始数据量）
# - Tasks  → 看耗时分布是否均匀（不均 = 倾斜，见第 8 章）
```

## 自测

1. 为什么 `reduceByKey` 的 Shuffle 数据量通常小于 `groupByKey`？机制上差在哪？
2. `spark.sql.shuffle.partitions` 设置过大、过小分别有什么症状？
3. AQE 的三大能力分别解决什么问题？哪类问题 AQE 解决不了？
4. 大表 join 大表，但你知道其中一张表当天分区只有 5MB，最优写法是什么？
5. Shuffle Write 和 Shuffle Read 各自发生在哪个 Stage 的哪一侧？

## 参考与官方文档

- [Spark SQL Performance Tuning（含 AQE 参数）](https://spark.apache.org/docs/latest/sql-performance-tuning.html)
- [Configuration：Shuffle Behavior](https://spark.apache.org/docs/latest/configuration.html#shuffle-behavior)
- [Databricks：AQE 介绍](https://www.databricks.com/blog/2020/05/29/adaptive-query-execution-speeding-up-spark-sql-at-runtime.html)
