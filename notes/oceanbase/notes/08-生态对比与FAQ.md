# 08 生态对比与 FAQ

## 一句话

选数据库没有银弹。OceanBase 的强项是**金融级强一致 + 原生分布式 + Oracle/MySQL 双兼容 + 多租户整合**；如果只是中小业务、单机够用，MySQL 更简单；如果是纯 OLAP，ClickHouse/StarRocks 更合适。

## 主流分布式数据库对比

| 维度 | OceanBase | TiDB | PolarDB-X | GaussDB | Oracle RAC |
| --- | --- | --- | --- | --- | --- |
| **架构** | shared-nothing + Paxos | shared-nothing + Raft | 计算存储分离 | shared-nothing / 集中式多形态 | 共享存储集群 |
| **兼容性** | MySQL + Oracle 双模式 | MySQL | MySQL | PostgreSQL / Oracle 兼容 | Oracle |
| **强一致** | 是，RPO=0 | 是 | 取决于部署 | 是 | 是 |
| **多租户** | 原生租户隔离 | 较弱 | 较弱 | 有 | 无 |
| **HTAP** | 行存 + 列存 | TiFlash | 有 | 有 | 以 OLTP 为主 |
| **国产化** | 是 | 是 | 是 | 是 | 否 |
| **典型场景** | 金融核心、政务大集中 | 互联网 HTAP | 阿里云生态 | 政企、金融 | 传统核心 |

## 和 OLAP 数据库怎么分工

| 系统 | 定位 | 与 OceanBase 的关系 |
| --- | --- | --- |
| **ClickHouse** | 列式 OLAP，单表聚合极快 | OB 承载交易，CH 承载大屏/日志分析 |
| **StarRocks / Doris** | 实时 OLAP、复杂 JOIN | 同上，适合报表层 |
| **Hive / Spark** | 离线数仓 | OB 数据通过 CDC 同步到数仓 |
| **Kafka** | 消息队列 | 迁移/CDC 链路的缓冲 |
| **Redis** | 缓存/高并发点查 | 放在 OB 前面做缓存 |

常见组合：

```
交易写 OceanBase → CDC/OMS 同步 → Kafka → 数仓/ClickHouse → 报表
```

## 版本与选型

| 项 | 建议 |
| --- | --- |
| **版本** | 生产优先选 LTS 版本（如 4.2/4.3 系列），跟随官方补丁 |
| **部署** | 小规模用 OBD；生产用 OCP；云上用托管服务 |
| **模式** | 新业务优先 MySQL 模式；Oracle 存量迁移用 Oracle 模式 |
| **副本** | 生产 3F 起步；核心系统 5F 或 2F+1A |
| **硬件** | SSD/NVMe、万兆网络、NTP 时钟同步 |

## 典型场景选型

| 场景 | 推荐 |
| --- | --- |
| 银行核心账务 | OceanBase（三副本/五副本）+ OCP + OMS |
| 政务大集中 | OceanBase 多租户整合多个委办局业务 |
| Oracle 替换 | OceanBase Oracle 模式 + OMS 迁移 |
| 互联网高并发交易 | OceanBase MySQL 模式 或 TiDB |
| 实时报表 | ClickHouse / StarRocks（OB 列存可作为补充） |
| 中小业务 | MySQL / PostgreSQL |
| 海量 KV 点查 | HBase / Redis |

## FAQ

**Q1：OceanBase 和 MySQL 最大的区别是什么？**
A：MySQL 是单机数据库（主从只解决高可用，不解决水平扩展）；OceanBase 是原生分布式数据库，分区打散、Paxos 多副本、在线扩容、多租户都是内核能力。

**Q2：Oracle 迁移的工作量主要在哪？**
A：不在数据搬运，而在兼容性改造（PL/SQL、包、DBLink、高级对象）、SQL 调优、业务口径校验和回滚预案。数据迁移有 OMS 工具，通常不是最大瓶颈。

**Q3：OceanBase 单机性能怎么样？**
A：OB 不是「只能靠堆机器」的数据库，单机也有完整的 SQL/事务/存储引擎。但它的价值在三副本、扩展性和多租户；如果只需要单机，MySQL 往往更划算。

**Q4：三副本是不是很浪费存储？**
A：三副本确实带来 3 倍副本开销，但 OB 的编码压缩通常能显著降低单副本体积；也可以用 2F+1A 仲裁副本降低成本。核心系统用空间换可靠性是值得的。

**Q5：OceanBase 支持事务吗？隔离级别是什么？**
A：支持完整的 ACID 事务，默认快照隔离；跨分区事务用两阶段提交，多副本通过 Paxos 保证提交不丢。

**Q6：大事务会有什么问题？**
A：大事务占用内存与日志空间，可能导致超时、回滚变慢、影响其他租户。建议拆批提交，控制单事务行数与耗时。

**Q7：OceanBase 能代替 Redis 吗？**
A：不适合。OB 是关系型数据库，高频 KV 点查、缓存场景仍应使用 Redis；OB 负责持久化与强一致。

**Q8：社区版够用吗？**
A：学习、POC、部分生产场景可以用社区版；关键生产系统要评估企业版能力、商业支持与合规要求。

**Q9：运维需要哪些技能？**
A：SQL 调优、Linux、网络、存储、分布式系统基础；需要会看执行计划、合并状态、副本健康、备份恢复。OCP 能降低门槛，但不能替代原理理解。

**Q10：迁移失败了怎么办？**
A：割接前就要设计回滚：OMS 反向增量、双写、源库只读保留、回滚演练。没有回滚方案的迁移不能上线。

## 学习路线建议

```
01 概述 → 02 架构 → 03 存储 → 04 多租户
   → 05 SQL → 06 运维调优
   → 07 Oracle 迁移（重点）
   → 08 对比与 FAQ
```

如果想快速上手：先跑一个 Docker 单机版，建 MySQL 模式租户，建表、写入、看执行计划；再做一次 Oracle 模式的小表迁移，体会两种模式的差异。

## 自测

1. OceanBase、TiDB、MySQL 各自的定位差异是什么？
2. 什么情况下不应该选 OceanBase？
3. Oracle 迁移项目中最容易被低估的环节是什么？
4. 设计一个「OB 交易 + ClickHouse 报表」的组合链路。

## 参考与官方文档

- [OceanBase 官方文档](https://www.oceanbase.com/docs)
- [OceanBase 与 TiDB 对比（社区文章）](https://www.oceanbase.com/blog)
- [OceanBase 最佳实践](https://www.oceanbase.com/docs/common-oceanbase-database-cn-10000000001692030)
- [OceanBase 社区](https://ask.oceanbase.com/)
- [OceanBase GitHub](https://github.com/oceanbase/oceanbase)
