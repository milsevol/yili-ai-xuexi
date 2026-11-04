# Apache HBase

Apache HBase 是建立在 HDFS 之上的分布式列式 KV 数据库：毫秒级点查、每秒百万级写，靠 RowKey 的有序性做范围扫描。本主题用中文笔记 + **浏览器可视化交互演示**，梳理「是什么 → 怎么存 → 怎么查 → 怎么调 → 怎么运维」的完整链路。

> 版本参考：HBase 2.5 / 2.6。演示不连接真实集群；默认打开 `demos/index.html`。

## 先决知识

- HDFS 基本概念（块、副本、机架感知）
- ZooKeeper 是什么（选主、协调）
- 会一点 Java 或 Python 更佳，非必须

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位) | `./start.sh 01` | HBase vs HDFS vs Hive vs Cassandra 边界 |
| 2 | [02-架构与组件](./notes/02-架构与组件) | `./start.sh 02` | HMaster、RegionServer、WAL、Region 切分 |
| 3 | [03-数据模型与 RowKey 设计](./notes/03-数据模型与RowKey设计) | `./start.sh 03` | RowKey 热点与设计策略：加盐/哈希/反转 |
| 4 | [04-LSM-Tree 与存储原理](./notes/04-LSM-Tree与存储原理) | `./start.sh 04` | MemStore→Flush→HFile→Compaction 动画 |
| 5 | [05-API 与 CRUD 实战](./notes/05-API与CRUD实战) | `./start.sh 05` | Java API + Python happybase + Scan 优化 |
| 6 | [06-Region 管理与性能调优](./notes/06-Region管理与性能调优) | `./start.sh 06` | Compaction 策略、Region 分裂、热点打散 |
| 7 | [07-部署与集群规划](./notes/07-部署与集群规划) | `./start.sh 07` | HMaster HA、ZK 数量、JVM/内核参数 |
| 8 | [08-运维监控与故障排查](./notes/08-运维监控与故障排查) | `./start.sh 08` | HMaster 切换、RS 宕机、Compaction 阻塞 |
| 9 | [09-HBase 与周边组件](./notes/09-HBase与周边组件) | `./start.sh 09` | HBase vs Cassandra vs ClickHouse；Spark 读写 |
| 10 | [10-生态对比与 FAQ](./notes/10-生态对比与FAQ) | `./start.sh 10` | 选型决策 + 面试 FAQ |

## 如何启动演示

```bash
cd notes/hbase
./start.sh          # 浏览器可视化交互
./start.sh 03       # 直达 RowKey 热点模拟
./start.sh --cli    # 备用终端文字版
```

也可：`python3 main.py hbase` / `python3 main.py hbase 03`。

## 参考与官方文档

- [HBase 2.5 官方文档](https://hbase.apache.org/2.5/book.html)
- [HBase 2.6 官方文档](https://hbase.apache.org/2.6/book.html)
- [HBase 架构概览](https://hbase.apache.org/2.5/book.html#arch.overview)
- [GitHub](https://github.com/apache/hbase)
