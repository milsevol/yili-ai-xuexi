# 10 生态对比与FAQ

## 一句话

HBase 不是什么场景都适合的万能药——选它还是选 Hive、ClickHouse、Cassandra、TiDB，取决于「**延迟要求**、**查询模式**、**一致性要求**、**生态绑定**、**运维能力**」五件事。本章先给出选型决策树，再整理高频面试题。

## 决策树：什么时候选谁

```
你的需求有哪些？
│
├─ 需要按主键/RowKey 随机点查或范围扫描吗？
│   │
│   ├─ 是 → 需要 ACID 事务吗？
│   │   │
│   │   ├─ 是 → TiDB（MySQL 协议、分布式事务）
│   │   │        或 CockroachDB（兼容 PostgreSQL）
│   │   │
│   │   └─ 否 → 需要多 DC 主动-主动吗？
│   │            │
│   │            ├─ 是 → Cassandra（可调一致性、多 DC 顶级）
│   │            │
│   │            └─ 否 → 生态绑定 Hadoop 吗？
│   │                     │
│   │                     ├─ 是 → HBase（和 HDFS/ZK 无缝配合）
│   │                     │
│   │                     └─ 否 → 考虑 RocksDB（嵌入式）或 Cassandra
│   │
│   └─ 否 → 主要是聚合分析、多表 Join 吗？
│            │
│            ├─ 低延迟（秒级）→ ClickHouse（列式 OLAP）
│            │                  或 Doris（MPP OLAP）
│            │
│            ├─ 分钟级即可 → Hive（离线数仓）
│            │                  或 Spark SQL + Iceberg（湖仓一体）
│            │
│            └─ 实时流处理 → Flink（流引擎）
│
├─ 纯时序数据（监控、IoT）？
│   ├─ OpenTSDB（基于 HBase）
│   ├─ InfluxDB
│   ├─ TimescaleDB（PostgreSQL 插件）
│   └─ VictoriaMetrics / Mimir
│
└─ 全文搜索、复杂多条件查询？
    ├─ Elasticsearch
    └─ 搜索 + 存储分离（ES 做搜、HBase/对象存储做存）
```

## 五维对比：HBase vs Hive vs ClickHouse vs Cassandra

| 维度 | **HBase** | **Hive** | **ClickHouse** | **Cassandra** |
| --- | --- | --- | --- | --- |
| **模型** | 列式 KV（RowKey 有序） | 分区文件系统 + SQL | 列式 OLAP | 宽列 KV |
| **延迟** | 毫秒级（点查） | 分钟级（批） | 毫秒~秒级（聚合） | 毫秒级（点查） |
| **写入** | 高并发随机写 | 批量 Load（Insert Overwrite） | 高吞吐 Append | 极高并发随机写 |
| **读** | 点查 + 范围 Scan | 全表/分区扫 + 聚合 | 列式扫 + 极速聚合 | 点查 + 有序 Scan |
| **Join** | 不支持 | 支持（底层 MR/Tez/Spark） | 支持（内存 Join） | 不支持 |
| **二级索引** | 无（Phoenix/自建） | 靠分区分桶 | 原生跳数索引 | CQL 原生支持 |
| **事务** | 无（Row 级原子） | 无 | 无 | LWT 轻量 |
| **一致性** | 强一致 | 最终 | 最终 | 可调 |
| **依赖** | HDFS + ZooKeeper | HDFS + 元数据库 | 无 | 无 |
| **生态** | Hadoop | Hadoop + Spark + Flink | 独立 | 独立 |
| **运维复杂度** | 中 | 低~中 | 低 | 高（无主架构） |
| **适合场景** | 画像、时序、计数、随机读写 | 离线数仓、ETL | 实时/近实时 BI、OLAP | 全球多 DC、高可用业务 |
| **不适合** | 多条件查询、Join、复杂 SQL | 高并发点查、随机写 | 高并发点查、Update | 复杂 Join、二级索引复杂 |

## 混合架构：常见组合

没有一个组件能做所有事。真实生产常是**混合架构**：

| 场景 | 存储方案 |
| --- | --- |
| **画像 + 报表 + 搜索** | HBase（画像点查）+ Hive/Spark（报表 ETL）+ ES（全文搜索） |
| **实时写入 + 离线分析** | Flink → Kafka → HBase（实时写），Flink → Iceberg（离线分析） |
| **监控系统** | OpenTSDB / VictoriaMetrics（时序存）+ Grafana（可视化） |
| **电商订单** | TiDB/MySQL（事务）+ HBase（历史明细点查）+ ClickHouse（销售报表） |
| **广告系统** | HBase（点击明细随机查）+ ClickHouse（聚合报表）+ ES（创意素材搜索） |

## HBase on Kubernetes

### 现状

- HBase 原生**不支持**运行在 K8s 上（2.6 仍无官方 Operator）。
- 社区有第三方 Operator：
  - **Bitnami hbase-operator**：相对成熟，2.4/2.5 支持。
  - **Community hbase-operator**：CloudNative 爱好者作品。
- 核心挑战：
  - StatefulSet + 持久化存储（PV/PVC）替代 HDFS。
  - ZooKeeper → Zookeeper Operator。
  - RegionServer 和 HMaster 的启动顺序与依赖。
  - HBase 强依赖网络稳定性——K8s 的 Pod 漂移/重启影响大。

### 要不要上 HBase on K8s

**要，如果**：
- 你的基础设施已经全面容器化（全部业务在 K8s）。
- HBase 只是**轻量级组件**（不是核心业务数据库）。
- 运维团队有能力维护 StatefulSet + Operator。

**不要，如果**：
- HBase 是核心业务库（毫秒级延迟、高 SLA）。
- 数据量大（TB 级以上）。
- 网络稳定性要求高（K8s Pod 漂移会影响 RegionServer 心跳）。

> 当前主流做法：**RegionServer 和 HDFS DataNode 仍跑在物理机/VM 上**，K8s 跑其他业务组件；或者干脆用 Cassandra 替代 HBase（Cassandra 无主架构，更适合 K8s 弹性伸缩）。

## 高频面试题

### 架构类

**Q1：HBase 的 Region 是什么？为什么要切片？**

A：Region 是 HBase 表的一段连续 RowKey 范围，是**存储和负载均衡的最小单位**。切片原因：① 大表切成多个 Region，每个 RegionServer 管几个，横向扩展；② 每个 Region 的 MemStore / HFile / WAL 独立，避免一个 Region 太大导致读写阻塞；③ Region 可以在 RegionServer 间灵活迁移、Split、Merge。

**Q2：HMaster 和 RegionServer 的分工？HMaster 挂了会怎样？**

A：HMaster 管 Region 的分配/Split/Merge/迁移、HBase 元数据；RegionServer 管 Region 的实际读写、Flush、Compaction。**HMaster 不扛读写**——客户端直连 RegionServer。HMaster 挂了：① Active → Standby 顶（60s session timeout）；② 期间 Region 读写正常（客户端不知道 HMaster 挂了）；③ 但 Region 不能 Split/Move/故障恢复。

**Q3：WAL 是什么？为什么要先写 WAL 再写 MemStore？可以关闭吗？**

A：WAL 是 RegionServer 的预写日志（写 HDFS）。先写 WAL（fsync 落盘）再写 MemStore，保证 RegionServer 挂了后 MemStore 未 Flush 的数据可以从 WAL 回放恢复。**可以关闭**（`SKIP_WAL`），但只能用于可重放的数据（比如每日全量同步），否则会丢数据。

### 存储原理类

**Q4：LSM-Tree 和 B+ 树的核心差异？为什么 LSM 写性能好？**

A：B+ 树是单树结构、随机 IO 写；LSM-Tree 是多文件分层、写追加到内存（MemStore）满了顺序 Flush 成 HFile、多个 HFile 再 Compaction 合并。LSM 写性能好因为：① 写走内存追加（O(1)）；② Flush 是顺序写 HDFS；③ B+ 树写要先查索引页、随机 IO、页分裂。代价：读要查多个 HFile + Merge（有读放大），Compaction 有写放大。

**Q5：Flush 和 Compaction 的区别？分别有什么阈值？**

A：Flush：MemStore 满了（默认 128MB/CF）→ 顺序写成 HFile。Compaction：多个 HFile 文件累积超过阈值（默认 3 个）→ 合并成一个。阈值见：`hbase.hregion.memstore.flush.size`、`hbase.hstore.compactionThreshold`、`hbase.hregion.majorcompaction`。Flush 解决 MemStore 内存压力；Compaction 解决 HFile 太多导致读路径爆炸。

**Q6：BloomFilter 有假阳性没假阴性，对 HBase 读意味着什么？**

A：查 Get 时，先查 HFile 的 BloomFilter：① 如果 BloomFilter 说"不在"→ 一定不在（无假阴性）→ 跳过这个 HFile，省了一次 HDFS 读；② 如果 BloomFilter 说"在"→ 可能不在（假阳性）→ 还是要读 Data Block 确认。这极大减少了不必要的 HDFS 读取，是点查性能的关键。

### RowKey 设计类

**Q7：RowKey 为什么不能只用时间戳？**

A：时间戳单调递增，新写入永远落在 RowKey 范围的尾部 → 尾部的 Region 持续热点 → 其他 Region 闲得慌。正确做法：**时间戳只能做后缀**，前缀必须是**散列维度**（设备 ID、用户 ID、盐前缀）。例如时序数据：`device_id + reverse(timestamp_ms)`。

**Q8：RowKey 加盐和哈希的区别？**

A：加盐（Salting）：在 RowKey 前面加固定长度的随机/取模前缀，打散到多个 Region；保留点查能力（知道业务 ID，算加盐）、但范围扫描麻烦（要并发扫所有盐前缀再归并）。哈希：对业务主键做哈希后放前面，**彻底失去有序性**、范围扫描不可用；适合纯点查场景。

### 运维调优类

**Q9：RegionServer 上 Region 太多会怎样？上限多少？**

A：每个 Region 有独立的 MemStore（每个 CF 一个），叠加起来吃掉 RS 的堆内存；每个 Region 都要 Flush/Compaction，Region 多了同时 Flush/Compaction 的概率高 → 集群 IO 打满；Region 多了 HMaster 的元数据管理压力大。**单 RS 上限通常 100–200 个 Region**（2.5+ 多段 Flush 可以到 300+），超过 200 要警惕。

**Q10：Compaction 队列满了怎么办？**

A：① 先缓解：业务低谷时手动 Major Compaction；② 根因：查 IO（HDFS DataNode 磁盘 await）、查 HFile 大小（max.size 太大？）、查 threshold（太松？）；③ 调策略：ExploringCompactionPolicy 比 RatioBased 平滑，时序数据用 FIFOCompactionPolicy；④ 加 IO 资源（DataNode 磁盘、SSD）。

**Q11：RegionServer 心跳超时被 HMaster 判 dead，但它还在跑——为什么？**

A：① **GC 暂停太久**（> 60s）→ RS 无法发送心跳 → HMaster 以为它挂了。② **Swap 被换出** → 任何一页被 swap 回来延迟都可能到秒级。③ **网络抖动** → 丢包或高延迟。预防：① 禁用 Swap；② G1GC / ZGC；③ GC 暂停超时阈值调低；④ 监控告警。

### 选型类

**Q12：HBase vs Cassandra，什么时候选谁？**

A：两者都是 LSM-Tree 的分布式 KV。核心差异：HBase 是**主从架构**（依赖 HDFS + ZooKeeper，Region 分片），Cassandra 是**无主架构**（P2P 自动容错，调一致级别）。选 HBase：① 已经在 Hadoop 生态；② 数据在 HDFS；③ 运维熟悉 Hadoop 工具链。选 Cassandra：① 需要全球多 DC 主动-主动复制；② 高可用 > 一切；③ 可调一致性；④ 不绑定 Hadoop 生态。

**Q13：HBase vs ClickHouse vs TiDB，场景？**

A：HBase：**随机点查 + 范围 Scan**，毫秒级，适合画像/时序/计数。ClickHouse：**列式聚合分析**，极速 Scan+聚合，适合 BI/报表。TiDB：**分布式事务 + MySQL 协议**，适合业务系统（替换 MySQL Sharding）。三者互补不替代：画像用 HBase、报表用 ClickHouse、订单事务用 TiDB。

**Q14：HBase 和 RocksDB 是什么关系？**

A：没有直接关系——两者都是 LSM-Tree 的实现。HBase 是分布式的、运行在 HDFS 上、有 Region/RegionServer/HMaster；RocksDB 是**嵌入式库**（作为进程内组件）、由 Facebook 开源、被 TiDB/CockroachDB/Pika 等用作底层存储引擎。两者可以互相替代吗？不行——HBase 是分布式系统、RocksDB 是单机组件，不在一个层级。

### 实战类

**Q15：怎么给 HBase 加二级索引？**

A：四种方式。① **Phoenix**（推荐）：自动维护索引表、SQL 化查询；② **自建索引表**：再建一张 HBase 表把索引列当 RowKey，主表和索引表双写；③ **ES 方案**：HBase 变化同步到 ES，应用先查 ES 拿 RowKey 再 Batch Get HBase；④ **OpenTSDB 等专用组件**：用特定 RowKey 设计模式实现。

**Q16：批量写 HBase 用什么方式最快？**

A：**BulkLoad**（绕过 WAL + Flush + Compaction，直接把 HFile move 到 HDFS）。步骤：① MR/Spark 并行生成 HFile；② 用 `LoadIncrementalHFiles` BulkLoad 到 HBase。注意：BulkLoad 绕过 WAL，如果 BulkLoad 未完成 RegionServer 挂了可能元数据不一致，适合数据导入场景，不适合实时增量。

## 易错点清单

1. **"HBase 和 Cassandra 是替代品"**：架构完全不同（主从 vs 无主、依赖 HDFS vs 独立），选型要看生态和一致性需求。
2. **"HBase 能做复杂 SQL 查询"**：原生不能，得靠 Phoenix/Kylin/自建索引。
3. **"Region 可以随便 Move"**：Move 期间 Region 不服务（客户端会重试），热 Region 别频繁 Move。
4. **"HBase on K8s 很成熟"**：2.6 仍无官方支持，第三方 Operator 不稳定；生产核心库别上。
5. **"关闭 WAL 能提写性能"**：确实能，但风险极高（丢数据），只适合可重放数据。

## 自测

1. 用你自己的话画一张「HBase vs Hive vs ClickHouse vs Cassandra 选型决策树」。
2. 为什么说 HBase 的 RowKey 设计和 Region 分裂策略共同决定了热点？
3. 某业务要做「实时用户画像 + 离线日报 + 全文搜索」，你会怎么搭？每部分用什么组件？为什么？
4. HBase 和 RocksDB 都是 LSM-Tree，一个做分布式 KV、一个做嵌入式存储——它们的架构差异有哪些？

## 参考与官方文档

- [HBase vs RDBMS FAQ](https://hbase.apache.org/2.5/book.html#faq.vs.rdbms)
- [Phoenix 文档](https://phoenix.apache.org/)
- [Apache Cassandra 官网](https://cassandra.apache.org/)
- [RocksDB 文档](https://rocksdb.org/)
- [ClickHouse 官网](https://clickhouse.com/)
