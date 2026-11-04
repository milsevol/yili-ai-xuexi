# Apache HBase

Apache HBase 是建立在 HDFS 之上的**分布式列式 KV 数据库**：它把一张表切成许多 **Region** 分布在 **RegionServer** 上，用 **LSM-Tree** 把随机写性能拉满，再靠 **RowKey** 的有序性做范围扫描。如果说 HDFS 解决的是「海量文件怎么存」，HBase 解决的是「海量记录怎么**随机读写**」——毫秒级点查、每秒百万级写，代价是**必须懂 RowKey 设计、Compaction、Region 分裂**。

> 版本参考：以 **HBase 2.5 / 2.6** 为准（2.5.x 是 2.5 线 LTS，2.6.0 于 2024 年发布、引入 Region 级复制等特性）。示例以 Java 8 API、Shell 与 Python happybase 为主。配套**浏览器可视化交互演示**：HBase vs HDFS vs Hive 对比、架构图、RowKey 热点模拟、LSM-Tree 动画、CRUD 流程、调优计算器、部署建议、排障决策等，打开 `demos/index.html` 即玩，无需集群。

## 先决知识

- 知道 HDFS 的基本概念（块、副本、机架感知）
- 知道 ZooKeeper 是什么（选主、协调、临时节点）
- 会一点 Java 或 Python（读代码示例用），非必须
- 看过 Hadoop 主题的 01–04 章更佳

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位.md) | `./start.sh 01` | HBase vs HDFS vs Hive vs Cassandra 的边界、什么时候选 HBase |
| 2 | [02-架构与组件](./notes/02-架构与组件.md) | `./start.sh 02` | HMaster、RegionServer、ZooKeeper、Region 切分、WAL 架构 |
| 3 | [03-数据模型与RowKey设计](./notes/03-数据模型与RowKey设计.md) | `./start.sh 03` | Table / CF / Qualifier / Cell / Version；RowKey 热点与设计策略 |
| 4 | [04-LSM-Tree与存储原理](./notes/04-LSM-Tree与存储原理.md) | `./start.sh 04` | MemStore → Flush → HFile → Compaction → BloomFilter；读路径覆盖 |
| 5 | [05-API与CRUD实战](./notes/05-API与CRUD实战.md) | `./start.sh 05` | Java API（Put/Get/Delete/Scan/Increment）、Python happybase、批量与 Scan 优化 |
| 6 | [06-Region管理与性能调优](./notes/06-Region管理与性能调优.md) | `./start.sh 06` | Region 分裂策略、Compaction 策略、WAL 配置、热点 Region 打散 |
| 7 | [07-部署与集群规划](./notes/07-部署与集群规划.md) | `./start.sh 07` | HMaster HA、RegionServer 位置、ZooKeeper 数量、JVM/内核参数 |
| 8 | [08-运维监控与故障排查](./notes/08-运维监控与故障排查.md) | `./start.sh 08` | HMaster 切换、RS 宕机、Compaction 阻塞、GC 问题、日志分析 |
| 9 | [09-HBase与周边组件](./notes/09-HBase与周边组件.md) | `./start.sh 09` | HBase vs Cassandra vs RocksDB；Hive/Spark 读写；Phoenix/OpenTSDB/ES 二级索引 |
| 10 | [10-生态对比与FAQ](./notes/10-生态对比与FAQ.md) | `./start.sh 10` | 什么时候选 HBase vs Hive vs ClickHouse；HBase on K8s；面试 FAQ |

建议：01–02 建立架构心智模型（LSM + Region 分片是核心）；03 是 RowKey 设计的主战场，决定了后面性能；04–05 深入存储与 API；06–08 面向生产调优与运维；09–10 面向生态与选型。

## 如何启动演示

```bash
cd notes/hbase
./start.sh          # 打开浏览器交互演示页
./start.sh 03       # 直达第 3 章（RowKey 热点模拟）
./start.sh --cli    # 备用：终端文字摘要
```

也可从仓库根进入：`python3 main.py hbase`。演示为纯 HTML/JS，无需构建、无需集群。

## 本地快速验证（可选）

HBase 支持单机/伪分布式运行，需要 **Linux/macOS、JDK 8 或 11**（2.5/2.6 官方支持 JDK 8/11）、一个 ZooKeeper（自带内置或独立部署），以及已安装的 Hadoop/HDFS。最简单是用 Docker 起一个单机 HBase：

```bash
# 示例思路，镜像以实际发行版为准
docker run -d --name hbase -p 16010:16010 -p 16000:16000 apache/hbase:2.6.0
docker exec -it hbase hbase shell
hbase> create 'test', 'cf'
hbase> put 'test', 'row1', 'cf:name', 'hello'
hbase> get 'test', 'row1'
hbase> scan 'test'
```

Web UI：`http://localhost:16010`（Master）、`http://localhost:16030`（RegionServer 默认）。

> 注意：HBase 强依赖 ZooKeeper。独立部署时至少 3 台 ZK（奇数，2F+1），不要和 RegionServer 混布到同一批机器上。

## 参考与官方文档

- 官方文档（2.5）：https://hbase.apache.org/2.5/book.html
- 官方文档（2.6）：https://hbase.apache.org/2.6/book.html
- HBase 架构概览：https://hbase.apache.org/2.5/book.html#arch.overview
- 性能调优指南：https://hbase.apache.org/2.5/book.html#perf
- GitHub：https://github.com/apache/hbase
- 经典书籍：《HBase 权威指南》（第 3 版，O'Reilly）
