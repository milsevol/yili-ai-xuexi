# 09 Hive 与周边组件

## 一句话

Hive 4.x 的核心定位是 **Metastore（通用元数据中心）+ SQL 兼容层**，不再强调自己是独立执行引擎。**Spark SQL、Flink、Trino（Presto）都能直接连 Hive Metastore 读表结构**，Hive Metastore 成为大数据生态的"基础设施"。同时 Hive 也正在被 Iceberg/Hudi/Delta 等湖仓表格式取代文件层的角色。

## Hive Metastore 的新地位

传统观念里 Metastore 只是 Hive 的一个子组件。但 4.x 之后，Metastore 独立成了一个**可被任意引擎共享的元数据服务**：

```
                    ┌─────────────┐
                    │ Hive Metastore│ ← 唯一真相（表、列、分区、Location）
                    │  （端口 9083）│
                    └──────┬───────┘
                           │ Thrift 协议
          ┌────────────────┼────────────────┬────────────────┐
          ↓                ↓                ↓                ↓
   ┌──────────┐      ┌──────────┐      ┌──────────┐     ┌──────────┐
   │ Spark SQL │      │  Flink   │      │  Trino   │     │   Hive   │
   │（直接连 HMS）│     │（Catalog）│      │（Hive Connector）│  │（HS2 入口）│
   └─────┬────┘      └─────┬────┘      └─────┬────┘     └─────┬────┘
         ↓                  ↓                  ↓                ↓
      [HDFS / 对象存储 / Iceberg / Hudi / Delta]
```

**所有引擎共享同一套 Hive 表定义和分区元数据**。Spark SQL 建的表，Trino 能查到；Flink CDC 写的分区，Hive 能做 ETL。

### Spark SQL 连接 Hive Metastore

```properties
# spark-defaults.conf
spark.sql.catalogImplementation=hive    # 默认连接 Hive Metastore
spark.sql.warehouse.dir=/user/hive/warehouse

# Spark SQL 代码里指定 Metastore URI
# 也可以直接用 hive-site.xml（Spark 启动时读取 classpath 里的 hive-site.xml）
```

```python
# PySpark 连接 Hive Metastore
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("test-hive") \
    .config("spark.sql.catalogImplementation", "hive") \
    .enableHiveSupport() \
    .getOrCreate()

# 直接读 Hive 表
df = spark.table("dwd_order_detail").where("dt='2026-11-03'")
df.show()

# 写 Hive 表
df.write.mode("overwrite").partitionBy("dt").saveAsTable("dwd_order_detail")
```

### Flink 连接 Hive Metastore

```sql
-- Flink SQL 建 Hive Catalog
CREATE CATALOG hive_catalog WITH (
  'type' = 'hive',
  'hive-conf-dir' = '/etc/hive/conf',
  'hadoop-conf-dir' = '/etc/hadoop/conf'
);

USE CATALOG hive_catalog;

-- 读写 Hive 表
SELECT * FROM dwd_order_detail WHERE dt = '2026-11-03';
INSERT INTO dwd_order_detail VALUES (...);
```

### Trino 查询 Hive

Trino 有内置的 `hive` connector，直接连 Hive Metastore：

```properties
# etc/catalog/hive.properties
connector.name=hive
hive.metastore.uri=thrift://hms1:9083,hms2:9083
hive.config.resources=/etc/hive/conf/hive-site.xml
hive.storage-format=ORC
```

Trino 读 Hive 表时**不经过 HiveServer2**，直接用 Hive FileSystem Client 读 HDFS/对象存储，性能比 Hive on Tez/Spark 快 5–20x（纯内存列式执行）。

## 湖仓表格式：Iceberg / Hudi / Delta

这三个正在取代 Hive 原生表的角色，但**都能接 Hive Metastore**：

| 表格式 | 特点 | Hive Metastore 对接 |
| --- | --- | --- |
| **Apache Iceberg** | 表格式（不是引擎），支持 Hive/Spark/Flink/Trino，时间旅行、Schema 演进、隐藏分区 | ✅ Catalog 后端选 Hive |
| **Apache Hudi** | 表格式，支持 MOR/COW 两种写入，Upsert/增量拉取强 | ✅ Catalog 后端选 Hive |
| **Delta Lake** | Databricks 开源，Spark 原生强，时间旅行、Optimization | ✅ 有 Hive Metastore 支持 |

### Iceberg + Hive Metastore 示例

```properties
# iceberg-defaults.properties
# 让 Iceberg 把表元数据写进 Hive Metastore
iceberg.catalog.type=hive
```

```sql
-- 在 Spark 里建 Iceberg 表（会自动在 Hive Metastore 注册）
CREATE TABLE spark_catalog.dwd_order_iceberg (
  order_id    BIGINT,
  user_id     BIGINT,
  amount      DECIMAL(12,2),
  dt          STRING
)
USING iceberg
PARTITIONED BY (dt)
TBLPROPERTIES ('format-version'='2');

-- 然后 Hive 和 Trino 就能直接查到
-- Hive: SELECT * FROM spark_catalog.dwd_order_iceberg WHERE dt='...'
-- Trino: SELECT * FROM hive.dwd_order_iceberg WHERE dt='...'
```

### Iceberg 的优势（对比 Hive 原生表）

| 能力 | Hive 原生 | Iceberg |
| --- | --- | --- |
| 存储格式绑定 | 只能 ORC（事务表） | ORC / Parquet / Avro 都支持 |
| Schema 演进 | 加列简单，改类型/删列有限 | **完整支持**（加/删/改/重命名列） |
| 隐藏分区 | 必须显式 PARTITIONED BY | **支持 transform**（`bucket(16, user_id)`） |
| Time Travel | ❌ | ✅ `SELECT ... VERSION AS OF ...` |
| Compact | 手动/后台 Minor/Major | OPTIMIZE / SORT / ZORDER |
| 写入原子性 | 临时目录 + rename（可能并发问题） | **完整快照 + CAS** |

## Hive vs Iceberg vs Hudi vs Delta 选型

| 场景 | 推荐 | 理由 |
| --- | --- | --- |
| 纯数仓、依赖 Hive Metastore、传统 ORC | **Hive 原生表** | 简单稳定，存量系统 |
| 新项目、需要时间旅行 + Schema 演进 | **Iceberg** | 社区最广，多引擎支持好 |
| 需要 CDC Upsert + MOR（Merge-On-Read） | **Hudi** | MOR 写入 + 增量拉取强 |
| Spark 为主生态、Databricks 客户 | **Delta Lake** | Spark 原生最完善 |
| 全链路流批一体（Flink + Flink CDC） | **Iceberg 或 Hudi** | Flink 对两者都很好 |

## Beeline vs Hive CLI

| 维度 | Hive CLI | Beeline |
| --- | --- | --- |
| 协议 | HiveServer 1 旧协议 | **HiveServer2（JDBC）** |
| Hive 4.x 状态 | **已废弃**（`hive` 命令提示 deprecated） | **推荐**（4.x 唯一入口） |
| 连接方式 | 直接 `hive` | `beeline -u jdbc:hive2://host:10000` |
| 脚本执行 | `hive -e "SELECT ..."` | `beeline -u ... -e "SELECT ..."` 或 `!run script.hql` |

```bash
# Beeline 连接（4.x 推荐方式）
$HIVE_HOME/bin/beeline -u jdbc:hive2://hive-server2:10000 -n hiveuser

# 执行 HQL 脚本
$HIVE_HOME/bin/beeline -u jdbc:hive2://hive-server2:10000 \
  -f /path/to/dwd_order_daily.hql

# Shell 里直接跑
$HIVE_HOME/bin/beeline -u jdbc:hive2://hive-server2:10000 \
  -e "INSERT OVERWRITE TABLE dwd_order PARTITION (dt='2026-11-03')
      SELECT * FROM ods_order WHERE dt='2026-11-03'"
```

## HiveServer2 HA

生产环境至少要部署 2–3 台 HiveServer2，前面挂一个软负载均衡（HAProxy / Nginx / LBS）：

```
Client（Beeline/JDBC）
        ↓
   [HAProxy / LBS]
     ↙     ↘
  HS2-1    HS2-2    ← 都连同一个 Metastore（Remote 模式）
```

```properties
# hive-site.xml（两台 HS2 都配）
hive.server2.thrift.port=10000
hive.server2.thrift.bind.host=0.0.0.0

# JDBC 连接时配多个地址（Failover，不是负载均衡）
# jdbc:hive2://hs2-1:10000,hs2-2:10000/default
```

## Metastore HA

Remote 模式下 Metastore 也可以做多节点 + ZooKeeper 注册中心：

```properties
# hive-site.xml
hive.metastore.uris=thrift://hms1:9083,thrift://hms2:9083,thrift://hms3:9083
hive.zookeeper.quorum=zk1:2181,zk2:2181,zk3:2181
hive.metastore.zookeeper.path=/hive/metastore
```

Metastore 数据库（MySQL/PostgreSQL）可以用主从或多主（Galera Cluster / PgBouncer）。

## Hive vs Spark SQL vs Trino vs ClickHouse：谁做什么

| 组件 | 强项 | 典型角色 |
| --- | --- | --- |
| **Hive** | 数仓建模、ETL、稳定、与 YARN/Tez 整合 | 后端 ETL 主力、数仓建模层 |
| **Spark SQL** | 迭代、Catalyst 快、与 MLlib/图计算整合 | 既要 ETL 又要 ML 的一站式 |
| **Trino（Presto）** | 亚秒级、多数据源联邦查询、列式内存 | **业务方交互式查询 / Ad-hoc** |
| **ClickHouse** | 单表聚合极快、列存压缩好、物化视图 | **ADS 报表层、仪表盘** |

**常见架构组合**：

```
实时：Kafka → Flink → Iceberg/Hudi（CDC Upsert）
批量：Hive on Tez / Spark ETL → DWD/DWS 层（Iceberg 格式，Hive Metastore）
查询：Trino（业务 Ad-hoc）+ ClickHouse（报表 ADS）
```

## 关键配置

```properties
# ============ 多引擎共享 Metastore ============
# hive-site.xml 必须所有引擎都在 classpath 里
hive.metastore.uris=thrift://hms1:9083,thrift://hms2:9083

# ============ Spark 读取 Hive ============
# spark-defaults.conf
spark.sql.catalogImplementation=hive
spark.sql.warehouse.dir=/user/hive/warehouse

# ============ Flink 连接 Hive Catalog ============
# Flink SQL CREATE CATALOG (见上文)
# 需要 flink-sql-connector-hive jar

# ============ Trino Hive Connector ============
# etc/catalog/hive.properties
connector.name=hive
hive.metastore.uri=thrift://hms1:9083,hms2:9083
```

## 常见问题

**Q：Spark SQL 直接 `spark.table("xxx")` 就能查 Hive 表，要不要先 HiveServer2？**
A：不需要。Spark 直接连 Metastore（9083 端口），用 Hive FileSystem Client 读 HDFS。HS2 是给 JDBC/Beeline 用的入口网关。

**Q：Iceberg 表已经在 Hive Metastore 注册了，用 Hive Beeline 能查到吗？**
A：**4.x 部分支持**。Hive 对 Iceberg 表的读写支持在 4.0+ 有增强，但不如 Spark/Flink 完善。建议用 Spark/Flink/Trino 查 Iceberg 表。

**Q：Metastore 挂了会影响 Hive 执行中的查询吗？**
A：已提交到引擎的查询可以继续跑（计划已经生成，元数据已缓存），但新查询提交不了。Metastore 是**高可用服务**，必须部署 HA。

**Q：Trino 查 Hive 表为什么比 Hive on Tez 快？**
A：Trino 是纯内存列式执行，Pipeline 算子之间数据不落地；Tez 虽然 DAG 紧凑，但 Hive on Tez 仍要经过 Hive 编译器 + YARN 调度开销。而且 Trino 可以把小查询拆成秒级返回。

## 自测

1. 画出「Hive Metastore 作为通用元数据中心」的组件图，标出 Spark SQL、Flink、Trino 如何连接它。
2. 用一句话说清 Iceberg 和 Hive 原生表的核心区别，以及它们如何共存。
3. 场景：一个数仓系统，实时 CDC 写入 + 每日 ETL + 业务方秒级 ad-hoc 查询。请推荐组件组合，说明每层选型理由。
4. HiveServer2 和 Metastore 分别的 HA 方案是什么？用在生产环境的最低部署数量是多少？

## 参考与官方链接

- [Hive Metastore 多引擎共享](https://cwiki.apache.org/confluence/display/hive/designofhivemetastore)
- [Spark SQL + Hive Metastore 官方文档](https://spark.apache.org/docs/latest/sql-data-sources-hive-tables.html)
- [Flink Hive Connector](https://nightlies.apache.org/flink/flink-docs-release-1.18/docs/connector/table/hive/)
- [Trino Hive Connector](https://trino.io/docs/current/connector/hive.html)
- [Iceberg Hive Catalog](https://iceberg.apache.org/docs/latest/hive/)
