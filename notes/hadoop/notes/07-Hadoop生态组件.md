# 07 Hadoop 生态组件

## 一句话

**Hadoop 的底座只有 HDFS、YARN、MapReduce，但真正把它变成「数仓 + 数据库 + 数据管道」的，是 Hive、HBase、ZooKeeper、采集同步工具、调度器和安全组件。**

## 生态全景

| 组件 | 解决什么问题 | 现状（Hadoop 3.3/3.4 时代） |
| --- | --- | --- |
| **HDFS** | 分布式存储，多副本容错 | 仍在服役，新项目逐渐转向对象存储 + 湖仓 |
| **YARN** | 集群资源管理与调度 | 传统行业主力，新增负载被 K8s 分流 |
| **MapReduce** | 批处理编程模型 | 基本退场，只维护存量作业 |
| **Hive** | 文件映射成表，用 SQL 做数仓 | 4.x 仍在发布，执行多交给 Tez/Spark |
| **HBase** | 海量数据随机读写 | 2.x 稳定，点查场景不可替代 |
| **ZooKeeper** | 分布式协调、选主、配置 | Hadoop HA 的基石 |
| **Tez** | DAG 执行引擎，替代 MR 跑 Hive | Hive on Tez 仍是常见生产形态 |
| **Sqoop** | 关系库 ↔ HDFS 批量同步 | **已退役**，换 DataX / SeaTunnel / Flink CDC |
| **Flume** | 日志采集与汇聚 | 逐步被 Filebeat + Kafka 取代 |
| **Kafka** | 消息缓冲、削峰、解耦 | 实时链路标配，不是长期存储 |
| **Oozie** | 工作流调度 | **已进 Attic**，换 DolphinScheduler / Airflow |
| **Ranger / Kerberos** | 授权 / 认证 | 生产必配 |

## Hive：把文件变成数仓

`Client（beeline / JDBC / ODBC）→ HiveServer2(10000) → 编译器 → MR/Tez/Spark 执行引擎`，所有元数据统一走 Metastore(9083)。

| 组件 | 职责 | 关键点 |
| --- | --- | --- |
| **Metastore** | 存库、表、分区、列、SerDe、权限等元数据 | 生产必须**远程模式** + 独立 MySQL，别用内嵌 Derby |
| **HiveServer2** | 接收 SQL、会话管理、返回结果 | 多用户入口，端口 10000 |
| **编译器** | SQL → AST → 逻辑计划 → 优化 → 物理计划 | 谓词下推、列裁剪、Join 重排 |
| **执行引擎** | 把物理计划跑成 MR/Tez/Spark 作业 | `hive.execution.engine` 默认 `mr`，生产多用 `tez` |
| **Metastore 服务** | 通过 thrift 暴露元数据给多引擎 | 端口 9083，Hive/Spark/Flink/Trino 共享 |

Metastore 三种模式：**内嵌**（Derby，单进程独占，多会话会锁死）、**本地**（本机 MySQL，单机用）、**远程**（独立 MySQL + `thrift://host:9083`，生产唯一选择）。

| 年代 | 引擎 | 特点 |
| --- | --- | --- |
| Hive 1.x | MapReduce | 每个 stage 落盘，慢 |
| Hive 2.x+ | Tez | DAG 合并多个 MR，减少落盘，快数倍 |
| 现在 | Spark / Trino | Hive 主要留 Metastore 和 SQL 兼容层 |

| | 内部表（managed） | 外部表（external） |
| --- | --- | --- |
| 数据归属 | Hive 管理 | 用户自己管理 |
| `DROP TABLE` | 删元数据 **+ 删数据** | 只删元数据，数据保留 |
| 典型用途 | 中间表、ETL 结果 | 原始日志、共享数据、对象存储上的数据 |

注意：Hive 3.x 一度把 managed 表默认设为 ACID 事务表，4.x 又调整过默认行为，`hive.create.as.acid`、`hive.create.as.external.legacy` 在不同版本默认值不一致。**建表时显式写 `EXTERNAL` 和 `STORED AS ORC`，别依赖默认值。**

| | 分区（Partition） | 分桶（Bucket） |
| --- | --- | --- |
| 本质 | 按列值拆**目录** | 按列 hash 取模拆**文件** |
| 好处 | 分区裁剪，少扫数据 | 采样、Map Join、按桶并行 |
| 写法 | `PARTITIONED BY (dt STRING)` | `CLUSTERED BY (user_id) INTO 16 BUCKETS` |
| 坑 | 分区过多 → 小文件、Metastore 压力 | 桶数要和文件大小匹配，写入要开 `hive.enforce.bucketing` |

| 格式 | 列式 | 压缩 | 谓词下推 | 说明 |
| --- | --- | --- | --- | --- |
| TextFile | 否 | 可选 | 否 | 可读性最好，生产几乎不用 |
| Parquet | 是 | 内置 | 是 | Spark 生态最常用 |
| **ORC** | 是 | 内置（Zlib/Snappy/ZSTD） | 是（stripe 索引） | Hive 原生，ACID 表必须 ORC |
| Avro | 否（行式） | 可选 | 否 | Schema 演进友好，适合写 Kafka |

> Hive 表优先 ORC，Spark 为主就 Parquet；两者互相可读，但别在同一张表上混用。

**Hive 4.x 现状**：4.0 于 2024 年 3 月发布（后续 4.1/4.2 继续迭代，并开始支持 JDK 21），Metastore 与执行进一步解耦。生产里 Hive 更多是「Metastore + SQL 兼容层」，计算交给 Spark/Trino。元数据共享是最大价值：Spark 配 `spark.sql.catalogImplementation=hive` + `hive.metastore.uris=thrift://hms:9083`，Flink、Trino 同理，一份表定义多引擎可读。

## HBase：LSM 上的随机读写数据库

HDFS 适合「一次写入、顺序大扫描」，不适合「按 RowKey 毫秒级点查、高并发随机写」，HBase 在 HDFS 之上补了这层能力。

```
写：Client → RegionServer → WAL → MemStore →（满了）flush 成 HFile → 后台 Compaction 合并
读：Client → RegionServer → MemStore → BlockCache → HFile（BloomFilter 先过滤）
```

| 概念 | 作用 |
| --- | --- |
| **WAL** | 预写日志，宕机恢复 MemStore 未落盘数据 |
| **MemStore** | 内存写缓冲，按 ColumnFamily 独立 |
| **HFile** | HDFS 上的有序存储文件 |
| **Compaction** | minor 合并小文件，major 合并并清理过期版本 |

| 角色 | 职责 | 端口 |
| --- | --- | --- |
| **HMaster** | 建删表、Region 分配迁移、负载均衡 | 16000 RPC / 16010 Web |
| **RegionServer** | 托管 Region，处理读写、flush、compact | 16020 RPC / 16030 Web |
| **ZooKeeper** | 存 `hbase:meta` 位置、Master 选举、集群状态 | 2181 |
| **Region** | 表按 RowKey 范围切分的分片 | 达 `hbase.hregion.max.filesize`（默认 10GB）自动 split |

**RowKey 设计决定成败**：

| 问题 | 做法 |
| --- | --- |
| 写热点（单调递增 RowKey 全打一台） | **加盐**：`0~9` 前缀打散；**哈希**：`MD5(key)` 前几位做前缀 |
| 需要按时间倒序查最新 | **反转**：`Long.MAX_VALUE - timestamp` 做前缀 |
| RowKey 太长，索引膨胀 | 控制在 16–32 字节，能用二进制别用长字符串 |
| 有范围扫描需求 | 设计成「前缀相同、后缀有序」，如 `salt + user_id + ts` |

| 适合 | 不适合 |
| --- | --- |
| 按 RowKey 点查、前缀扫描 | 复杂 SQL、多表 Join、窗口函数 |
| 高并发随机写、计数器 | 全表大范围聚合扫描 |
| 稀疏宽表（几百列只存少数） | 跨行事务、强关系约束 |
| 明细随机回溯 | 需要任意二级索引（得自己建索引表） |

ColumnFamily 建议不超过 2–3 个，因为不同 CF 的 MemStore/Flush/Compaction 是独立的，CF 多了小文件会爆炸。

## ZooKeeper：协调底座

- **ZAB 协议**：Leader + Follower，写请求过半确认才成功；Leader 挂了重新选举。
- **znode**：持久节点、临时节点（会话断开自动删）、顺序节点（自增序号）。
- **watch**：一次性通知，触发后要重新注册。
- **Hadoop HA**：两个 NN 抢同一 znode 锁，谁抢到谁是 Active；ZKFC 监控 NN 健康、自动切换、执行 fencing。
- HBase 也依赖 ZK 存 `hbase:meta` 位置和 Master 选举；Kafka 新版已用 KRaft 替代 ZK。

## 数据集成

| 工具 | 定位 | 现状与建议 |
| --- | --- | --- |
| **Sqoop** | 关系库 ↔ HDFS/Hive 批量导入导出 | 2021 年退役进 Attic，**新项目不要用** |
| **DataX** | 阿里开源，离线批量同步 | 插件丰富、稳定，国内常用 |
| **SeaTunnel** | 批流一体同步引擎 | 新项目优先，支持 CDC、多引擎 |
| **Flink CDC** | 数据库变更实时捕获 | 实时入湖/入仓首选 |
| **Flume** | Agent 采集：source → channel → sink | 逐步被 Filebeat 取代，只做存量 |
| **Kafka** | 消息队列 | 缓冲/削峰，不是长期存储，保留期到了就删 |

```
业务库 ──Flink CDC / DataX──▶ HDFS/Hive（离线）
应用日志 ──Filebeat──▶ Kafka ──Flink/Spark──▶ HDFS/湖仓（实时）
```

## 调度器对比

| | Oozie | Azkaban | DolphinScheduler | Airflow |
| --- | --- | --- | --- | --- |
| 状态 | 已进 Apache Attic | 社区活跃度低 | 国产、活跃 | 全球主流 |
| 定义方式 | XML + workflow.xml | job 文件 + Web | 可视化 DAG | Python DAG |
| 多租户 | 弱 | 弱 | 强 | 中 |
| Hadoop 支持 | 原生 | 原生 | 原生（Spark/Hive/Shell/SQL） | 靠 operator 集成 |
| 适合 | 存量 Hadoop 栈 | 简单依赖 | 国内 Hadoop/数仓团队 | 复杂依赖、云原生、Python 团队 |

**选型建议**：新项目从 DolphinScheduler（中文生态、可视化、Hadoop 任务开箱即用）或 Airflow（Python 化、云原生）里选；Oozie/Azkaban 只做存量维护。

## 统一元数据与安全

- **HCatalog**：早期给 Pig/MR 提供「按表读写 Hive 数据」的抽象，现在角色被 Hive Metastore + Iceberg/Hudi Catalog 取代。
- **统一元数据**：Hive、Spark、Flink、Trino 共用一份表定义，避免「每套引擎各建一张表」。
- **Kerberos**：解决「你是谁」，`kinit` 拿票据，服务用 keytab。
- **Ranger**：解决「你能干什么」，集中管理 HDFS/Hive/HBase/YARN 的表、列、行级策略并输出审计。
- 文件级可叠加 HDFS ACL：`hdfs dfs -setfacl -m user:alice:r-x /data/report`。

## 组件选择速查

| 需求 | 首选 | 备注 |
| --- | --- | --- |
| SQL 数仓 / 报表 | Hive + Tez，或 Spark SQL / Trino | 新项目直接上 Iceberg |
| 毫秒级点查、高并发写 | HBase | RowKey 设计先行 |
| 关系库批量同步 | DataX / SeaTunnel | Sqoop 已退役 |
| 数据库实时入仓 | Flink CDC | 需要湖仓表支持 upsert |
| 日志采集 | Filebeat → Kafka | Flume 只做存量 |
| 工作流调度 | DolphinScheduler / Airflow | 别选 Oozie |
| 协调与选主 | ZooKeeper | K8s 场景可用 etcd |
| 权限与审计 | Kerberos + Ranger | 生产必配 |
| 列式存储 | ORC（Hive）/ Parquet（Spark） | 别用 TextFile 做数仓 |

## 自测

1. Hive 的 Metastore 有哪三种模式？为什么生产必须用远程模式？
2. 内部表和外部表在 `DROP TABLE` 时分别发生什么？举一个必须用外部表的场景。
3. HBase 的写路径经过哪几个结构？为什么写完 WAL 就可以返回成功？
4. 一个业务表 RowKey 是自增 ID，写入全压在一台 RegionServer 上，你怎么改？
5. Sqoop、Oozie 都已退役，各自常用的替代方案是什么？

## 参考与官方文档

- [Apache Hive 官方文档](https://hive.apache.org/)
- [Hive Metastore 管理](https://cwiki.apache.org/confluence/display/Hive/AdminManual+Metastore+Administration)
- [Apache HBase 参考手册](https://hbase.apache.org/book.html)
- [Apache ZooKeeper 概览](https://zookeeper.apache.org/doc/current/zookeeperOver.html)
- [Apache Flume](https://flume.apache.org/) / [Apache DolphinScheduler](https://dolphinscheduler.apache.org/) / [Apache Airflow](https://airflow.apache.org/)
- [Apache Ranger](https://ranger.apache.org/)
