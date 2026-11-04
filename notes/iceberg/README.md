# Apache Iceberg（湖仓一体）

Apache Iceberg 是**开放表格式（Open Table Format）**：它不存数据、不跑计算，而是在 Parquet / ORC / Avro 文件之上加了一层「元数据树 + 快照」，让对象存储上的「一堆文件」第一次拥有了**数据库语义**——ACID、Schema 演进、隐藏分区、Time Travel、多引擎并发读。

Iceberg 直接解决了传统 Hive 表的三大痛点：**无 ACID（不能行级 UPDATE/DELETE）**、**分区演进难（改分区要重写全表）**、**无 Time Travel（查不到历史版本）**。今天它已经是「湖仓一体」的事实标准之一：Spark、Flink、Trino、Presto、Hive、StarRocks、Doris、Snowflake、BigQuery 都能直接读写同一张 Iceberg 表。

本主题用中文笔记梳理「为什么需要 → 元数据怎么组织 → 怎么保证 ACID → 怎么演进 → 怎么集成 → 怎么调优 → 怎么选型」的完整链路。

> 版本参考：以 **Iceberg 1.4 / 1.5 / 1.6** 为准，示例以 Spark SQL、Flink SQL、Iceberg Java API、表属性（TBLPROPERTIES）为主。配套**浏览器可视化交互演示**：元数据五层展开、并发写冲突 retry、隐藏分区演进、Time Travel 时间轴、Schema 列 ID 映射、小文件合并、分区计算器等，打开 `demos/index.html` 即玩，无需集群。

## 先决知识

- 了解 HDFS 或 S3 等对象存储：文件、目录、List 操作、最终一致性（对象存储没有 rename，只有 copy + delete）
- 了解 Hive Metastore：库表元数据、`thrift://host:9083`、Spark/Flink/Trino 共享元数据中心
- 会用 Spark 或 Flink 其中之一：DataFrame / Spark SQL / Flink SQL / checkpoint
- 了解 Parquet / ORC 列式格式：行组（Row Group / Stripe）、列统计信息、谓词下推
- 知道「数据湖」和「数据仓库」的基本区别（Schema-on-Read vs Schema-on-Write）

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与湖仓一体](./notes/01-概述与湖仓一体.md) | `./start.sh 01` | 数据湖 vs 数仓 vs 湖仓一体；Hive 表四大痛点；Iceberg/Hudi/Delta 对比；为什么 Iceberg 成事实标准 |
| 2 | [02-架构与元数据层级](./notes/02-架构与元数据层级.md) | `./start.sh 02` | Catalog → Metadata File → Manifest List → Manifest → Data File；Snapshot；元数据演进；Catalog 类型 |
| 3 | [03-表格式与文件组织](./notes/03-表格式与文件组织.md) | `./start.sh 03` | Parquet/ORC/Avro；Manifest 结构；min/max/null count 统计；data file 与 delete file；元数据规划 |
| 4 | [04-ACID与快照隔离](./notes/04-ACID与快照隔离.md) | `./start.sh 04` | 原子切换 metadata 指针；乐观并发控制；Snapshot Isolation；冲突检测与 retry；Compaction |
| 5 | [05-分区演进与隐藏分区](./notes/05-分区演进与隐藏分区.md) | `./start.sh 05` | Hive 分区 vs 隐藏分区；partition spec 演进；days()/hours()/bucket()/truncate()；分区裁剪 |
| 6 | [06-TimeTravel与版本管理](./notes/06-TimeTravel与版本管理.md) | `./start.sh 06` | Snapshot；VERSION AS OF / TIMESTAMP AS OF；rollback / cherrypick；branch 与 tag；快照过期 |
| 7 | [07-Schema演进与数据类型](./notes/07-Schema演进与数据类型.md) | `./start.sh 07` | 加列/删列/重命名/改类型；列 ID 而非列名；嵌套结构演进；分区字段变更的区别 |
| 8 | [08-与SparkFlinkHive集成](./notes/08-与SparkFlinkHive集成.md) | `./start.sh 08` | Spark 读写；Flink 流式写入 exactly-once；Hive 4 读 Iceberg；Trino/Presto；版本兼容矩阵 |
| 9 | [09-性能优化与实践](./notes/09-性能优化与实践.md) | `./start.sh 09` | compaction rewrite_data_files；rewrite_manifests；分区策略；Z-Order；统计信息与裁剪；维护调度 |
| 10 | [10-生态对比与FAQ](./notes/10-生态对比与FAQ.md) | `./start.sh 10` | Iceberg/Hudi/Delta 深度对比；Paimon；选型建议；湖仓落地架构；常见面试题 |

建议：01–02 建立心智模型（**表格式 = 元数据树 + 快照**）；03–04 是理解内核的主战场（文件组织与 ACID）；05–07 是 Iceberg 相对 Hive 的核心增量能力；08 面向多引擎落地；09 面向生产调优；10 面向选型与面试。

## 如何启动演示

```bash
cd notes/iceberg
./start.sh          # 打开浏览器交互演示页
./start.sh 02       # 直达第 2 章（架构与元数据层级）
./start.sh --cli    # 备用：终端文字摘要
./start.sh --cli 02 # 终端查看第 2 章摘要
```

也可从仓库根进入：`python3 main.py iceberg`。演示为纯 HTML/JS，无需构建、无需集群、无需 Java。

## 本地快速验证（可选）

只想跑通「建一张 Iceberg 表 + 写入 + 时间旅行」，最省事的是 Spark 3.5 + `iceberg-spark-runtime` jar。用本地 Hadoop Catalog + 本地文件系统即可，不需要 HDFS/S3：

```bash
# 1) 启动 Spark（local 模式），带上 Iceberg runtime jar 与 Hive 支持
spark-sql \
  --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.2 \
  --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions \
  --conf spark.sql.catalog.local=org.apache.iceberg.spark.SparkCatalog \
  --conf spark.sql.catalog.local.type=hadoop \
  --conf spark.sql.catalog.local.warehouse=/tmp/iceberg-warehouse
```

```sql
-- 2) 建表：按天分区（隐藏分区，不是目录 dt=xxx）
CREATE TABLE local.db.orders (
  order_id  BIGINT,
  user_id   BIGINT,
  amount    DECIMAL(12,2),
  ts        TIMESTAMP
) USING iceberg
PARTITIONED BY (days(ts))
TBLPROPERTIES ('format-version' = '2');

-- 3) 写入两批数据 → 两个 snapshot
INSERT INTO local.db.orders VALUES
  (1, 1001, 99.00, TIMESTAMP '2026-11-01 10:00:00'),
  (2, 1002, 20.00, TIMESTAMP '2026-11-02 11:00:00');

-- 4) 看快照列表
SELECT snapshot_id, committed_at, operation FROM local.db.orders.snapshots;

-- 5) Time Travel 查历史
SELECT * FROM local.db.orders VERSION AS OF 1;

-- 6) 行级 UPDATE（Hive 表做不到）
UPDATE local.db.orders SET amount = 88.00 WHERE order_id = 1;
```

> 生产环境把 Catalog 换成 Hive Metastore（`type=hive`）或 REST Catalog，warehouse 指向 `s3://bucket/warehouse`。Iceberg 需要对象存储支持**原子 rename 或条件写**：S3 用 `S3FileIO`（依赖 DynamoDB 做提交协调），HDFS 用原生 rename，二者都开箱即用。

## 参考与官方文档

- Iceberg 官方文档（总入口）：https://iceberg.apache.org/docs/latest/
- 表格式规范（Table Spec v1/v2/v3）：https://iceberg.apache.org/spec/
- 分区转换函数：https://iceberg.apache.org/docs/latest/partitioning/
- Spark 集成：https://iceberg.apache.org/docs/latest/spark-writes/
- Flink 集成：https://iceberg.apache.org/docs/latest/flink/
- Hive 集成：https://iceberg.apache.org/docs/latest/hive/
- 表维护（Compaction / Rewrite Manifests）：https://iceberg.apache.org/docs/latest/maintenance/
- 配置项全集：https://iceberg.apache.org/docs/latest/configuration/
- Nessie（Git 式 Catalog）：https://projectnessie.org/
- 论文：Apache Iceberg: An Open Table Format for Huge Analytic Datasets
- GitHub：https://github.com/apache/iceberg
- 生态对比：Apache Hudi https://hudi.apache.org/ · Delta Lake https://delta.io/ · Apache Paimon https://paimon.apache.org/
- 推荐阅读：《Designing Data-Intensive Applications》第 3 章（存储与检索）、第 7 章（事务）
