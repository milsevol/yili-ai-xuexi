# 03 Producer 生产者原理

## 一句话

Producer 发送流程：**拦截器 → 序列化 → 分片器 → ProducerRecord 进入 RecordAccumulator（累加器）→ 攒够一批由 Sender 线程批量发给 Broker**。Broker 返回 ack，Producer 根据 `acks` 配置和错误码决定重试还是抛异常。

## 完整发送流程

```
Producer.send(record)
  │
  ├─ 1. ProducerInterceptor.onSend()       ← 可选拦截器（打日志、加 header）
  │
  ├─ 2. Serializer.serialize()             ← 把 key/value 序列化成 byte[]
  │
  ├─ 3. Partitioner.partition()            ← 决定目标 Partition
  │
  ├─ 4. 算 Cluster → 目标 Broker            ← 从 metadata 拿 Partition Leader 在哪台
  │
  ├─ 5. 进 RecordAccumulator               ← 按 (Broker, Partition) 分组进批次
  │     └─ 如果该 Broker/Partition 已有批次 → 追加；否则新建 RecordBatch
  │
  ├─ 6. Sender 线程                        ← 后台线程，从 accumulator 拿满/超时的批次
  │     ├─ 构建 ClientRequest（含 header + batch payload）
  │     ├─ 走 NIO channel 批量发送到 Broker
  │     └─ 收 Response，按 acks 处理
  │
  └─ 7. 回调 CompletableFuture              ← send() 返回的 Future.complete / completeExceptionally
```

**批处理是 Kafka 吞吐的根本**：单条消息 send() 并不立即发出去，而是进 accumulator，直到：
- 该 partition 的 batch 满了（`batch.size`，默认 16KB），或
- `linger.ms`（默认 0）到了（为 0 就立刻发），或
- accumulator 内存满了（`buffer.memory`，默认 32MB），阻塞等待。

## acks 三种模式

| acks | Broker 行为 | 语义 | 性能 |
| --- | --- | --- | --- |
| **0** | Leader 收到就返回，不等落盘也不等 ISR | 可能丢（Leader 写一半挂了就没了） | 最高 |
| **1** | Leader 落盘后返回 | Leader 挂了、Follower 还没 sync → 丢（常见） | 中 |
| **all** | Leader 落盘 + ISR 全部 sync 完返回 | 只要 ISR ≥ min.insync.replicas，基本不丢 | 最低 |

**⚠️ 生产建议**：`acks=all` + `min.insync.replicas=2` + `replication.factor=3`。此时即使挂一个 Broker（只剩 Leader+1 个 Follower），仍然可以接受；挂两个 Broker 只剩 Leader 时，acks=all 会拒绝写入（返回 NOT_ENOUGH_REPLICAS），这是安全策略。

## 重试与幂等

### 重试

`retries`（默认 2147483647）控制 Producer 对哪些错误重试：

| 错误类型 | 重试？ | 示例 |
| --- | --- | --- |
| 可重试 | ✅ | 网络超时、NOT_LEADER_OR_FOLLOWER、BROKER_NOT_AVAILABLE、REQUEST_TIMED_OUT |
| 不可重试 | ❌ | RECORD_TOO_LARGE（单条 > max.message.bytes）、INVALID_REQUIRED_ACKS（Broker 不支持）、TOPIC_AUTHORIZATION_FAILED |

重试期间要注意**重试放大**：Broker 抖动时会产生大量重复请求。建议配合 `delivery.timeout.ms`（默认 120000）做硬超时。

### 幂等 Producer

```properties
enable.idempotence=true        # 自动 acks=all、retries=MAX、max.in.flight.requests.per.connection≤5
```

幂等 = **同一条消息多次发送，Broker 只落一次**。原理：Producer 启动时向 Broker 申请一个 PID（Producer ID）+ 有序的序列号 SeqNo。Broker 收到 (PID, Partition, SeqNo) 后，若是重复就丢弃、不返回错误。

**幂等的边界**：只能保证**单 Partition 内、单 Producer 会话内**不重复。跨 Producer 实例做不到——需要**事务**。

### 事务 Producer

```java
producer.initTransactions();
producer.beginTransaction();
try {
    producer.send(orderMsg);     // Topic: order
    producer.send(inventoryMsg); // Topic: inventory
    producer.commitTransaction();
} catch (Exception e) {
    producer.abortTransaction();
}
```

事务保证**原子性**：要么 order 和 inventory 两个 Partition 都写成功，要么都回滚。配合 `isolation.level=read_committed` 的 Consumer 可以只读到已提交的事务消息。

## 关键配置

| 配置 | 默认 | 含义 | 调优建议 |
| --- | --- | --- | --- |
| `acks` | 1 | 安全等级 | 生产用 all |
| `retries` | 2147483647 | 可重试错误次数 | 保留默认，配合 delivery.timeout.ms |
| `batch.size` | 16384 | 单批次最大字节数 | 消息大就调大，内存会涨 |
| `linger.ms` | 0 | 攒批等待时间 | 非 0 才会攒批，高吞吐调 10~100ms |
| `buffer.memory` | 33554432 | accumulator 总内存 | 高并发生产调 64~128MB |
| `compression.type` | none | 压缩算法 | 推荐 lz4（快）或 zstd（压缩率高） |
| `enable.idempotence` | false | 开启幂等 | 生产强烈建议开启 |
| `transactional.id` | null | 跨进程恢复事务 ID | 做 Exactly-Once 时用固定值 |
| `max.in.flight.requests.per.connection` | 5 | 飞行中请求数 | 幂等时 ≤5 才能保证顺序；非幂等可到 10 |
| `delivery.timeout.ms` | 120000 | 总发送超时 | 建议 ≥ linger.ms + request.timeout.ms |
| `request.timeout.ms` | 45000 | 单次请求超时 | 不要大于 Broker 的 socket.request.timeout.ms |

## 代码示例（Java）

```java
Properties props = new Properties();
props.put("bootstrap.servers", "kafka1:9092,kafka2:9092,kafka3:9092");
props.put("key.serializer", "org.apache.kafka.common.serialization.StringSerializer");
props.put("value.serializer", "org.apache.kafka.common.serialization.StringSerializer");
props.put("acks", "all");
props.put("retries", 3);
props.put("enable.idempotence", "true");
props.put("compression.type", "lz4");

Producer<String, String> producer = new KafkaProducer<>(props);
for (int i = 0; i < 1000; i++) {
    producer.send(new ProducerRecord<>("demo", "key-" + i, "value-" + i),
        (meta, ex) -> {
            if (ex == null)
                System.out.printf("topic=%s partition=%d offset=%d%n",
                    meta.topic(), meta.partition(), meta.offset());
            else
                ex.printStackTrace();
        });
}
producer.flush();
producer.close();
```

## 常见问题

**Q: RecordTooLargeException 怎么办？**
A: Producer 端调 `max.request.size`，Broker 端调 `max.message.bytes`（默认 1MB）。但真正的解法是**消息不要这么大**——大消息会吃掉网络、拖慢其他批次、破坏批处理效果。建议拆小或用引用（存大对象进 HDFS/对象存储，Kafka 只发路径）。

**Q: 幂等 Producer 为什么要限制 in.flight.requests ≤ 5？**
A: 因为 Broker 要按 SeqNo 去重。如果并发请求数超过 5 且中间有重试，可能把 SeqNo 的天然顺序打乱，导致错误去重。Kafka 3.0+ 对幂等 Producer 自动强约束。

## 自测

1. 描述 Producer 发送流程中 accumulator 和 Sender 线程的分工。
2. acks=0 / 1 / all 的区别分别是啥？生产上应该用哪个，为什么？
3. 幂等 Producer 和事务 Producer 分别解决什么问题？边界在哪里？
4. RecordTooLargeException 从何而来，除了调大配置还有什么解法？

## 参考与官方文档

- [Producer 配置官方文档](https://kafka.apache.org/documentation/#producerconfigs)
- [Kafka 幂等与事务](https://kafka.apache.org/documentation/#semantics)
- [RecordAccumulator 源码](https://github.com/apache/kafka/blob/trunk/clients/src/main/java/org/apache/kafka/clients/producer/internals/RecordAccumulator.java)
