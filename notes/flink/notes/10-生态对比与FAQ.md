# 10 生态对比与 FAQ

## 一句话

**Flink vs Spark 是「实时 vs 批/SQL」，不是谁取代谁**——Flink 吃掉了 Spark Structured Streaming 的实时场景，Spark 在批处理、ML、SQL 生态上仍然强；**Flink CDC vs SeaTunnel 是「流引擎 vs 同步工具」，不是二选一**；**流批一体 vs 湖仓一体是两个独立维度**——Flink SQL 是流批一体的 SQL 层，Iceberg/Hudi/Delta 是湖仓一体的存储层，前者读写后者，组合起来才是现代数仓。

## Flink vs Spark vs Trino vs ClickHouse

| 维度 | Flink | Spark | Trino (Presto) | ClickHouse |
| --- | --- | --- | --- | --- |
| 定位 | 流处理引擎 + SQL | 批 / SQL / ML / 流（Structured Streaming） | **分布式 SQL 查询引擎** | **列式 OLAP 数据库** |
| 处理模式 | 真正的流 + 批（流批一体） | 批 + 微批流 + 交互式 | 交互式 SQL | 列式扫描 |
| 延迟 | ms ~ s 级 | s ~ min 级 | min 级（大查询） | ms ~ s 级 |
| 存储 | 不存；读 Kafka/HDFS/湖仓 | 不存；读 HDFS/湖仓 | 不存；读湖仓/Hive | 自己存（MergeTree） |
| 状态 | 原生 Keyed/Operator State | Offset + RocksDB StateStore | 无 | 无 |
| CDC | 原生 MySQL/PG CDC Source | 无原生；需要 Debezium 等 | 无 | 无 |
| 入湖 | 原生 Iceberg/Hudi Sink | 原生 Iceberg/Hudi | 原生 Iceberg/Hudi | 不适合 |
| 交互式 | 不适合 | 适合（Spark Shell） | **最适合** | 适合（OLAP） |
| ML | 无 | Spark MLlib | 无 | 无 |
| 典型链路 | Kafka → Flink → Iceberg/HBase | HDFS → Spark → 结果表 | Iceberg/Hive → Trino → 报表 | 明细 → CH → 明细查询 |

### 选型决策树

```
你的核心需求是什么？
│
├─ 实时性 < 1s / CDC / 入湖 → Flink
│
├─ T+1 批处理 / ML / 复杂 ETL → Spark
│
├─ 交互式 Ad-Hoc SQL 查询 → Trino + Iceberg
│
└─ 海量明细点查 / OLAP → ClickHouse / Doris / StarRocks
```

## Flink CDC vs SeaTunnel

| 维度 | Flink CDC | SeaTunnel |
| --- | --- | --- |
| 定位 | Flink 生态的 CDC Source（读端） | **独立的同步工具**（Source → Transform → Sink） |
| 底层 | 跑在 Flink 上 | 跑在 Flink / Spark / SeaTunnel Engine 上 |
| 读能力 | MySQL / PG / Oracle / MongoDB / 消息队列 | 更多（MySQL / PG / Oracle / Kafka / HTTP / 等） |
| 写能力 | 依赖 Flink Connector（Kafka / Iceberg / HBase / JDBC） | 自带大量 Sink Connector |
| Schema 变更 | 支持自动演化 | 支持 |
| 数据转换 | 用 Flink SQL / DataStream 做 | SeaTunnel Transform 或 Flink 原生 |
| 适用场景 | 已经有 Flink 作业，加 CDC Source | 需要同步但不想写 Flink 代码的团队 |

**实战搭配**：SeaTunnel 做离线全量同步（简单表复制），Flink CDC 做实时增量 + 入湖 + 清洗聚合。

## Flink on K8s 现状

### 现状总结

| 方面 | 现状 |
| --- | --- |
| **成熟度** | ✅ 生产可用（1.13+ 成熟，1.18+ 完善） |
| **模式** | Application（推荐）、Session、Per-Job（废弃） |
| **资源隔离** | K8s Pod 级隔离，比 YARN 好 |
| **弹性** | 1.17+ 支持 Adaptive Scheduler，TM 可自动扩缩 |
| **外部依赖** | K8s 本身（RBAC、Leader Election、PV/PVC） |
| **监控** | Flink Metrics → Prometheus + Grafana；K8s 自带指标 |
| **缺点** | K8s 运维门槛高；网络开销比 YARN 略大；Kafka 网络访问需 VPC Peering |

### YARN vs K8s 怎么选

| 条件 | 推荐 |
| --- | --- |
| 已有成熟 YARN 集群 + 多租户 | YARN |
| 团队有 K8s 运维能力 + 云环境 | K8s |
| 需要弹性扩缩（夜间自动缩、白天自动扩） | K8s + Adaptive Scheduler |
| 作业多、生命周期短 | K8s Application / YARN Per-Job |
| 同时跑 Spark + Flink + Presto | YARN 或 K8s 都可（Spark on K8s 也成熟了） |

## 流批一体 vs 湖仓一体

**两个独立维度**，不冲突，互相配合：

| 维度 | 含义 | 代表 |
| --- | --- | --- |
| **流批一体** | 同一套 API/SQL 既能做流处理又能做批处理 | Flink SQL / Spark Structured Streaming |
| **湖仓一体** | 同一套存储既能做 OLAP 分析又能做大数据计算 | Iceberg / Hudi / Delta + 对象存储 |

### 组合起来

```
┌─────────────────────────────────────────────────────┐
│  计算层（流批一体）                                    │
│  Flink SQL（流） + Spark SQL（批） + Trino（交互）    │
└────────────────────────┬────────────────────────────┘
                         │ 读写统一的表格式
┌────────────────────────▼────────────────────────────┐
│  存储层（湖仓一体）                                    │
│  Iceberg / Hudi / Delta + S3/HDFS（对象存储）         │
└─────────────────────────────────────────────────────┘
```

- Flink SQL 实时写 Iceberg 表（流）
- Spark SQL 每天跑 T+1 的 ETL 读同一张 Iceberg 表（批）
- Trino 做交互式 Ad-Hoc 查询
- 三者读的是**同一份数据**

## Flink vs Kafka Streams

| 维度 | Flink | Kafka Streams |
| --- | --- | --- |
| 定位 | 分布式流处理引擎（独立集群） | **轻量级嵌入式流库**（跑在应用进程内） |
| 状态存储 | TM 内 RocksDB + Checkpoint 到 HDFS/S3 | Kafka Changelog Topic 备份 |
| 容错 | Checkpoint + 自动重启 | 依赖 Consumer Group Rebalance + Offset |
| 部署 | 独立集群（JM + TM） | 无独立集群，嵌入你的 Java 应用 |
| 复杂度 | 高（集群运维） | 低（应用级） |
| 适用场景 | 大规模流处理（> 100 节点，复杂 State） | 中等规模（< 10 节点，简单 ETL / 规则引擎） |

## 面试高频题

### Q1：Flink 的 Exactly-Once 是怎么实现的？

1. **Checkpoint Barrier 对齐**：Source 注入 Barrier，算子在所有上游 Barrier 都到达后才开始快照，期间缓存数据
2. **状态快照**：所有算子的 Keyed/Operator State 快照持久化到 HDFS/S3
3. **Sink 端事务**：Kafka 0.11+ Producer 两阶段提交（Checkpoint complete 时 commit）
4. **异常恢复**：从最近一次 Checkpoint 恢复状态，重放 Offset

> 注意：Sink 端如果不是事务型（比如写普通 HTTP），即使 Flink 保证了 Exactly-Once，也会有重复。**Sink 必须幂等或支持事务**。

### Q2：Watermark 是怎么推进的？为什么设计成单调递增？

- 从 Source 开始，每条事件携带 timestamp，Source 周期性生成 `Watermark = max_seen_ts - allowed_lateness`
- 多并行度 Source → 下游算子取 min 推进
- 单调递增：窗口触发、状态清理、Timer 触发都依赖 Watermark 的单调推进；如果 Watermark 能倒退，窗口可能反复触发、状态无法清理

### Q3：State 过大怎么办？

1. 换 RocksDBStateBackend（关键）
2. 加 State TTL 清理过期 Key
3. 检查 ListState/MapState 是否无限增长
4. 加 TM 节点 / 加 Managed Memory
5. 检查并行度和 Key Group 分布

### Q4：Flink 和 Spark Streaming 的本质区别？

| | Flink | Spark Streaming |
| --- | --- | --- |
| 底层 | 真正的流（逐条处理） | 微批（批处理引擎上的小批） |
| Watermark | 原生支持 | 2.3+ 才加，支持有限 |
| State | 原生 Keyed/Operator State | Offset + StateStore |
| Event-Time | 一等公民 | 2.3+ 支持 |
| 延迟 | ms 级 | ms ~ s 级 |

### Q5：Operator Chain 的好处和限制？

- **好处**：同线程内方法调用，省序列化、反序列化、网络传输开销
- **限制**：并行度必须相同；中间没有 shuffle 边界；同 SlotSharingGroup；程序员可手动 disable

### Q6：Checkpoint 和 Savepoint 有什么区别？

| | Checkpoint | Savepoint |
| --- | --- | --- |
| 触发 | 周期性自动 | 手动 |
| 元数据 | 最小化 | 完整（算子 ID 映射） |
| 用途 | 故障恢复 | 升级、扩缩、版本迁移 |
| 性能 | 增量、快 | 全量、慢 |

### Q7：为什么 Flink 的 Temporal Join 这么快？

因为它**不保留双流状态**——维表（右表）只保留最新一行，事件流（左表）每来一条直接查维表最新值。和 Regular Join 必须缓存两侧所有元素、等窗口/超时清理相比，状态极小、速度极快。

### Q8：Flink 的并行度和 Slot 数什么关系？

- 总 Slot 数 = max(所有算子的并行度) × SlotSharingGroup 数（简化理解）
- 默认一个作业所有算子属于同一个 SlotSharingGroup → Slot 数 ≥ 最大并行度
- 并行度可在不同算子上分别设置：`.keyBy(...).setParallelism(8)`

## 参考与官方文档

- [Flink 官方 FAQ](https://nightlies.apache.org/flink/flink-docs-stable/qa.html)
- [Flink CDC 项目](https://nightlies.apache.org/flink/flink-cdc-docs-release-3.2/)
- [Kafka Streams vs Flink](https://nightlies.apache.org/flink/flink-docs-stable/concepts/flink-architecture.html)
- [Iceberg 官网](https://iceberg.apache.org/)
