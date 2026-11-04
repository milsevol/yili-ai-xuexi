# 10 生态对比与 FAQ

## 一句话

Kafka 已经成为大数据实时链路的事实标准，但在业务消息、多集群管理、极端延迟等场景仍有替代品。面试高频问题集中在：ISR 机制、Rebalance 语义、Exactly-Once、KRaft 与 ZK 区别。

## 四大消息系统综合对比

| 维度 | Kafka | RocketMQ | Pulsar | RabbitMQ |
| --- | --- | --- | --- | --- |
| 模型 | Topic → Partition（日志） | Topic → Queue | Topic → Partition（分片日志） | Exchange → Queue |
| 吞吐（单节点） | ~1 MB/s | ~500 KB/s | ~1 MB/s | ~100 KB/s |
| 延迟（端到端） | ms~亚秒 | ms~亚秒 | ms~亚秒 | µs~ms |
| 消息保留 | 可配置（永久） | 可配置 | 可配置 | 默认消费完删 |
| 顺序性 | 单 Partition | 单 Queue | 单 Partition | 单 Queue |
| 事务 | Producer 事务 + Consumer 配合 | 半消息 + 回查 | ✅ | ✅ 复杂 |
| 跨地域 | MirrorMaker 2 | 原生 | 原生（Geo） | Shovel |
| 流处理 | Streams API | - | Functions API | - |
| 典型场景 | 大数据链路、CDC、日志 | 业务解耦、延迟消息 | 多租户、流存储 | 业务小量、AMQP |

### 选型总结

```
你是大数据团队，需要 Flink/Spark 生态 →  Kafka
你是电商交易，需要事务、延迟消息 →  RocketMQ
你有多集群/跨地域需求 →  Pulsar
你是小业务，要极低延迟 + AMQP 协议 →  RabbitMQ
```

## KRaft 何时全面替代 ZooKeeper

当前时间点（2026 Q4）：

| 时间 | 状态 |
| --- | --- |
| Kafka 3.5（2023 Q4） | KRaft GA（生产可用） |
| Kafka 3.6（2024 Q1） | KRaft + JBOD/RAID 支持 |
| Kafka 3.7（2024 Q3） | KRaft 生产推荐 |
| Kafka 3.8（2025 Q1） | ZooKeeper mode **deprecated** |
| Kafka 4.0（2025 Q4 计划） | **完全移除 ZooKeeper** |

### 迁移路径

```bash
# Kafka 3.5+ 支持 ZK → KRaft 在线迁移（rolling）
kafka-metadata-quorum.sh --bootstrap-server kafka1:9092 \
  --migrate --feature.level final
```

迁移要点：
1. 先升级所有 Broker 到 3.5+（ZK 模式）
2. 启动 KRaft Controller Quorum（独立 3 节点）
3. 执行 `kafka-metadata-quorum.sh --migrate`
4. Broker 逐步切到 KRaft controller.quorum.voters
5. 最后停 ZooKeeper

## Kafka on K8s 现状

### 主流方案

| 方案 | 维护方 | 特点 |
| --- | --- | --- |
| **Strimzi** | Red Hat / Apache 社区 | 功能最全，KRaft 支持早，社区活跃 |
| **Kafka Operator（Bitnami）** | VMware | Helm Chart 友好，社区版 |
| **Confluent Operator** | Confluent | 商业方案，支持 Control Center 一体化 |
| **Aiven Kafka** | Aiven | 托管服务，不用管 Operator |

### K8s 上的坑

1. **网络延迟**：Pod 间网络比 VM 间略高，但一般可接受；跨 AZ 部署要谨慎
2. **本地盘 vs 云盘**：本地盘快但 Pod 漂移丢数据；云盘安全但慢
3. **LB 暴露**：Producer 在集群外时，NodePort / LoadBalancer 要配置 `advertised.listeners` 正确
4. **KRaft Controller 选举**：K8s 上 Leader Election 可能有网络抖动影响 Raft 心跳
5. **JVM GC 与 CPU limit**：CPU limit 太紧会导致 GC 线程拿不到时间片 → GC 停顿变长 → Consumer Rebalance

## 常见面试题

### 基础篇

**Q1: 为什么 Kafka 吞吐这么高？**
A: ① 磁盘顺序写（追加日志）；② OS PageCache 合并写；③ 零拷贝 sendfile 读；④ 批量发送（Producer batch + Consumer Fetch）；⑤ Partition 并行（横向扩展 Broker 和 Consumer）。

**Q2: ISR 机制是什么？为什么要有 ISR？**
A: ISR（In-Sync Replicas）是当前与 Leader 保持同步的副本集合。Follower 落后超过 `replica.lag.time.max.ms` 被踢出（变 OSR），追上后重新加回。ISR + `min.insync.replicas` 构成了 Kafka 的安全底线：acks=all 只有在 ISR ≥ min.insync.replicas 时才接受写入，保证至少 N 个副本有这条消息。

**Q3: Consumer Rebalance 什么时候触发？Rebalance 期间会发生什么？**
A: 触发：① 新 Consumer 加入；② Consumer 心跳超时；③ Consumer 处理超过 `max.poll.interval.ms`；④ Topic 分区数变化；⑤ Coordinator 切换。期间：Group 暂停消费 → Consumer 重新 JoinGroup → Leader 分配 Partition → SyncGroup → 恢复消费。Rebalance 间隔是不可避免的性能损失，所以要调大 max.poll.interval.ms、优化 GC。

**Q4: Kafka 如何保证 Exactly-Once 语义？**
A: ① Producer：开启幂等（`enable.idempotence=true`）+ 事务（`transactional.id` + 跨 Topic 原子提交）。② Consumer：`isolation.level=read_committed` 只读已提交事务，处理完业务后手动 commitSync offset。③ 外部系统：需要业务侧幂等（唯一 ID + 去重），因为 Kafka 管不了外部 DB。Kafka 自己保证的是**Kafka 内部跨 Partition、跨 Topic 的 Exactly-Once**（EOS v2）。

### 进阶篇

**Q5: Broker 宕机后，Partition 怎么恢复？**
A: ① Controller 检测到 Broker 下线（ZK Watch / KRaft Raft）；② 该 Broker 上所有 Partition 的 Leader 从剩余 ISR 里选新 Leader；③ Follower 从新 Leader 继续同步；④ 原 Broker 重启后，追上新 Leader 的日志 → 重新加入 ISR；⑤ Controller 可能触发 PreferReplicaLeaderElection 把 Leader 还回去。

**Q6: 为什么 Kafka 的消息能百万级/s？单 Partition 的理论上限是多少？**
A: 百万级是因为多 Partition 并行。单 Partition 的上限约 **50-100 MB/s**（磁盘顺序写能力 + 网络带宽）。所以吞吐 = Partition 数 × 单 Partition 能力。Broker 上 Partition 太多反而会增加 Controller 压力和 ISR 同步风暴。

**Q7: KRaft 比 ZooKeeper 好在哪里？**
A: ① 少一个外部组件，运维成本减半；② 元数据存取更快（本地 Raft log vs ZK RPC）；③ 支持更大集群（百万级 Partition vs ZK 的 20-30K）；④ Controller 切换更快（Raft vs ZK Watch）；⑤ 4.0 将彻底移除 ZK。

**Q8: 为什么 Kafka 不支持减少 Topic 分区数？**
A: 分区是 Topic 的并行度和顺序性的基本单位，key → partition 的映射是 `hash(key) % numPartitions`。如果减分区，这个映射会大变，下游 Consumer Group 重新 Rebalance 后，同一个 key 的数据会跑到不同 Partition，消费顺序被打乱。Kafka 作者认为这是一个破坏性变更，所以不支持。

**Q9: `acks=all` 到底是什么安全级别？会不会丢数据？**
A: acks=all 要求 ISR 所有副本都 sync 到这条消息。但 ISR 本身可能只剩 Leader 一个副本（其他 Follower 落后被踢），此时 acks=all 就退化到 acks=1。要真正安全，必须配 `min.insync.replicas=2`（replication.factor=3）。这样只要 ISR ≥ 2，acks=all 才接受写入。如果 ISR < min.insync.replicas，Broker 直接返回 NOT_ENOUGH_REPLICAS，拒绝写入——**这是硬拒绝，不是静默接受**。

**Q10: 生产环境 Kafka 怎么规划 Partition 数？**
A: ① 先按业务吞吐量需求倒推：Consumer Group 最大并行消费数 → Partition 数；② 再按写入带宽：QPS × 消息大小 ÷ 单 Partition 目标 QPS（~5000 QPS）；③ 加 30-50% 余量（业务增长 + 临时扩容）；④ 注意 Partition 只能增不能减，宁多勿少。

### 设计篇

**Q11: 如果让你设计一个「比 Kafka 更适合多租户」的消息系统，你会做什么？**
A: 参考 Pulsar + Pulsar Functions：① Broker 无状态 + BookKeeper 分布式存储（容易扩容）；② 原生多租户命名空间隔离；③ 跨地域 Geo-Replication；④ Functions API 内置轻量流处理；⑤ 分层存储（热数据本地盘 + 冷数据对象存储）。

**Q12: Kafka 为什么要用追加日志而不是随机写？**
A: 磁盘顺序写比随机写快一个数量级（HDD 尤其明显）。追加日志（Append-Only Log）天然就是顺序写，OS PageCache 可以高效合并这些写。读的时候，追加日志 + 稀疏索引可以快速定位 offset + 零拷贝 sendfile 返回，也是极致高效。

## 学习资源推荐

| 类型 | 推荐 |
| --- | --- |
| 官方文档 | https://kafka.apache.org/documentation/ |
| 书籍 | 《Kafka 权威指南 第 2 版》《Kafka 内核设计与实现》 |
| 博客 | Jay Kreps（LinkedIn Kafka 创造者）的 Confluent 博客 |
| 源码阅读 | github.com/apache/kafka（推荐从 clients 模块 Producer/Consumer 开始） |
| 视频 | ApacheCon 历年 Kafka 专场 |

## 自测

1. 对比 Kafka、RocketMQ、Pulsar、RabbitMQ 四种产品的适用场景。
2. KRaft 替代 ZooKeeper 的时间表是什么？有哪些好处？
3. Kafka on K8s 的主流方案有哪些？主要坑是什么？
4. 从面试高频题里选一道你最想展开讲讲的。

## 参考与官方文档

- [Kafka 4.0 Roadmap](https://cwiki.apache.org/confluence/display/KAFKA/Kafka+4.0+Roadmap)
- [Pulsar vs Kafka 对比](https://pulsar.apache.org/docs/next/comparison/)
- [Strimzi 官网](https://strimzi.io/)
- [Jay Kreps 博客](https://www.confluent.io/blog/)
