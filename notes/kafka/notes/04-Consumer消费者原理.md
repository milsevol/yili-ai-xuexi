# 04 Consumer 消费者原理

## 一句话

Consumer 是**拉模式**：自己定期从 Broker Fetch 一批消息，处理完后自己决定什么时候提交 Offset。Consumer Group 内，每个 Partition 只能被一个 Consumer 消费；Consumer 挂了或扩容时触发 **Rebalance**，把 Partition 重新分配给活着的 Consumer。

## 完整消费流程

```
Consumer.poll(timeout)
  │
  ├─ 1. 确保已 subscribe / assign
  │     ├─ subscribe(Pattern)  → 自动进 Consumer Group，走 ConsumerCoordinator
  │     └─ assign(TopicPartition[]) → 手动分配，不进 Group，自己管 Offset
  │
  ├─ 2. ConsumerCoordinator 心跳
  │     └─ 向 Group Coordinator（Broker）定期发 Heartbeat（heartbeat.interval.ms）
  │        Coordinator 维护 Group 成员列表，决定谁做 Group Leader
  │
  ├─ 3. Group Leader 做 Partition 分配
  │     └─ 调用 PartitionAssignor（Range / RoundRobin / Sticky）
  │        把 TopicPartitions → Group 内 Consumer
  │        把分配方案通过 JoinGroupResponse 下发
  │
  ├─ 4. 启动 Fetch 线程（Fetcher）
  │     └─ 对每个分配到的 Partition，从上次 commit 的 offset 开始拉
  │        FetchRequest 可一次拉多个 Partition，批量网络 IO
  │
  ├─ 5. Consumer 处理拉到的 ConsumerRecords
  │     └─ 业务逻辑：写库、调用下游、聚合……
  │
  └─ 6. 提交 Offset
        ├─ enable.auto.commit=true → poll() 间隔自动提交
        └─ enable.auto.commit=false → commitSync()/commitAsync() 手动提交
```

## Rebalance：触发与问题

Rebalance = Consumer Group 里成员变化 → 重新分配 Partition。

| 触发条件 | 典型场景 |
| --- | --- |
| 新 Consumer 加入 Group | 扩容 |
| 旧 Consumer 离开 Group | 进程正常退出（leaveGroup） |
| Consumer 心跳超时 | 进程 OOM/崩溃/网络分区 → Coordinator 判定它死了 |
| Consumer 处理太慢超过 `max.poll.interval.ms` | 业务逻辑耗时太长，Broker 认为它卡死了 |
| Topic 分区数变化 | 新增分区（减分区不支持） |
| Coordinator 自己挂了 | 整个 Group 重新 Join |

**Rebalance 的问题**：
1. **期间 Group 停止消费**：Rebalance 从 JoinGroup → SyncGroup → 每个 Consumer 重新拉 offset 开始，可能几秒到几十秒。
2. **可能重复消费**：Rebalance 时如果上一个 Consumer 的 offset 还没 commit，新 Consumer 会从上上一次 commit 的位置拉 → 重复处理。
3. **可能丢消费**：极端情况（比如 `auto.commit.interval.ms` 太频繁、业务逻辑在 commit 前崩了）。

### Rebalance 协议（Kafka 3.0+ 改进）

老版本 Rebalance 流程：JoinGroup → 等待 Leader 分配 → SyncGroup。
3.0+ 引入 **Incremental Cooperative Rebalance**，允许**渐进式迁移 Partition**，不必停整个 Group。

## Partition 分配策略

| 策略 | 行为 | 适用场景 |
| --- | --- | --- |
| **RangeAssignor**（默认） | 每个 Topic 的 Partitions 按 Range 分配给 Consumer | 同一 Topic 多 Consumer，简单均匀 |
| **RoundRobinAssignor** | 跨 Topic 轮询分配 | 多 Topic 混合消费，想让每个 Consumer 均衡拿各个 Topic 的 Partition |
| **StickyAssignor** | 尽量保持原有分配，Rebalance 时只迁移最少的 Partition | Rebalance 时最小化中断，3.0+ 推荐 |
| **CooperativeStickyAssignor** | Sticky + 渐进式迁移 | 配合 Cooperative Rebalance，最优体验 |

## 消费语义：At-Most / At-Least / Exactly-Once

| 语义 | 含义 | 怎么做到 |
| --- | --- | --- |
| **At-Most-Once** | 可能丢，不重复 | 先 commit offset 再处理业务 |
| **At-Least-Once** | 不丢，可能重复 | 先处理业务再 commit offset |
| **Exactly-Once** | 不丢不重 | Consumer + Producer 事务（`isolation.level=read_committed`）+ 幂等下游 |

```
At-Most-Once:  poll() → commitSync() → 处理
                          ↑
               崩了 → 跳过消息，丢了

At-Least-Once: poll() → 处理 → commitSync()
                              ↑
               崩了 → 上次没 commit，重启后 re-pull → 重复

Exactly-Once:  poll() → producer.beginTransaction()
               ├─ 写 Kafka（事务内）→ producer.commitTransaction()
               └─ 写外部系统 → 用 2PC / 幂等
               最后 consumer 自己 commit offset
```

**⚠️ 现实中 Exactly-Once 很难**：因为 Consumer 处理完外部系统（DB/ES/HTTP）之后、还没 commit offset 之前崩了，重启后会重复处理 → 外部系统不是事务性的，幂等只能靠业务侧保证（比如每条消息一个业务唯一 ID + 去重表）。

## 提交策略

| 策略 | 做法 | 优缺点 |
| --- | --- | --- |
| 自动提交 | `enable.auto.commit=true`，每 `auto.commit.interval.ms`（默认 5s）提交一次 | 简单，但可能重复或丢 |
| 手动同步提交 | `commitSync()` 处理完一条/一批后调用 | 保证 At-Least-Once，但每批一次同步 IO |
| 手动异步提交 | `commitAsync(callback)` 不阻塞 | 高吞吐，但失败需要重试 |
| 批量 + 偏移提交 | `commitSync(Map<TopicPartition, OffsetAndMetadata>)` | 控制粒度最细 |

**生产推荐**：`enable.auto.commit=false` + **手动同步/异步提交** + **业务侧幂等**。

## 关键配置

| 配置 | 默认 | 含义 | 调优建议 |
| --- | --- | --- | --- |
| `bootstrap.servers` | — | Broker 列表 | 至少写 3 个 |
| `group.id` | — | Consumer Group ID | 固定，重平衡/offset 都按它 |
| `enable.auto.commit` | true | 自动提交 | 生产设 false |
| `auto.commit.interval.ms` | 5000 | 自动提交间隔 | 自动模式下生效 |
| `auto.offset.reset` | latest | 首次没有 offset 时 | 设 earliest 补数据；latest 只收新数据 |
| `fetch.min.bytes` | 1 | 最小拉取字节数 | 攒批，高吞吐设 65536 |
| `fetch.max.bytes` | 52428800 | 单次 Fetch 上限 | 跟 Broker `max.partition.fetch.bytes` 配合 |
| `max.poll.records` | 500 | 单次 poll() 最多返回条数 | 业务慢时调小，避免超时 |
| `max.poll.interval.ms` | 300000 | poll() 间隔上限 | 业务真的慢就调大，否则触发 Rebalance |
| `session.timeout.ms` | 45000 | Group 会话超时 | 心跳 * 3 左右 |
| `heartbeat.interval.ms` | 3000 | 心跳间隔 | session.timeout 的 1/3 |
| `partition.assignment.strategy` | RangeAssignor | 分配策略 | 生产用 Sticky 或 CooperativeSticky |
| `isolation.level` | read_uncommitted | 读已提交/未提交 | 需要事务用 read_committed |

## 代码示例（Java）

```java
Properties props = new Properties();
props.put("bootstrap.servers", "kafka1:9092,kafka2:9092,kafka3:9092");
props.put("group.id", "demo-group");
props.put("key.deserializer", "org.apache.kafka.common.serialization.StringDeserializer");
props.put("value.deserializer", "org.apache.kafka.common.serialization.StringDeserializer");
props.put("enable.auto.commit", "false");           // 手动提交
props.put("auto.offset.reset", "earliest");

KafkaConsumer<String, String> consumer = new KafkaConsumer<>(props);
consumer.subscribe(Arrays.asList("demo"));

try {
    while (true) {
        ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(100));
        for (ConsumerRecord<String, String> r : records) {
            // 业务处理：写 DB / 调下游 / 聚合
            System.out.printf("partition=%d offset=%d key=%s value=%s%n",
                r.partition(), r.offset(), r.key(), r.value());
        }
        consumer.commitSync(); // 手动同步提交，At-Least-Once
    }
} finally {
    consumer.close();
}
```

## 常见问题

**Q: subscribe 和 assign 有什么区别？**
A: `subscribe` 进 Consumer Group，走 Rebalance 协议，offset 由 Broker 存（__consumer_offsets）。`assign` 不进 Group，自己手动指定 Partition，Offset 自己管（或也可以 commit 到 Broker，但没人帮你 Rebalance）。

**Q: 为什么我的 Consumer 一直在 Rebalance？**
A: 常见原因：① 业务处理太慢，超过 `max.poll.interval.ms`；② GC 停顿导致心跳没发出；③ 网络抖动；④ 同时起了多个同 `group.id` 的进程互相打架。排查：看 Coordinator 日志 + Consumer 端的 Rebalance 日志。

**Q: 如何优雅关闭 Consumer？**
A: 收到 SIGTERM/SIGINT 时，在业务逻辑当前批次处理完 → `consumer.wakeup()` 让 poll 抛 WakeupException → 在 finally 里 `commitSync()` + `close()`。这样不会丢最后一批。

## 自测

1. 描述 poll() → Fetch → 提交 offset 的完整链路。
2. 三种分配策略各适合什么场景？生产推荐哪种？
3. At-Most-Once / At-Least-Once / Exactly-Once 分别怎么做？
4. Consumer 频繁 Rebalance 最可能的三个原因是什么？

## 参考与官方文档

- [Consumer 配置官方文档](https://kafka.apache.org/documentation/#consumerconfigs)
- [Kafka 消费语义](https://kafka.apache.org/documentation/#semantics)
- [Rebalance 协议改进](https://cwiki.apache.org/confluence/display/KAFKA/KIP-429%3A+Kafka+Consumer+Incremental+Rebalance+Protocol)
