# 09 Structured Streaming

## 一句话

**Structured Streaming = 把流数据当成「一张无限增长的表」**：你用批处理同一套 DataFrame/SQL 写法写流任务，引擎负责增量执行、容错、状态管理——**流批一体**是 Spark 流处理的核心理念。

> 老的 DStream（Spark Streaming）已被标记过时，新项目直接用 Structured Streaming。

## 编程模型：无界表

```
Kafka 消息 ──→ 无界输入表（不断追加新行）
                  │
                  ▼  你的查询（和批处理一样的 SQL）
              结果表（每个触发周期增量更新）
                  │
                  ▼
              Sink（Kafka / Parquet / Console / 自定义）
```

**关键理解**：你写的 `groupBy("word").count()` 对无界表同样成立——每来一批新数据，就增量更新计数结果。

## 最小可运行示例（本地 5 行跑通）

```python
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = (SparkSession.builder.master("local[*]")
         .appName("ch09")
         .config("spark.sql.shuffle.partitions", "4")   # 本地测试调小
         .getOrCreate())

# 用 rate source 造数据（内置测试源，每秒生成行）
df = (spark.readStream.format("rate")
      .option("rowsPerSecond", 10)
      .load())

result = df.groupBy(F.window("timestamp", "10 seconds")).count()

query = (result.writeStream
         .outputMode("complete")        # 全量输出结果表
         .format("console")             # 打印到控制台
         .option("truncate", False)
         .start())

query.awaitTermination(30)              # 30 秒后停（生产用 awaitTermination()）
```

跑起来你会看到每 10 秒一个窗口的计数结果不断输出。

## 三大概念：Trigger、Output Mode、Watermark

| 概念 | 作用 | 可选值 |
| --- | --- | --- |
| **Trigger**（触发器） | 多久算一次 | 默认微批（尽快）、`processingTime="10 seconds"`、`once=True`（一次性跑完）、`availableNow`（3.2+，跑完存量就停） |
| **Output Mode**（输出模式） | 结果表怎么写给 Sink | `append`（只增不改，默认）、`complete`（全量）、`update`（只更新变化行） |
| **Watermark**（水位线） | 容忍多久的乱序/迟到数据 | `withWatermark("ts", "10 minutes")`，配合窗口控制状态过期 |

**Output Mode 与查询类型的匹配**（易错）：

| 查询类型 | append | update | complete |
| --- | --- | --- | --- |
| 无聚合（map/filter） | ✅ 默认 | — | — |
| 聚合 + watermark + 事件时间窗口 | ✅ | ✅ | ✅ |
| 聚合但无 watermark | ❌ 不允许 | ✅ | ✅ |

`append` 要求「结果一旦写出就不再变」，所以无 watermark 的无限聚合不能用 append（结果永远在变）。

## 窗口与 Watermark（流处理核心）

```python
from pyspark.sql.functions import window

result = (df.withWatermark("event_time", "10 minutes")   # 容忍 10 分钟乱序
            .groupBy(window("event_time", "5 minutes"), "device")
            .count())
```

| 窗口类型 | 写法 | 说明 |
| --- | --- | --- |
| 滚动窗口（Tumbling） | `window("ts", "5 minutes")` | 不重叠，5 分钟一段 |
| 滑动窗口（Sliding） | `window("ts", "10 minutes", "5 minutes")` | 10 分钟窗，每 5 分钟滑一次 |
| 会话窗口（Session） | `session_window("ts", "30 minutes")` | 30 分钟无活动则关闭会话 |

**Watermark 的三重作用**：

1. **决定窗口何时输出**：watermark 超过窗口结束时间才输出（保证迟到数据已等到）。
2. **决定状态何时清理**：旧窗口状态占内存，watermark 过了就丢弃。
3. **与 append 模式配合**：保证输出后不再更新。

**迟到数据的处理**：watermark 内 → 更新对应窗口；超过 watermark → 直接丢弃（除非配 `allowedLateness`）。

## 状态管理（Stateful Operations）

Spark 自动管理以下算子的状态：

| 算子 | 状态内容 | 注意事项 |
| --- | --- | --- |
| 聚合（count/sum/avg） | 各 key 的中间聚合值 | 状态随 key 增长，需 watermark 或定期清理 |
| `dropDuplicates` | 去重 key 的集合 | 无 watermark 会无限膨胀，必须配 watermark |
| `mapGroupsWithState` / `flatMapGroupsWithState` | 自定义状态 | 灵活但复杂，Scala API 更完整 |
| 流流 Join | 两侧按 key 缓存 | 必须配 watermark + 时间范围条件，否则状态爆炸 |

**状态存储**：默认 HDFS 兼容的 State Store（RocksDB 可选，大状态推荐）。

```python
spark.conf.set("spark.sql.streaming.stateStore.providerClass",
               "org.apache.spark.sql.execution.streaming.state.RocksDBStateStoreProvider")
```

## Source 与 Sink 速查

### Source（输入）

| Source | 生产可用 | 说明 |
| --- | --- | --- |
| **Kafka** | ✅ | 主流；`readStream.format("kafka")` |
| **文件**（Parquet/JSON/CSV…） | ✅ | 监控目录，新文件触发； exactly-once |
| **rate** | 测试 | 固定速率生成行 |
| Socket | ❌ 仅测试 | 无容错，勿生产 |

Kafka 读取示例：

```python
df = (spark.readStream.format("kafka")
      .option("kafka.bootstrap.servers", "broker1:9092,broker2:9092")
      .option("subscribe", "orders")
      .option("startingOffsets", "latest")        # earliest / latest / JSON 指定
      .load()
      .selectExpr("CAST(key AS STRING)", "CAST(value AS STRING) as json")
      .select(F.col("key"), F.from_json("json", schema).alias("d"))
      .select("key", "d.*"))
```

### Sink（输出）

| Sink | 容错级别 | 说明 |
| --- | --- | --- |
| **Kafka** | at-least-once（配合幂等生产者可 exactly-once） | 主流 |
| **文件**（Parquet/Delta…） | exactly-once | 带 `_spark_metadata` 日志 |
| **foreachBatch** | 取决于你的实现 | **最灵活**，每批微批数据当批 DataFrame 处理 |
| console / memory | 测试 | 勿生产 |

foreachBatch 写 MySQL/Redis 等外部系统：

```python
def write_to_mysql(batch_df, batch_id):
    (batch_df.write.format("jdbc")
             .option("url", "jdbc:mysql://host/db")
             .option("dbtable", "realtime_cnt")
             .mode("append").save())

query = (result.writeStream
         .foreachBatch(write_to_mysql)
         .option("checkpointLocation", "hdfs:///checkpoints/orders_cnt")  # 必须
         .start())
```

## 容错：Checkpoint 与 Exactly-Once

```python
.option("checkpointLocation", "hdfs:///checkpoints/my_query")
```

Checkpoint 目录存三样东西：

1. **偏移量（offsets）**：当前读到哪了（Kafka offset / 文件列表）
2. **状态（state）**：聚合中间结果
3. **元数据**：查询配置、Schema

**Exactly-Once 的条件**：Source 可重放（Kafka/文件 ✅）+ Sink 幂等或事务（文件 ✅、Kafka 幂等生产者 ✅、foreachBatch 需自己保证）。

> 常见误区：以为开了 Checkpoint 就 exactly-once。**foreachBatch 里用 `mode("append")` 写 MySQL 是 at-least-once**——批失败重试会重复写。要 exactly-once 需用主键去重或事务。

## 流批一体：一份代码两种跑法

```python
def process(df):
    return (df.filter(F.col("status") == "pay")
              .groupBy("channel").agg(F.sum("amount").alias("gmv")))

# 批跑
batch_df = spark.read.parquet("s3://dwd/orders/dt=2026-10-31/")
process(batch_df).write.parquet("s3://dm/channel_gmv/")

# 流跑
stream_df = spark.readStream.format("kafka")...
process(stream_df).writeStream.format("console").start()
```

这就是 Structured Streaming 的精髓：**业务逻辑不感知流批**，只是输入输出不同。

## 生产部署注意

| 事项 | 建议 |
| --- | --- |
| 部署模式 | cluster 模式，Driver 挂掉由集群重启 |
| Checkpoint | 放 HDFS/S3，勿放本地磁盘 |
| 背压（Backpressure） | `spark.sql.streaming.kafka.maxOffsetsPerTrigger` 限流，防启动时积压冲垮 |
| 监控 | StreamingQueryListener 采集 lag/延迟；或 Prometheus + Grafana |
| 升级 | 停 → 改代码 → 同 checkpoint 重启（兼容性见官方文档，状态 Schema 变更需谨慎） |

## 自测

1. 为什么「无 watermark 的聚合查询」不能用 `append` 输出模式？
2. Watermark 设为 10 分钟，一条事件时间 9:50 的数据在 10:05 到达，会被处理吗？10:15 到达呢？
3. `foreachBatch` 写 MySQL 时，怎么设计才能接近 exactly-once？
4. 流流 Join 为什么必须配 watermark 和时间范围条件？
5. `trigger(once=True)` 和 `trigger(availableNow=True)` 的差异？

## 参考与官方文档

- [Structured Streaming 编程指南](https://spark.apache.org/docs/latest/structured-streaming-programming-guide.html)
- [Kafka 集成指南](https://spark.apache.org/docs/latest/structured-streaming-kafka-integration.html)
- [Databricks：流处理状态管理](https://docs.databricks.com/en/structured-streaming/stateful-streaming.html)
