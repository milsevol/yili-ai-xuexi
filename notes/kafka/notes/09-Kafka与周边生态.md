# 09 Kafka 与周边生态

## 一句话

Kafka 在大数据链路中的角色是**缓冲与解耦层**：上游埋点/日志/DB binlog 汇聚到 Kafka，下游可以是 Flink 实时算、Spark 离线批、Connect 同步到 HDFS/ES/HBase/... 任一种都不影响上游。

## 大数据链路中的位置

```
            ┌─────────────────────────────────────┐
            │              数据源                   │
            │  埋点 SDK / 日志 / DB binlog / IoT    │
            └──────────────┬──────────────────────┘
                           ↓
            ┌─────────────────────────────────────┐
            │            Kafka（入口）              │
            │  ├─ 缓冲洪峰                          │
            │  ├─ 解耦上下游                        │
            │  ├─ 多订阅：一个 Topic 多个 Consumer Group │
            │  └─ 持久化：随时回放                   │
            └───────┬──────────┬──────────┬────────┘
                    ↓          ↓          ↓
              ┌─────────┐ ┌────────┐ ┌──────────────┐
              │  Flink   │ │ Spark  │ │ Kafka Connect │
              │ 实时流   │ │ Struct.│ │ Source/Sink  │
              │          │ │Stream. │ │              │
              └─────┬───┘ └───┬────┘ └──────┬───────┘
                    ↓         ↓              ↓
              ┌─────────────────────────────────────┐
              │       落地存储                       │
              │  HDFS / HBase / ES / S3 / OLAP      │
              └─────────────────────────────────────┘
```

### 三种典型链路

1. **实时链路**：埋点 → Kafka → Flink → ClickHouse/Doris（实时 OLAP）
2. **离线链路**：DB binlog → Kafka → Kafka Connect S3 Connector → Hive/Spark 批处理
3. **CDC 链路**：MySQL binlog → Debezium（Kafka Connect Source）→ Kafka → 多端（ES 建索引 + HBase 同步 + Flink 计算）

## Spark Streaming vs Flink 消费 Kafka

### Spark Streaming（老，DStream）

```scala
val stream = KafkaUtils.createDirectStream[String, String](
  streamingContext,
  LocationStrategies.PreferConsistent,
  ConsumerStrategies.Subscribe[String, String](topics, kafkaParams))
```

- 微批（默认 1 秒一个 batch），每个 batch 从 Kafka 拉一段时间窗口的数据
- 背压机制：Spark 1.5+ 支持动态调整拉取速率
- 适用：低延迟秒级、已有 Spark 技术栈的团队

### Spark Structured Streaming（推荐，统一 API）

```scala
val df = spark.readStream
  .format("kafka")
  .option("kafka.bootstrap.servers", "kafka1:9092")
  .option("subscribe", "demo")
  .load()

df.writeStream.format("parquet").outputMode("append")
  .trigger(Trigger.ProcessingTime("1 minute"))
  .option("path", "/data/structured-demo")
  .option("checkpointLocation", "/chkpt")
  .start()
```

- DataFrame API，批流统一
- Exactly-Once 语义 + Checkpoint 持久化
- **Consumer Lag 由 Spark 管理**，不走 Kafka Consumer Group（checkpoint 里存 offset）

### Flink Kafka Source（主流，实时）

```java
FlinkKafkaConsumer<String> source = new FlinkKafkaConsumer<>(
    "demo",
    new SimpleStringSchema(),
    properties);
source.setStartFromGroupOffsets();
source.setCommitOffsetsOnCheckpoints(true);

DataStream<String> stream = env.addSource(source);
```

- 真正的流（不是微批），延迟毫秒级
- Checkpoint + 两阶段提交 Exactly-Once
- **Flink 和 Kafka Consumer Group 配合**：Checkpoint 时 commit offset 到 Broker 的 `__consumer_offsets`

### 三者对比

| 维度 | Spark Streaming | Spark Structured Streaming | Flink |
| --- | --- | --- | --- |
| 模型 | 微批 DStream | 结构化 DataFrame | 真正的 DataStream + SQL |
| 延迟 | 秒级 | 秒级-分钟级（trigger 可调） | 毫秒级 |
| Exactly-Once | 依赖 checkpoint | ✅ Checkpoint | ✅ Checkpoint + 2PC |
| Kafka 集成 | DirectStream | readStream.format("kafka") | FlinkKafkaConsumer |
| Offset 存储 | checkpoint（不走 Consumer Group） | checkpoint | Checkpoint + __consumer_offsets |
| 状态存储 | 内存 + checkpoint | checkpoint | Managed Memory + RocksDB |
| 适用场景 | 老项目维护 | 批流数仓 | 实时流处理主流 |

## Kafka Connect CDC 实战

### Debezium MySQL CDC 配置

```json
{
  "name": "mysql-source",
  "config": {
    "connector.class": "io.debezium.connector.mysql.MySqlConnector",
    "database.hostname": "mysql-master",
    "database.port": "3306",
    "database.user": "debezium",
    "database.password": "xxx",
    "database.server.name": "mydb",
    "database.include.list": "order_db",
    "table.include.list": "order_db.orders,order_db.items",
    "database.history.kafka.bootstrap.servers": "kafka1:9092",
    "database.history.kafka.topic": "schema-changes",
    "snapshot.mode": "initial",
    "include.schema.changes": "true"
  }
}
```

### 数据流向

```
MySQL binlog
    ↓ (Debezium Source)
Kafka Topic: mydb.order_db.orders
    ↓
├─ Flink → 实时聚合/风控
├─ Elasticsearch Connector → 建检索索引
├─ S3/HDFS Connector → 冷备
└─ Kafka Streams → 状态化计算
```

**CDC 要点**：
- MySQL 要开 binlog（ROW 格式 + 全量）
- 首次启动走 snapshot（全量） + 后续 binlog（增量）
- Topic 命名规则：`<server.name>.<database>.<table>`
- 每条消息是 JSON（或 Avro）格式的 CDC Event：op + before + after + ts

## Kafka vs Pulsar vs RocketMQ 选型

| 维度 | Kafka | Pulsar | RocketMQ |
| --- | --- | --- | --- |
| 架构 | Broker 存日志文件 | Broker 无状态 + BookKeeper 存数据 | Broker + NameServer |
| 部署 | 简单（KRaft 模式） | 复杂（Broker + BookKeeper + ZK） | 简单 |
| 吞吐 | ~百万/s | ~百万/s | ~十万/s |
| 跨地域 | 需要 MirrorMaker | 原生支持（Geo-Replication） | 原生支持 |
| 存储隔离 | Partition 写 Broker 本地 | BookKeeper 分布式存储 | Broker 本地 |
| 动态扩缩 | Partition 重分配 | Broker 无状态，直接加机器 | 加 Broker，自动 Rebalance |
| 事务 | 3.0+ EOS v2 | ✅ | ✅ 半消息 |
| 顺序 | 单 Partition | 单 Partition | 单 Queue |
| 适用 | 大数据流处理、日志、CDC | 多租户、多集群、流存储 | 业务消息 + 大数据 |

### 选型决策

```
跨地域 / 多集群 / 流存储      →  Pulsar
大数据主流生态 / Flink/Spark  →  Kafka（首选）
业务消息 + 大数据兼顾 / 阿里系 →  RocketMQ
```

## Kafka 在云原生中的位置

- **Kafka on K8s**：Strimzi / Operator 把 Broker + Controller 容器化，StatefulSet 保证稳定网络标识，PersistentVolume 挂存储
- **Serverless Kafka**：AWS MSK / Azure Event Hubs / Aliyun RocketMQ Serverless，不用运维 Broker
- **流存储统一**：云原生数据湖（Iceberg/Hudi）+ Kafka 作为实时入口

## 自测

1. 描述 Flink 消费 Kafka 的链路，Checkpoint 和 offset commit 怎么配合？
2. Debezium CDC 的数据流向是什么？MySQL 侧需要开启什么配置？
3. Kafka 和 Pulsar 架构的核心差异是什么？分别适合什么场景？
4. Spark Structured Streaming 消费 Kafka 时 offset 存在哪里？

## 参考与官方文档

- [Apache Flink Kafka Connector](https://nightlies.apache.org/flink/flink-docs-stable/docs/connectors/datastream/kafka/)
- [Spark Structured Streaming + Kafka](https://spark.apache.org/docs/latest/structured-streaming-kafka-integration.html)
- [Debezium 文档](https://debezium.io/documentation/reference/stable/)
- [Apache Pulsar 官网](https://pulsar.apache.org/)
