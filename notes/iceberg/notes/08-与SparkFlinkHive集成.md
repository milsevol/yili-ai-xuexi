# 08 与 Spark / Flink / Hive 集成

## 一句话

Iceberg 是**引擎无关**的表格式：同一张表，Spark 做批量 ETL、Flink 做实时写入、Trino 做交互查询、Hive 4 做只读兼容，彼此共享 Catalog 和元数据；集成的关键只有三件事——**放对 runtime jar、配好 Catalog、理解各引擎的提交时机**。

## 集成总览

```
     Catalog：Hive Metastore / REST / Glue / Nessie（只存元数据指针）
   Spark（批/流）  Flink（实时）  Trino（查询）  Hive 4（只读）
        对象存储 / HDFS（Parquet + Manifest）
```

| 引擎 | 读 | 写 | 典型用途 |
| --- | --- | --- | --- |
| Spark | ✅ | ✅（批 + 微批） | ETL、compaction、维护 |
| Flink | ✅ | ✅（流式，exactly-once） | 实时 CDC、流式入湖 |
| Trino / Presto | ✅ | ✅（1.4+ 基础写） | 交互式查询、联邦分析 |
| Hive 4 | ✅（只读） | ❌ | 兼容存量 Hive SQL |

## Spark 集成

### 依赖与配置

```properties
# spark-defaults.conf 或 --conf
spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions
spark.sql.catalog.ice=org.apache.iceberg.spark.SparkCatalog
spark.sql.catalog.ice.type=hive
spark.sql.catalog.ice.uri=thrift://hms:9083
spark.sql.catalog.ice.warehouse=s3://bucket/warehouse
```

```bash
spark-submit --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.2 ...
```

> 命名规则：`iceberg-spark-runtime-<spark版本>_<scala版本>:<iceberg版本>`。

### SQL 读写

```sql
CREATE TABLE ice.db.orders (
  order_id BIGINT, user_id BIGINT, amount DECIMAL(12,2), ts TIMESTAMP
) USING iceberg PARTITIONED BY (days(ts))
TBLPROPERTIES ('format-version' = '2');

INSERT INTO ice.db.orders VALUES (1, 1001, 99.00, TIMESTAMP '2026-11-01 10:00:00');

MERGE INTO ice.db.orders t
USING (SELECT 1 AS order_id, 88.00 AS amount) s
ON t.order_id = s.order_id
WHEN MATCHED THEN UPDATE SET t.amount = s.amount
WHEN NOT MATCHED THEN INSERT *;

SELECT * FROM ice.db.orders WHERE ts >= TIMESTAMP '2026-11-01 00:00:00';
```

### DataFrame API

```python
df = spark.read.format("iceberg").load("ice.db.orders")   # 读

df.writeTo("ice.db.orders").append()                       # 追加
df.writeTo("ice.db.orders").overwritePartitions()          # 动态覆盖

# 流式写：df.writeStream.format("iceberg").option("checkpointLocation", ...).toTable(...)
```

**提交时机**：批量写在任务成功结束时提交；`INSERT OVERWRITE` 先写新文件再原子切换；流式写每个 microbatch 提交一次，靠 checkpoint 恢复。

## Flink 集成

```sql
CREATE CATALOG ice WITH (
  'type' = 'iceberg', 'catalog-type' = 'hive',
  'uri' = 'thrift://hms:9083', 'warehouse' = 's3://bucket/warehouse',
  'io-impl' = 'org.apache.iceberg.aws.s3.S3FileIO'
);
USE CATALOG ice;

CREATE TABLE ice.db.orders (
  order_id BIGINT, user_id BIGINT, amount DECIMAL(12,2), ts TIMESTAMP(3),
  PRIMARY KEY (order_id) NOT ENFORCED
) WITH (
  'format-version' = '2',
  'write.upsert.enabled' = 'true',
  'write.distribution-mode' = 'hash'
) PARTITIONED BY (days(ts));
```

把 `iceberg-flink-runtime-1.18-1.5.2.jar` 放到 Flink 的 `lib/` 下（版本必须与 Flink 对齐）。

> Flink 的 `PRIMARY KEY` 只是告诉 Iceberg 用 Upsert 模式（写 EQUALITY DELETE + INSERT），不是数据库主键约束。

### 流式写入 exactly-once

Flink 写 Iceberg 的 exactly-once 靠 **checkpoint 两阶段提交**：

```
每个 checkpoint 周期：
  1. 快照算子状态（当前文件、已提交快照）
  2. Iceberg Sink 把本次 checkpoint 内写的文件"预提交"（pending）
  3. checkpoint 完成 → 回调 notifyCheckpointComplete
  4. 此时才真正执行 Iceberg commit（写 manifest + 切指针）

失败恢复：从最近一次成功的 checkpoint 重启
  → 未提交的文件被忽略/清理（不产生脏数据）
  → 已提交的快照不回滚
```

```yaml
# flink-conf.yaml
execution.checkpointing.interval: 60s
execution.checkpointing.mode: EXACTLY_ONCE
```

### 常见坑

| 问题 | 原因 | 解决 |
| --- | --- | --- |
| 小文件太多 | checkpoint 间隔太短 | 调到 60s+，配 compaction |
| 提交失败导致作业重启 | Catalog 不可用 / 权限 | Catalog HA、重试配置 |
| 数据重复 | 没用 upsert | `write.upsert.enabled=true` |
| 写入慢 | 单并发、分区倾斜 | `distribution-mode=hash`、加并行度 |

## Hive 集成

**Hive 4 才支持读 Iceberg**，Hive 3 及以下不支持。

```xml
<!-- hive-site.xml：<property><name>iceberg.engine.hive.enabled</name><value>true</value></property> -->
```

```bash
cp iceberg-hive-runtime-1.5.2.jar $HIVE_HOME/auxlib/
```

```sql
SELECT * FROM db.orders WHERE ts >= '2026-11-01 00:00:00';   -- 只读
```

定位：Hive 4 只用于存量 SQL 兼容、报表工具对接；写入和高级操作交给 Spark/Flink。

## Trino / Presto 集成

```properties
# etc/catalog/iceberg.properties
connector.name=iceberg
iceberg.catalog.type=hive_metastore
hive.metastore.uri=thrift://hms:9083
fs.native-s3.enabled=true
```

```sql
SELECT * FROM iceberg.db.orders WHERE ts >= TIMESTAMP '2026-11-01 00:00:00';
SELECT * FROM iceberg.db.orders FOR VERSION AS OF 3051729675574597004;
```

Trino 特点：纯内存 Pipeline、交互查询快、支持 Time Travel；写入能力有限，不适合大批量 ETL。PrestoDB 的 connector 类似，但版本滞后。

## 版本兼容矩阵

> 下表为常见组合，实际以官方兼容性文档为准。**核心原则：runtime jar 的主版本后缀必须与引擎主版本严格匹配。**

| Iceberg | Spark | Flink | Hive | Trino |
| --- | --- | --- | --- | --- |
| 1.4.x | 3.3 / 3.4 | 1.16 / 1.17 | 4.0（只读） | 426+ |
| 1.5.x | 3.4 / 3.5 | 1.17 / 1.18 | 4.0（只读） | 435+ |
| 1.6.x | 3.5 | 1.18 / 1.19 | 4.0（只读） | 445+ |

- **Scala 版本**：Spark 3.x 用 Scala 2.12 / 2.13，jar 名要匹配
- **Flink 小版本**：`iceberg-flink-runtime-1.18` 不能用于 Flink 1.19
- **Catalog 共享**：所有引擎连**同一个** Hive Metastore / REST，warehouse 路径一致

## 多引擎协作的典型架构

```
MySQL ──Debezium──► Kafka ──Flink──► Iceberg（ODS，MOR Upsert）
                                        ├── Spark（清洗、compaction）──► Iceberg（DWD）
                                        ├── Trino（交互查询 / BI）
                                        └── StarRocks（外部表，极速 OLAP）
```

1. **统一 Catalog**：所有引擎用同一个 Hive Metastore / REST
2. **统一格式**：全表 Parquet + zstd，避免格式混用
3. **写入分工**：Flink 只写 ODS；Spark 负责 DWD/DWS；Trino 只读
4. **维护与权限统一**：compaction / expire 由 Spark 定时跑；对象存储 + Catalog 两层权限

## 常见问题

**Q：同一张表能被 Spark 和 Flink 同时写吗？**
A：能，但会有并发冲突和 compaction 竞争。建议按分区/职责分工：Flink 写实时分区，Spark 写历史/批量，维护任务单独跑。

**Q：Flink 写 Iceberg 怎么保证 exactly-once？**
A：靠 checkpoint 的两阶段提交：checkpoint 期间写 pending 文件，`notifyCheckpointComplete` 后才真正 commit。失败重启时未提交文件会被清理。

**Q：Hive 3 能读 Iceberg 吗？**
A：官方不支持。Hive 4 才内置 Iceberg 读支持，Hive 3 只能通过 Spark/Trino 读取。

**Q：Trino 查 Iceberg 需要额外装 jar 吗？**
A：不需要，Trino 内置 Iceberg connector，只需要在 `etc/catalog/` 配好 properties。

## 自测

1. Spark 集成 Iceberg 需要哪两类配置（jar + conf）？
2. Flink 写 Iceberg 的 exactly-once 依赖什么机制？描述提交的两个阶段。
3. Hive 4 对 Iceberg 的支持是读还是写？为什么？
4. Trino 和 Spark 在 Iceberg 查询上的定位差异是什么？

## 参考与官方链接

- [Iceberg Spark 集成](https://iceberg.apache.org/docs/latest/spark-getting-started/)
- [Iceberg Spark 写入](https://iceberg.apache.org/docs/latest/spark-writes/)
- [Iceberg Flink 集成](https://iceberg.apache.org/docs/latest/flink/)
- [Iceberg Flink 写入（exactly-once）](https://iceberg.apache.org/docs/latest/flink-writes/)
- [Iceberg Hive 集成](https://iceberg.apache.org/docs/latest/hive/)
- [Iceberg Trino 集成](https://trino.io/docs/current/connector/iceberg.html)
