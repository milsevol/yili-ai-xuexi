# 04 时间语义与 Watermark

## 一句话

Flink 提供三种时间语义：**Event-Time（事件发生的时间）**、**Processing-Time（算子处理的机器时间）**、**Ingestion-Time（数据进入 Flink 的时间）**；生产上**优先 Event-Time**，它靠 **Watermark（水位线）** 推进——Watermark 单调递增，表示「事件时间至少到这里了」，允许一定的乱序容忍度，用来触发窗口、判断迟到。

## 三种时间语义

| 时间类型 | 谁产生 | 例子 | 优点 | 缺点 |
| --- | --- | --- | --- | --- |
| **Event-Time** | 事件本身带的时间戳 | 订单的 `create_time`、日志的 `@timestamp` | 结果可复现；不受机器延迟影响；跨机器有意义 | 需要 Source 提取 timestamp + 生成 Watermark；有状态开销 |
| **Processing-Time** | Flink 算子所在机器的系统时间 | `System.currentTimeMillis()` | 最快、实现最简单；无状态开销 | 结果不可复现；乱序无法处理 |
| **Ingestion-Time** | 数据进入 Flink 的时间 | Source 接收到数据那一刻 | 比 Processing-Time 好一点 | 本质还是机器时间，只是固定在 Source 处 |

> 生产原则：**能用 Event-Time 就不用 Processing-Time**。只有当事件本身没有时间戳、且对精确性不敏感时才退而求 Processing-Time。

## Watermark 原理

Watermark 是一条特殊的记录（`Watermark(t)`），它在数据流中**单调递增**流过每个算子：

- Watermark `t` 表示：**算子已经看到了所有事件时间 ≤ t - 1ms 的数据**
- 窗口 [start, end) 在 Watermark ≥ end 时触发
- Watermark 还用来清理过期状态

```
事件流（时间戳）:  3, 1, 5, 2, 8, 4, 7, 6, 10, 9, ...
                         ↑
                 Watermark w = 8 到达
                 → 窗口 [5, 10) 触发
                 → 晚到的 9 会被丢弃（除非 allowedLateness）
```

### Watermark 生成策略（最常用的两种）

```java
// 1) 固定乱序容忍（最常见）
WatermarkStrategy
    .<Event>forBoundedOutOfOrderness(Duration.ofSeconds(3))  // 最多晚到 3s
    .withTimestampAssigner((event, ts) -> event.getTimestamp());

// 2) 单调递增时间戳（无乱序）
WatermarkStrategy
    .<Event>forMonotonousTimestamps()
    .withTimestampAssigner((event, ts) -> event.getTimestamp());

// 3) 自定义 WatermarkGenerator（复杂场景）
```

### BoundedOutOfOrderness 的含义

`forBoundedOutOfOrderness(Duration.ofSeconds(3))` = 当前见过的**最大事件时间 - 3 秒**。如果最大看到 10:00:10，Watermark = 10:00:07。之后如果再来一条 10:00:08 的数据——Watermark 已经超过了——这就是**迟到数据**。

## Watermark 的传播

Watermark 从 Source 出发，经过算子链：

1. **单并行度 Source**：直接发 Watermark
2. **多并行度 Source**：各 Subtask 独立生成 Watermark
3. **多并行度算子的 Watermark**：来自上游所有并行实例的 Watermark 取**最小值**（`min(upstream_watermarks)`）作为下游推进

```
Source[0]  Watermark w=10
Source[1]  Watermark w=8
Source[2]  Watermark w=12
           ↓ 取 min
keyBy 算子的 Watermark = 8  → 窗口在所有上游都至少到 8 后触发
```

> **为什么取 min？** 因为最慢的那个 Source 还没推进，快的 Source 不能提前触发窗口，否则会丢数据。

## Watermark 与窗口触发

```java
DataStream<Order> orders = env.fromSource(kafkaSource,
    WatermarkStrategy.forBoundedOutOfOrderness(Duration.ofSeconds(5)),
    "kafka-source");

orders
  .keyBy(Order::getUserId)
  .window(TumblingEventTimeWindows.of(Time.minutes(10)))
  .allowedLateness(Time.minutes(2))   // 允许再晚到 2 分钟
  .aggregate(sumOrderAmount);
```

窗口 [10:00, 10:10) 的触发：

1. Watermark 到达 10:10 → **第一次触发**（正常情况）
2. Watermark 到达 10:10 + 2min = 10:12 → **彻底关闭**，之后再来的 10:00~10:10 数据会被丢弃或进侧输出流

## 迟到数据处理

三种策略：

| 策略 | 配置 | 效果 |
| --- | --- | --- |
| 丢弃（默认） | 不设 allowedLateness | Watermark 过了窗口结束就丢 |
| 延迟触发 | `.allowedLateness(Time.minutes(5))` | Watermark 首次到达窗口结束触发一次；之后每到一条迟到数据再触发；直到 Watermark 超过窗口结束 + lateness |
| 侧输出流 | `.sideOutputLateData(lateTag)` | 迟到数据单独进入一个侧输出流，不影响主窗口 |

```java
OutputTag<Order> lateTag = new OutputTag<>("late-orders", Order.class);

orders
  .keyBy(Order::getUserId)
  .window(TumblingEventTimeWindows.of(Time.minutes(10)))
  .allowedLateness(Time.minutes(2))
  .sideOutputLateData(lateTag)   // 迟到数据进侧输出
  .aggregate(...)
  .getSideOutput(lateTag)       // 拿到迟到数据流做补算
  .addSink(...);
```

## Watermark 推进的几个坑

### 坑 1：Source 没数据，Watermark 卡住

场景：Kafka Source 某个 Partition 暂时没数据，对应的 Watermark 不推进，整个下游的 Watermark 被 min 卡住。

解法：

```java
// 周期 Watermark（默认 200ms，可配）
env.getConfig().setAutoWatermarkInterval(200L);
// 但如果没有新事件，Watermark 还是不推进

// 推荐：用 WatermarkStrategy 的 withIdleness 处理空闲 Source
WatermarkStrategy
    .<Event>forBoundedOutOfOrderness(Duration.ofSeconds(3))
    .withTimestampAssigner(...)
    .withIdleness(Duration.ofSeconds(60));  // 60s 没数据视为空闲，Watermark 不参与 min 计算
```

### 坑 2：Timestamp 没赋值或赋成固定值

```java
// 错：忘记 withTimestampAssigner，Watermark 不推进
WatermarkStrategy.forBoundedOutOfOrderness(Duration.ofSeconds(3))

// 对：必须有 timestamp assigner
WatermarkStrategy
    .<Event>forBoundedOutOfOrderness(Duration.ofSeconds(3))
    .withTimestampAssigner((ev, ts) -> ev.getEventTime());
```

### 坑 3：事件时间戳是毫秒还是秒

Flink 内部时间单位是**毫秒**。如果你的 timestamp 是秒级的，必须 `* 1000`：

```java
.withTimestampAssigner((ev, ts) -> ev.getEventTime() * 1000L);
```

## Processing-Time 什么时候用

- 事件没有时间戳（如设备心跳只有「现在」概念）
- 对精确性不敏感（如监控指标采样）
- 需要极低延迟（Event-Time 要等 Watermark，有最小延迟）

```java
// Processing-Time 窗口不需要 Watermark
DataStream<Order> orders = env.fromSource(kafkaSource,
    WatermarkStrategy.noWatermarks(), "kafka-source");

orders
  .keyBy(Order::getUserId)
  .window(TumblingProcessingTimeWindows.of(Time.minutes(5)))
  .sum("amount");
```

## 关键配置

```properties
# 自动 Watermark 间隔
pipeline.auto-watermark-interval: 200ms

# Source 空闲检测
# 代码里 .withIdleness(Duration.ofSeconds(N))
```

## 常见问题

- **Watermark 为什么不是定时器？** 它是一种数据驱动的「进度信号」，不是靠系统时间轮询。这让 Flink 的 Event-Time 结果在任何机器上都一致。
- **多 Source 合流时 Watermark 怎么算？** 取所有上游 Watermark 的最小值。所以合流场景下，慢的那个 Source 会拖累整个 Watermark。
- **allowedLateness 设太大好不好？** 不好。设太大意味着窗口状态会保留很久，吃内存。要结合业务能容忍的迟到时间设。
- **Watermark 一直不推进？** 99% 是 Source 没有新数据 → Watermark 卡住。查 Source 是否空闲；是否有 timestamp assigner。

## 自测

1. 什么是 Watermark？它为什么设计成「单调递增」而不是定时器？
2. 三个 Source 并行度，Watermark 分别 100, 120, 110。下游 keyBy 算子的 Watermark 是多少？为什么？
3. 设 `forBoundedOutOfOrderness(5s)`，当前最大事件时间 = 10:00:20。此时 Watermark = ? 之后再来一条 10:00:16 的事件，它会被当作迟到吗？
4. 用 `.allowedLateness(2min)` + `.sideOutputLateData(lateTag)` 处理 10min 滚动窗口。窗口 [10:00, 10:10) 首次触发在 Watermark = ? 彻底关闭在 Watermark = ?

## 参考与官方文档

- [Event Time 官方文档](https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/event-time/)
- [Watermarking 文档](https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/event-time/generating_watermarks/)
- [Allowed Lateness](https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/window/allowed-lateness/)
