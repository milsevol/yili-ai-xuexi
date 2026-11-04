# 09 HBase与周边组件

## 一句话

HBase 不是孤立的——它上接 HDFS、下接 ZooKeeper、跟 Hive/Spark 配合做分析、被 Phoenix 变成 SQL、被 OpenTSDB 变成时序数据库、用 ES 做二级索引、跟 Cassandra/RocksDB 是同类竞品——理解它在这个生态里的位置，才能知道什么时候选谁。

## HBase vs Cassandra vs RocksDB

三者都是 LSM-Tree 架构的 KV/宽列存储，但定位完全不同：

| 维度 | **HBase** | **Apache Cassandra** | **RocksDB / LevelDB** |
| --- | --- | --- | --- |
| 类型 | 分布式列式 KV | 分布式宽列 KV | 嵌入式 KV |
| 架构 | 主从（HMaster + RegionServer） | 无主（P2P） | 单进程（作为库） |
| 一致性 | 强一致（按 Region 内） | 可调（ONE/QUORUM/ALL） | 强一致（单进程内） |
| 依赖 | HDFS + ZooKeeper | 无（自带存储和协调） | 无（直接链接） |
| 写吞吐 | 高 | 非常高（无主，多副本并行写） | 极高（无分布式开销） |
| 读延迟 | 毫秒级 | 毫秒级 | 亚毫秒级 |
| 跨 DC | 靠 HBase Replication | 原生多 DC（顶级能力） | 靠业务层 |
| 二级索引 | 无（需自建/用 Phoenix） | 原生 CQL 支持 | 无 |
| SQL | 靠 Phoenix / Kylin | 原生 CQL（类似 SQL） | 无 |
| 事务 | 无（Increment 是原子操作） | 无（LWT 轻量事务） | 有（WriteBatch） |
| 运维复杂度 | 中（HDFS+ZK+RS） | 高（无主架构运维） | 低（嵌入式） |
| 适用 | Hadoop 生态内、HDFS 成本利用、批量数据同步 | 全球多 DC、高可用、业务自管 | 单机/单节点场景、嵌入式 |

### 选型要点

- **你在 Hadoop 生态里，数据已经在 HDFS 上** → HBase（无需迁移）。
- **需要全球多 DC、主动-主动复制** → Cassandra（顶级能力）。
- **要极致低延迟（微秒级）、单机/嵌入式** → RocksDB（TiDB、CockroachDB、Pika 都用它做底层）。
- **想用 SQL 但又想随机读写** → Cassandra（CQL）或 HBase + Phoenix。

## Hive on HBase

Hive 可以把 HBase 表当成 Hive 表来读写——底层数据在 HBase（走 HBase API），上层用 Hive SQL 交互：

```sql
-- 建一个 Hive 外表，映射到 HBase 的 user 表
CREATE EXTERNAL TABLE hive_user (
  rowkey STRING,
  name STRING,
  age INT,
  city STRING
)
STORED BY 'org.apache.hadoop.hive.hbase.HBaseStorageHandler'
WITH SERDEPROPERTIES (
  "hbase.columns.mapping" = ":key,info:name,info:age,addr:city"
)
TBLPROPERTIES ("hbase.table.name" = "user");

-- 然后就能用 Hive SQL 读写 HBase 表了！
SELECT name, city FROM hive_user WHERE age > 30;

INSERT INTO hive_user VALUES ('user999', 'Diana', 35, 'Guangzhou');
```

### 优缺点

| 优点 | 缺点 |
| --- | --- |
| SQL 化访问 HBase，用户零门槛 | 底层走 Hive 执行引擎（MR/Tez/Spark），**延迟高（秒级/分钟级）** |
| 利用 HBase 的存储和 Region 分片 | 不能做复杂 Join（HBase 不支持） |
| HBase 的高并发写保留 | Scan 可能触发全表扫，要小心 |
| 适合"偶尔 SQL 查询 HBase 数据" | 不是高并发 OLTP |

### 什么时候用

- 业务已经在 HBase 上存数据，需要**临时用 SQL 查一下**（报表、开发验证）。
- 不适合作为生产级 SQL 查询入口——延迟太高。

## Spark 读写 HBase

### Spark 通过 HBase API 读写

```scala
// 引入 hbase-client 依赖
import org.apache.hadoop.hbase._
import org.apache.hadoop.hbase.client._

val conf = HBaseConfiguration.create()
conf.set("hbase.zookeeper.quorum", "zk1,zk2,zk3")
conf.set(TableInputFormat.INPUT_TABLE, "user")

// 读：RDD
val hBaseRDD = sc.newAPIHadoopRDD(conf, classOf[TableInputFormat], classOf[ImmutableBytesWritable], classOf[Result])
hBaseRDD.take(10).foreach { case (_, result) =>
  println(Bytes.toString(result.getRow))
}

// 写：BulkLoad 或 HBaseOutputFormat
val dataRDD = sc.parallelize(Seq(
  (Bytes.toBytes("user999"), Bytes.toBytes("info"), Bytes.toBytes("name"), Bytes.toBytes("Diana"))
))
dataRDD.foreachPartition { iter =>
  val connection = ConnectionFactory.createConnection(conf)
  val table = connection.getTable(TableName.valueOf("user"))
  iter.foreach { case (row, cf, qual, value) =>
    table.put(new Put(row).addColumn(cf, qual, value))
  }
  table.close()
  connection.close()
}
```

### Spark SQL 读 HBase

```scala
// Spark 3.x + hbase-spark connector
import org.apache.hadoop.hbase.spark._

val df = spark.read.hbase("user", 
  Map("cf" -> Seq("name", "age"))
)
df.show()
```

### BulkLoad from Spark

批量写 HBase 的标准姿势——Spark 并行生成 HFile，然后 BulkLoad 到 HBase：

```scala
// 1. Spark 并行生成 HFile
dataRDD.map { case (rowkey, cf, qual, value) =>
  (rowkey, new KeyValue(rowkey, cf, qual, value))
}.saveAsNewAPIHadoopFile(
  "/tmp/bulkload_hfile",
  classOf[org.apache.hadoop.mapreduce.lib.output.MapReduceFileOutputFormat]
)

// 2. BulkLoad（用 LoadIncrementalHFiles）
// 可以 MR 跑，也可以 Spark 跑完直接在主程序里调
```

### HBase on Spark 常见坑

- **每个 partition 建一个 Connection**：Connection 是 JVM 级单例，**不能在 map 里重复创建**。用 `foreachPartition` 在 partition 级别建一次。
- **BulkLoad 绕过 WAL**：数据导入场景没问题，但如果 BulkLoad 还没完成 RegionServer 挂了，可能元数据不一致。
- **Scan 用 `setCaching`**：Spark 默认每次 Scan 只取 1 行，务必调大。

## 二级索引方案

HBase 没有原生二级索引。按"行外列"（非 RowKey）查询只能全表扫或手动建索引。常用方案：

### 1. Phoenix（最主流）

Phoenix 是 HBase 上的 SQL 层，**原生支持二级索引**：

```sql
-- 建表（底层是 HBase 表）
CREATE TABLE user (
  rowkey VARCHAR PRIMARY KEY,
  name VARCHAR,
  age INTEGER,
  city VARCHAR
);

-- 建二级索引（底层在 HBase 里建一张索引表）
CREATE INDEX idx_user_city ON user (city);

-- 直接用索引查（Phoenix 内部用二级索引表定位 rowkey，然后走点查）
SELECT * FROM user WHERE city = 'Beijing';
```

| 特性 | 说明 |
| --- | --- |
| 二级索引实现 | 在 HBase 里建独立的索引表，索引 key 包含索引列值 + rowkey |
| 索引类型 | Single Column、Multi Column、Covered Index、Local Index |
| 维护 | 自动维护（写主表时同步写索引表） |
| 读加速 | 查询走索引表 → rowkey → 点查主表 |
| 延迟 | 比原生 HBase API 慢约 2–5×（多了一层） |
| 写放大 | 建索引后写操作额外写索引表 |

### 2. OpenTSDB（时序数据库）

OpenTSDB 不是二级索引，而是**把 HBase 变成时序数据库**：

```
metric=sys.cpu.percent, tags={host=web01, region=cn}
  → 按 metric + timestamp 做 RowKey，按 tags 做 Qualifier
  → 底层数据在 HBase
  → 支持按 metric 名称、按 tag 过滤查询
```

- 底层在 HBase 上用特定的 RowKey 设计模式。
- 支持聚合、下采样、多种输出格式（JSON/Grafana）。
- 适合监控数据。

### 3. ElasticSearch 方案（最灵活）

把 HBase 的变化同步到 ES，用 ES 做全文搜索和复杂查询：

```
HBase 表 Put/Delete
  → 订阅 HBase WAL（或用 HBase Replication 或 CDC）
  → 把变更转换成 ES 文档
  → 写入 ES
  → 应用层先查 ES 拿 rowkey 列表，再批量 Get HBase
```

| 方案 | 实现难度 | 实时性 | 功能 |
| --- | --- | --- | --- |
| 手动订阅 WAL | 高 | 秒级延迟 | 完全可控 |
| HBase CDC → Kafka → ES | 中 | 秒级延迟 | 标准链路，易维护 |
| Spark Streaming/Flink CDC | 中 | 秒级延迟 | 可做复杂加工 |
| Data Sync（双写） | 简单 | 实时 | 但要处理双写一致性 |

### 4. 自建索引表（最简单）

本质上就是**再建一张 HBase 表**，把索引列当 RowKey：

```
主表 user: RowKey = user_id
索引表 user_idx_city: RowKey = city + user_id

查 city='Beijing' 的用户：
  Scan user_idx_city 前缀 "Beijing" → 拿到所有 user_id
  Batch Get 主表 → 返回完整数据

写时：
  同时写 user（主表）和 user_idx_city（索引表）
```

- 简单、灵活、完全可控。
- 要处理双写一致性（失败重试、幂等）。
- 每张索引表 = 一次额外写入 = 双倍写放大。

### 二级索引方案对比

| 方案 | 适合场景 | 优点 | 缺点 |
| --- | --- | --- | --- |
| **Phoenix** | 需要 SQL、多种二级索引 | 成熟、自动维护、SQL 化 | 写放大、比原生 API 慢 |
| **OpenTSDB** | 时序数据监控 | 专业时序查询 | 只适合时序 |
| **ES + HBase** | 全文搜索、复杂多条件查询 | ES 查询能力强 | 链路长、最终一致 |
| **自建索引表** | 自定义 RowKey、最简链路 | 完全可控、无黑盒 | 手动维护、写放大 |

## HBase Replication（跨集群复制）

2.5+ 原生支持 Region 级复制：

```
集群 A 写
  │
  │ HBase Replication（类似 MySQL binlog 同步）
  ▼
集群 B 读（同一 HBase 表）
```

- **用途**：灾备、就近读、业务拆分、数据同步到分析集群。
- **2.6 新特性**：Region 级复制——可以只复制某些 Region，粒度比表级更细。

## 与 Kylin 的配合

Kylin 是基于 HBase 的 OLAP 引擎：把维度数据预聚合后存 HBase，查询时直接走预计算结果。

```
Kylin Cube 构建
  → 预聚合不同维度组合
  → 编码后写入 HBase
  → 查询时直接读 HBase 预计算结果
  → 秒级响应复杂聚合
```

## 生态全景图

```
                    ┌────────────┐
                    │   Hive     │── SQL 数仓（离线批处理）
                    └─────┬──────┘
                          │ 写/读
                    ┌─────▼──────┐
                    │   HBase    │── 随机读写、高并发写、宽表
                    └─────┬──────┘
                          │ 底层存储
                    ┌─────▼──────┐
                    │    HDFS    │── 分布式文件系统、便宜大存储
                    └────────────┘
                    
HBase 周边（上接下连）：
  上：Phoenix（SQL+二级索引）、OpenTSDB（时序）、Kylin（OLAP）、ES（全文）、Spark/Flink（计算）
  下：HDFS（存储）、ZooKeeper（协调）
  
与竞品：
  Cassandra（无主、多 DC、可调一致性）
  RocksDB（嵌入式、极致低延迟）
  ClickHouse（列式 OLAP 聚合）
```

## 易错点清单

1. **Hive on HBase 拿来做生产 OLTP**：不行，延迟秒级起，Hive 是批处理引擎。
2. **Phoenix 和原生 HBase API 混用**：可以，但注意 Phoenix 自己加的 CF 和 Qualifier 前缀，别误删。
3. **自建索引表不处理双写一致性**：主表写成功但索引表写失败 → 查询时漏数据。
4. **Cassandra 和 HBase 架构完全不同**：一个是无主 P2P、一个是主从 Region 分片，选型要懂架构差异。

## 自测

1. 某业务需要：高并发点查（ms 级）、按时间范围扫时序数据、偶尔 SQL 查询、数据已经在 HDFS 上。你会怎么搭？
2. Phoenix 的二级索引底层是怎么实现的？对写性能有什么影响？
3. 想给 HBase 加一个「按 email 查用户」的二级索引，你有哪几种实现方式？各有什么优缺点？
4. HBase 和 Cassandra 的核心架构差异是什么？各自在什么场景赢？

## 参考与官方文档

- [Phoenix 项目](https://phoenix.apache.org/)
- [OpenTSDB](http://opentsdb.net/)
- [HBase Replication](https://hbase.apache.org/2.5/book.html#cluster.replication)
- [Hive on HBase](https://cwiki.apache.org/confluence/display/hive/hbaseintegration)
