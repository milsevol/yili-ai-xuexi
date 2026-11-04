# 07 Flink SQL 与 Table API

## 一句话

**Flink SQL / Table API** 是 Flink 官方主推的**声明式 API**——用 SQL 写流处理，Flink 自动生成最优的执行计划；它和 DataStream 可以互转（`fromDataStream` / `toDataStream`）；**CDC（Change Data Capture）入湖**是它最炸裂的场景：直接读 MySQL/PG Binlog，实时写入 Iceberg/Hudi/Delta 湖仓表，自动处理 Schema 变更、分桶、Compaction。

## Flink SQL vs DataStream

| 维度 | Flink SQL / Table API | DataStream API |
| --- | --- | --- |
| 声明方式 | 声明式（What） | 命令式（How） |
| 上手门槛 | 有 SQL 基础就行 | 需要理解算子链、状态、Timer |
| 优化 | 内置优化器（Catalan/Calcite），自动谓词下推、列裁剪、Join 重排 | 自己写逻辑 |
| 功能覆盖 | 绝大多数场景（聚合、Join、窗口、CDC、入湖） | 极端场景（自定义 Trigger、复杂 ProcessFunction、异步 IO） |
| 状态管理 | 自动 | 手动声明 StateDescriptor |
| Schema 管理 | 有 Catalog、Table 元数据 | 无 |

> **生产原则**：能用 Flink SQL 就不用 DataStream。只有 SQL 表达不了（复杂 Timer、自定义 Trigger、异步 IO）才回 DataStream。

## Table API 基础

```java
StreamTableEnvironment tableEnv = StreamTableEnvironment.create(env);

// 从 DataStream 创建 Table
DataStream<Order> ordersDS = env.fromSource(kafkaSource, ...);
Table orders = tableEnv.fromDataStream(ordersDS);

// 写 SQL
Table result = tableEnv.sqlQuery("""
    SELECT user_id, SUM(amount) AS total
    FROM orders
    GROUP BY user_id, TUMBLE(ts, INTERVAL '10' MINUTE)
""");

// 转回 DataStream
DataStream<Row> resultDS = tableEnv.toDataStream(result);
resultDS.addSink(...);
```

## Catalog / Table / Connector 三件套

Flink SQL 的核心是 **Catalog（元数据仓库）+ Table（表定义）+ Connector（连接器实现）**：

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│   Catalog    │──▶│    Table     │──▶│  Connector   │
│ (元数据存储)   │   │ (Schema 定义) │   │ (实际读写)     │
└──────────────┘   └──────────────┘   └──────────────┘
                        │
                   CREATE TABLE xxx (...)
                   WITH ('connector' = 'kafka', ...)
```

### Catalog 类型

| Catalog | 用途 | 场景 |
| --- | --- | --- |
| **GenericInMemoryCatalog** | 内存 Catalog（默认） | 本地调试 |
| **HiveCatalog** | 读写 Hive Metastore | 接入现有 Hive 数仓；Flink SQL 直接查 Hive 表 |
| **IcebergCatalog** | Iceberg 元数据 | 湖仓表管理 |
| **JDBC Catalog** | 从 MySQL 等读元数据 | 直接把关系库当表用（CDC Source） |

### 连接器一览

| Connector | 方向 | 说明 |
| --- | --- | --- |
| Kafka | Source / Sink | 最常用；支持 Exactly-Once |
| MySQL CDC | Source | 读 Binlog，支持全量 + 增量 |
| PostgreSQL CDC | Source | 读 WAL |
| Oracle CDC | Source | 读 Redo Log |
| Iceberg | Source / Sink | 湖仓表；支持分桶、Compaction |
| Hudi | Source / Sink | 湖仓表；支持 UPSERT |
| Delta Lake | Source / Sink | 湖仓表 |
| HBase | Source / Sink | 维表 Join、CDC 写入 |
| Doris | Source / Sink | OLAP Sink，实时入湖 |
| JDBC | Source / Sink | 关系库批读写 |
| filesystem | Source / Sink | 文件系统（CSV/Parquet/ORC） |

## CDC：Flink 最强大的场景

**CDC（Change Data Capture）= 变化数据捕获**：不侵入业务代码，直接读数据库的 Binlog/WAL，把变化实时同步到下游。

### MySQL Binlog → Iceberg 入湖

```sql
-- 1. MySQL CDC Source 表
CREATE TABLE mysql_orders (
    order_id   BIGINT,
    user_id    BIGINT,
    amount     DECIMAL(10,2),
    create_time TIMESTAMP(3) METADATA FROM 'source.timestamp',
    PRIMARY KEY (order_id) NOT ENFORCED
) WITH (
    'connector'  = 'mysql-cdc',
    'hostname'    = 'mysql-host',
    'port'        = '3306',
    'database-name' = 'shop',
    'table-name'  = 'orders',
    'username'    = 'cdc_user',
    'password'    = '***',
    'scan.startup.mode' = 'initial',   -- initial / latest-offset / specific-offset
    'scan.incremental.snapshot.enabled' = 'true'
);

-- 2. Iceberg Sink 表
CREATE TABLE iceberg_orders (
    order_id   BIGINT,
    user_id    BIGINT,
    amount     DECIMAL(10,2),
    create_time TIMESTAMP(3),
    PRIMARY KEY (order_id) NOT ENFORCED
) WITH (
    'connector' = 'iceberg',
    'catalog'   = 'iceberg_catalog',
    'database'  = 'ods',
    'table'     = 'orders',
    'write-mode' = 'upsert',       -- upsert / append
    'format-version' = '2'
);

-- 3. 同步：一条 SQL 搞定
INSERT INTO iceberg_orders
SELECT order_id, user_id, amount, create_time
FROM mysql_orders;
```

### CDC 的核心特性

| 特性 | 说明 |
| --- | --- |
| **全量 + 增量** | `scan.startup.mode=initial`：先做一致性快照，再切 Binlog；无锁或低锁 |
| **Schema 变更** | MySQL CDC 自动识别 DDL（加列、改类型），Iceberg 表可以自动演化 Schema（需开启） |
| **Exactly-Once** | Flink Checkpoint + Iceberg Sink 事务保证 |
| **UPSERT 语义** | Iceberg 的 `write-mode=upsert` 支持主键更新；MySQL 的 UPDATE 自动映射 |
| **Checkpoint 依赖** | 必须启用 Checkpoint，否则 CDC Source 无法保存 Offset |

## Temporal Join（时态 Join）

实时流和**维表**关联（用户信息表、商品表）时，Temporal Join 是最常用的：

```sql
-- 维表：HBase / MySQL 小表，按 Key 查找最新一条
CREATE TABLE users (
    user_id BIGINT PRIMARY KEY,
    name STRING,
    city STRING
) WITH ('connector' = 'hbase', ...);

-- 订单流实时关联用户信息
CREATE TABLE orders (
    order_id BIGINT,
    user_id BIGINT,
    amount DECIMAL(10,2)
) WITH ('connector' = 'kafka', ...);

-- Temporal Join：每来一条订单，关联用户表当前最新的一行
SELECT
    o.order_id,
    u.name,          -- 实时拿到最新用户名（如果用户改名，新订单立刻看到）
    u.city,
    o.amount
FROM orders AS o
LEFT JOIN users FOR SYSTEM_TIME AS OF o.proc_time AS u
ON o.user_id = u.user_id;
```

| Join 类型 | 适用场景 | 代价 |
| --- | --- | --- |
| **Regular Join** | 双流无限 Join（订单 + 支付关联） | 两侧状态无限增长，必须设窗口/过期 |
| **Interval Join** | 双流按时间区间 Join | 自动清理过期状态 |
| **Temporal Join** | 流 + 维表（维表小、更新相对慢） | 维表状态小；Event-Time Temporal Join 需水位线对齐 |

## Hive Metastore 集成

Flink 可以直接把 Hive 表当 Source/Sink：

```sql
CREATE CATALOG hive_catalog WITH (
    'type'                    = 'hive',
    'hive-conf-dir'           = '/etc/hive/conf',
    'hive-conf.hive.metastore.uris' = 'thrift://hms:9083'
);

USE CATALOG hive_catalog;
SELECT * FROM default.events WHERE dt = '2026-11-04';
```

**Flink + Hive 组合拳**：

- Flink 流写入 Hive / Iceberg 表（分区按天）
- Trino / Spark SQL 查询同一张表
- Hive Metastore 作为统一元数据
- 实现 **流批一体 + 湖仓一体**

## Batch vs Streaming 执行器

Flink SQL 可以**同一条 SQL 既做批处理又做流处理**：

```java
// 批执行器：读有限数据集，一次跑完
env.execute("batch-job");

// 流执行器：读无限流，一直跑
StreamTableEnvironment tableEnv = StreamTableEnvironment.create(env);
```

| 执行器 | 输入 | 行为 | 触发 |
| --- | --- | --- | --- |
| **Batch** | 有限流 | 一次执行完退出 | 批边界（数据读完） |
| **Streaming** | 无限流 | 持续运行不退出 | Watermark / Processing-Time |

> 这就是 Flink「流批一体」的含义：**同一套 API、同一套 SQL、同一套元数据，底层执行引擎可以切批或流**。

## 关键配置

```properties
# Flink SQL Gateway（REST 服务 1.20+）
sql-gateway.endpoint.type: rest
sql-gateway.endpoint.rest.address: 0.0.0.0
sql-gateway.endpoint.rest.port: 8083

# CDC Source 需要 Checkpoint
execution.checkpointing.enabled: true
execution.checkpointing.interval: 60000

# Iceberg Sink Compaction（后台合并小文件）
table.exec.iceberg.enable-compaction: true
table.exec.iceberg.compaction.interval: 10min
```

## 常见问题

- **Flink SQL 和 Spark SQL 怎么选？** 实时流场景选 Flink SQL（Event-Time、CDC、入湖）；纯批场景两者差不多，Spark SQL 生态更广。
- **CDC 要锁 MySQL 表吗？** `scan.startup.mode=initial` 会做一次一致性快照，InnoDB 用 `FLUSH TABLES WITH READ LOCK`（短暂锁），之后切 Binlog。`incremental.snapshot.enabled=true` 用无锁快照。
- **Flink SQL 能写 Python 吗？** 可以，`pyflink.table` 提供 Python Table API；但 Flink SQL Gateway 主要还是用 Java/Scala 提交。
- **Temporal Join 和 Regular Join 区别？** Regular Join 双流都保留状态；Temporal Join 维表只保留最新一行，状态极小。

## 自测

1. 用自己的话解释「Flink SQL 的流批一体」。
2. 写出 MySQL Binlog → Iceberg 入湖的 Flink SQL 骨架代码（至少包括 CDC Source 表、Iceberg Sink 表、INSERT INTO）。
3. Temporal Join 和 Regular Join 的核心差异是什么？各适用什么场景？
4. Flink SQL 为什么必须依赖 Checkpoint 才能稳定跑 CDC？

## 参考与官方文档

- [Flink SQL 官方文档](https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/table/overview/)
- [Flink CDC 连接器](https://nightlies.apache.org/flink/flink-cdc-docs-release-3.2/)
- [Iceberg Connector](https://nightlies.apache.org/flink/flink-docs-stable/docs/connector/iceberg/)
- [Temporal Join](https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/table/sql/queries/joins/#temporal-joins)
