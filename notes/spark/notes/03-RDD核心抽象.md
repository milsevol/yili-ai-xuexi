# 03 RDD 核心抽象

## 一句话

**RDD（Resilient Distributed Dataset，弹性分布式数据集）**：一个只读的、分区的、带血缘的分布式对象集合——它是 Spark 的「元抽象」，DataFrame/SQL 底层最终都会被翻译成 RDD 操作。

> 日常开发 90% 用 DataFrame/SQL，但**不理解 RDD 就看不懂执行计划、调不了优、答不了面试**。本章建立的模型会贯穿后面所有章节。

## RDD 的五个特征（记住这张表）

| 特征 | 含义 | 推论 |
| --- | --- | --- |
| **分区的（Partitioned）** | 数据被切成 N 个分区，分散在集群各节点 | 分区数 = 并行度的上限 |
| **只读的（Immutable）** | 创建后不可变，只能经转换生成新 RDD | 天然适合重算与容错 |
| **惰性求值（Lazy）** | Transformation 只记录不算，Action 才触发 | 引擎能看到全图，才能全局优化 |
| **血缘（Lineage）** | 每个 RDD 记得自己从哪来（父 RDD + 转换） | 丢了不用备份，顺着血缘重算即可 |
| **可缓存（Cacheable）** | 可把计算结果物化到内存/磁盘 | 复用数据时避免重复计算 |

## 两类操作：Transformation 与 Action

| | Transformation（转换） | Action（行动） |
| --- | --- | --- |
| 返回什么 | 新 RDD | 值 / 写存储 |
| 何时执行 | 惰性，仅记录 | 立即触发整个 DAG 执行 |
| 例子 | `map` `filter` `flatMap` `join` `reduceByKey` `distinct` | `collect` `count` `take` `reduce` `foreach` `saveAsTextFile` |

```python
rdd = sc.textFile("logs/")            # T：读文件（此刻什么都没读！）
errors = rdd.filter(lambda l: "ERROR" in l)   # T：只是记录
count = errors.count()                # A：此刻才真正扫描全部文件
```

**为什么惰性是好设计**：因为引擎在 Action 触发时能看到完整的操作链，可以做流水线合并、消除冗余扫描。如果每步都立即执行，就失去了全局优化的机会。

## 窄依赖 vs 宽依赖（最重要的分水岭）

| | 窄依赖（Narrow） | 宽依赖（Wide / Shuffle） |
| --- | --- | --- |
| 父子分区关系 | 父分区 → 至多一个子分区 | 父分区 → 多个子分区（数据要跨网络搬家） |
| 算子例子 | `map` `filter` `union` | `groupByKey` `reduceByKey` `join`（未广播） `distinct` `repartition` |
| 执行方式 | 同一节点流水线执行（pipeline） | 必须 Shuffle：写盘 → 网络传输 → 拉取 |
| Stage 边界 | 不切 | **DAG 在此切分 Stage** |
| 容错代价 | 只重算丢失分区的流水线 | 可能要重算上溯多个分区 |

```
窄依赖： [p1]→map→[p1']→filter→[p1'']        一台机器一条龙
宽依赖： [p1]─┐
        [p2]─┼→ shuffle → [q1] [q2] [q3]     全网数据重新分发
        [p3]─┘
```

**工程启示**：Shuffle 是 Spark 作业最贵的操作（磁盘 + 网络 + 序列化），写代码时要有意识地「减少 Shuffle 次数、减少 Shuffle 数据量」。详见第 6 章。

## Key-Value 算子速查（Pair RDD）

PySpark 中形如 `(k, v)` 的二元组即 Pair RDD，拥有专属算子：

| 算子 | 作用 | 是否 Shuffle | 备注 |
| --- | --- | --- | --- |
| `reduceByKey(f)` | 按 key 聚合 | 是 | **map 端预聚合**，首选 |
| `groupByKey()` | 按 key 分组拿到全量 value 迭代器 | 是 | 不预聚合，数据量大时易爆内存，慎用 |
| `aggregateByKey(zero)(seq, comb)` | 带初始值的灵活聚合 | 是 | `reduceByKey` 的一般化 |
| `mapValues(f)` / `flatMapValues(f)` | 只动 value 不动 key | 否 | 保留分区信息，优于先 map 拆元组 |
| `sortByKey()` | 按 key 排序 | 是 | 全局有序 |
| `join(other)` / `leftOuterJoin` / `cogroup` | 双 RDD 连接 | 是 | 大表 join 大表前先想能否广播 |
| `partitionBy(n, hash)` | 指定分区器 | 是（如已相同则否） | 后续同 key 操作可免 Shuffle |

`reduceByKey` vs `groupByKey` 是万年面试题：**前者在 map 端先合并（combine），网络只传合并后的结果；后者全量搬运**。同理，DataFrame 层的 `groupBy().agg()` 也自动做预聚合。

## 容错机制：血缘重算

节点挂了，RDD 分区丢了怎么办？——**不靠复制，靠血缘（lineage）重算**：

```
textFile → map → filter → reduceByKey
             ↑ 某分区丢失时，只需从 textFile 的对应分区起，
               沿血缘重新执行 map/filter 即可恢复
```

- 窄依赖恢复：只重算丢失分区，代价小。
- 宽依赖恢复：可能要重算 Shuffle 上游多个分区，代价大。
- 这也是为什么 **cache/checkpoint 用得好能同时加速与保平安**（见下节）。

## cache / persist / checkpoint：三个「保存」别混淆

| | `cache()` | `persist(level)` | `checkpoint()` |
| --- | --- | --- | --- |
| 本质 | `persist(MEMORY_ONLY)` 的简写 | 可选存储级别 | 物化到可靠存储（HDFS）并**切断血缘** |
| 触发时机 | 下一个 Action 时物化 | 同左 | 需 Action 触发；通常先 cache 再 checkpoint |
| 目的 | 复用加速 | 复用加速（内存放不下可溢写磁盘） | 长链路容错 + 斩断过长血缘（防栈溢出/重算风暴） |
| 存储级别 | 内存 | MEMORY_ONLY / MEMORY_AND_DISK / SER / DISK_ONLY… | 可靠文件系统 |

常用级别速查：

| 级别 | 含义 | 适用 |
| --- | --- | --- |
| `MEMORY_ONLY` | 默认；放不下就不存（用到时重算） | 数据小、重算便宜 |
| `MEMORY_AND_DISK` | 内存放不下溢写磁盘 | **最常用兜底** |
| `MEMORY_ONLY_SER` | 序列化后存内存，省空间费 CPU | 内存紧张、CPU 富裕 |

```python
df = spark.read.parquet("s3://big/").filter(...)
df.cache()          # 或 df.persist(StorageLevel.MEMORY_AND_DISK)
df.count()          # 第一次 Action：真正计算并物化
df.groupBy("k").count().show()   # 第二次起：直接读缓存，快
df.unpersist()      # 用完记得释放
```

**什么时候值得 cache**：同一个 DF/RDD 被 **≥2 个 Action** 使用，且计算成本不低。只算一次就丢的数据不要 cache，纯属浪费内存。

## 创建 RDD 与分区控制

```python
sc = spark.sparkContext

rdd1 = sc.parallelize(range(1000), numSlices=8)   # 内存集合 → 8 分区
rdd2 = sc.textFile("hdfs:///data/logs/")          # 分区数 ≈ HDFS block 数
rdd3 = rdd1.repartition(16)     # 重新分区（Shuffle，可增可减）
rdd4 = rdd1.coalesce(2)         # 合并分区（尽量不 Shuffle，只能减）
```

| 操作 | Shuffle | 分区数 | 典型用途 |
| --- | --- | --- | --- |
| `repartition(n)` | 是 | 可增可减 | 提高并行度；写出前均匀打散 |
| `coalesce(n)` | 默认否 | 只能减 | 过滤后分区过多、小文件合并 |

## 闭包与序列化（PySpark 踩坑高发区）

Executor 执行 Task 时，Driver 会把「算子里的函数 + 它引用的外部变量」序列化发送到远端。因此：

1. **函数里引用的 Driver 变量会被拷贝**到 Executor，且各 Task 各持一份——修改互不可见（想聚合用累加器/共享变量，见第 4、6 章广播）。
2. 不可序列化的对象（如数据库连接、锁）不能直接闭包引用，要在 `mapPartitions` 内**按分区**初始化：

```python
def write_partition(rows):
    import pymysql
    conn = pymysql.connect(...)          # 每个分区建一次连接，而非每行
    try:
        for r in rows:
            ...                          # 批量写入
    finally:
        conn.close()

result_rdd.foreachPartition(write_partition)
```

3. `mapPartitions(f)` 按分区调用一次而非每行一次，是**减少初始化开销**的利器。

## 什么时候才需要写 RDD

| 场景 | 建议 |
| --- | --- |
| 结构化/半结构化数据，SQL 能表达 | 用 DataFrame/SQL（快、优化器加持） |
| 非结构化数据、自定义分区逻辑、精细控制 | 用 RDD |
| 需要与老的 RDD API 库对接（部分 MLlib 老接口） | 用 RDD |

原则：**能 DataFrame 不 RDD**——Catalyst 优化 + Tungsten 内存管理通常让 DataFrame 快 2~5 倍。但脑子里要始终有 RDD 模型。

## 自测

1. 为什么 RDD 设计成「只读 + 血缘」而不是「可变 + 副本」？各自代价是什么？
2. `repartition(200)` 和 `coalesce(3)` 在 Shuffle、分区方向上的差异？
3. 一段代码先 `df.cache()` 后只有一个 `df.count()`，这个 cache 有意义吗？
4. 为什么 `groupByKey().mapValues(sum)` 通常应该改写成 `reduceByKey`？

## 参考与官方文档

- [RDD Programming Guide](https://spark.apache.org/docs/latest/rdd-programming-guide.html)
- [RDD 论文（NSDI'12）](https://www.usenix.org/system/files/conference/nsdi12/nsdi12-final138.pdf)
- [StorageLevel 源码注释](https://spark.apache.org/docs/latest/api/python/reference/api/pyspark.StorageLevel.html)
