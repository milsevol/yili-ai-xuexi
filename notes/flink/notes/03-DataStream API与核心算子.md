# 03 DataStream API 与核心算子

## 一句话

**Flink DataStream API** 把数据处理分成 **Source（读入）→ Transformation（转换）→ Sink（写出）** 三个阶段；日常 80% 的需求用 `map/flatMap/filter/keyBy/process/window/join` 就能覆盖；复杂逻辑（Timer、广播状态、异步回调）要上 **ProcessFunction / KeyedProcessFunction**；遇到高延迟 IO（HTTP、RPC）要用 **AsyncDataStream** 防止背压整个作业。

## API 分层

```
                  ┌─────────────────────────┐
                  │   Flink SQL / Table API │   ← 声明式，推荐，Flink 官方主推
                  │    (StreamTableEnvironment)│
                  └──────────┬──────────────┘
                             │ toDataStream() / fromDataStream()
                  ┌──────────▼──────────────┐
                  │    DataStream API         │   ← 命令式，本讲重点
                  │  (ProcessFunction 最灵活)   │
                  └──────────┬──────────────┘
                             │
                  ┌──────────▼──────────────┐
                  │  底层算子 / 状态 / 时间     │
                  └─────────────────────────┘
```

建议：能用 Flink SQL 就不用 DataStream；需要精细控制（Timer、自定义状态、广播）时才上 DataStream。

## Source 怎么来

Flink 1.12+ 推荐用 **Source API（FLIP-27）** 而不是旧的 `SourceFunction`：

```java
// 新 Source API（推荐）
DataStream<String> kafkaSource = env.fromSource(
    KafkaSource.<String>builder()
        .setBootstrapServers("kafka:9092")
        .setTopics("events")
        .setGroupId("g1")
        .setStartingOffsets(OffsetsInitializer.latest())
        .setValueOnlyDeserializer(new SimpleStringSchema())
        .build(),
    WatermarkStrategy.forBoundedOutOfOrderness(Duration.ofSeconds(3)),
    "kafka-source"
);

// 文件源
DataStream<String> fileSource = env.fromSource(
    FileSource.forRecordStreamFormat(
        new TextLineInputFormat(),
        new Path("hdfs:///path/to/file")
    ).build(),
    WatermarkStrategy.noWatermarks(),
    "file-source"
);
```

## Transformation 算子速查

| 算子 | 输入 | 输出 | 特点 | 典型场景 |
| --- | --- | --- | --- | --- |
| **map** | 1 条 | 1 条 | 一对一映射 | 字段提取、类型转换 |
| **flatMap** | 1 条 | 0 ~ N 条 | 一对多/多对一 | 拆分日志、展开数组 |
| **filter** | 1 条 | 0 或 1 条 | 过滤 | 只保留异常数据 |
| **keyBy** | DataStream | KeyedStream | **hash shuffle** 同 Key 到同一 Subtask | 所有按 Key 聚合的前置 |
| **process** | KeyedStream → 任意 | ProcessFunction | 最灵活：状态 + Timer + 侧输出流 | 复杂状态机、窗口替代 |
| **sum / min / max** | KeyedStream | DataStream | 滚动聚合 | 简单计数器 |
| **reduce** | KeyedStream | DataStream | 滚动规约 | 自定义聚合 |
| **window** | KeyedStream → WindowedStream | 聚合 | 窗口内聚合 | 定时/会话窗口统计 |
| **join** | 两个 DataStream | JoinStream | 双流 Join | 订单 + 支付关联 |
| **connect** | 两个 DataStream | ConnectedStream | 双流同算子处理 | 主数据流 + 广播配置流 |

### 示例：电商订单分析

```java
DataStream<Order> orders = env.fromSource(orderSource, ...);

orders
  .filter(o -> o.getAmount() > 0)                // 过滤非法订单
  .map(o -> new OrderItem(o.getUserId(), o.getProductId(), o.getAmount()))
  .keyBy(OrderItem::getUserId)                   // 按用户分组
  .window(TumblingEventTimeWindows.of(Time.minutes(5)))
  .aggregate(new SumAggregator<>(), new WindowResultFunction<>())
  .addSink(new PrintSink<>());
```

## ProcessFunction vs KeyedProcessFunction

**ProcessFunction** 是 DataStream API 的瑞士军刀：

| 类 | 适用场景 | 特点 |
| --- | --- | --- |
| **ProcessFunction** | 非 KeyedStream 的转换 | 无 Keyed State，无 Timer |
| **KeyedProcessFunction<K, I, O>** | KeyedStream 的转换 | 有 **Keyed State** + **Timer** + **侧输出流** |
| **CoProcessFunction** | 双流 connect 后 | 两个 `processElement1/2` |
| **KeyedBroadcastProcessFunction** | connect 广播状态 | 处理广播配置更新 |

### KeyedProcessFunction 模板

```java
public class MyProcessFunction extends KeyedProcessFunction<String, Event, Result> {

    private ValueState<Long> countState;
    private ListState<Event> bufferState;

    @Override
    public void open(Configuration parameters) {
        countState = getRuntimeContext().getState(new ValueStateDescriptor<>("count", Long.class));
        bufferState = getRuntimeContext().getListState(new ListStateDescriptor<>("buf", Event.class));
    }

    @Override
    public void processElement(Event value, Context ctx, Collector<Result> out) throws Exception {
        Long count = countState.value() == null ? 0L : countState.value();
        countState.update(count + 1);

        // 注册一个定时器（在当前事件时间 + 1 分钟后触发）
        ctx.timerService().registerEventTimeTimer(value.getTs() + 60_000L);

        // 侧输出流
        ctx.output(slowTag, value);

        out.collect(new Result(value.getKey(), count));
    }

    @Override
    public void onTimer(long timestamp, OnTimerContext ctx, Collector<Result> out) {
        // 定时器触发：做窗口收尾、超时清理等
        out.collect(new Result(ctx.getCurrentKey(), -1L));
    }
}
```

> **关键**：Timer 和 Keyed State 绑定，每个 Key 独立。Timer 只有在 Watermark 超过触发时间时才触发。

## 异步 IO（AsyncDataStream）

当你的算子里有**高延迟 IO**（HTTP RPC、Redis GET、HBase 点查）时，同步调会阻塞整个算子，导致吞吐急剧下降。用 **AsyncDataStream**：

```java
// 定义一个异步 IO 函数
AsyncFunction<Order, EnrichedOrder> asyncLookup = new AsyncHBaseLookup(...);

// 无序返回（最快，可能乱序）
AsyncDataStream.unorderedWait(
    orders, asyncLookup, 2000, TimeUnit.MILLISECONDS, 100
);

// 有序返回（保留输入顺序，但会等最慢的那个）
AsyncDataStream.orderedWait(
    orders, asyncLookup, 2000, TimeUnit.MILLISECONDS, 100
);
```

参数说明：

| 参数 | 含义 |
| --- | --- |
| `timeout` | 单条 IO 超时时间 |
| `capacity` | 异步并发上限，防止打爆下游；超过则反压 |

> **生产注意**：AsyncDataStream 的 ThreadPool 是 TM 共享的；如果多个算子都用异步 IO，要确认总线程数不会超机器上限。`async-capacity` 不是越大越好，太大反而增加下游压力。

## Sink 怎么出

Flink 1.12+ 推荐 **Sink API（FLIP-143）**：

```java
// Kafka Sink（推荐：支持 Exactly-Once）
KafkaSink<String> sink = KafkaSink.<String>builder()
    .setBootstrapServers("kafka:9092")
    .setRecordSerializer(KafkaRecordSerializationSchema.builder()
        .setTopic("result")
        .setValueSerializationSchema(new SimpleStringSchema())
        .build())
    .setDeliveryGuarantee(DeliveryGuarantee.AT_LEAST_ONCE)
    .build();

result.sinkTo(sink);
```

| DeliveryGuarantee | 说明 | Sink 端 |
| --- | --- | --- |
| `AT_MOST_ONCE` | 最快，可能丢 | 不做事务，直接写 |
| `AT_LEAST_ONCE` | 不丢但可能重复 | 幂等 Sink 配合（Kafka 0.11+） |
| `EXACTLY_ONCE` | 精确一次 | 2PC 或 Sink 自带事务 API |

## DataStream vs Flink SQL 怎么选

| 场景 | 推荐 |
| --- | --- |
| 简单 ETL、聚合、Join | Flink SQL |
| 复杂状态机、自定义窗口、Timer | DataStream + ProcessFunction |
| 广播状态（配置驱动数据流） | DataStream + KeyedBroadcastProcessFunction |
| 异步 IO | DataStream + AsyncDataStream |
| CDC 入湖 | Flink SQL（Iceberg/Hudi Connector） |
| 需要写 UDF/UDAF | 两者都支持，SQL 更标准 |

## 关键配置

```properties
# 算子链开关
env.disableChaining()             # 代码里：整个作业不链
.execution.disable-chaining: true # 全局配置

# 异步 IO 默认参数
async.default-buffer-capacity: 100
async.default-timeout: 3000

# Source 并行度
# 提交时 -p 或 env.setParallelism() 或 算子上 .setParallelism(N)
```

## 常见问题

- **map 和 flatMap 怎么选？** → 明确 1→1 用 map；可能 0 条（过滤）或多条（展开）用 flatMap。
- **ProcessFunction 和 Window 冲突吗？** → 不冲突；可以在 Window 的 ProcessWindowFunction 里访问 Keyed State，或者干脆不用 Window、自己用 KeyedProcessFunction + Timer 实现。
- **异步 IO 会不会影响 Checkpoint？** → AsyncDataStream 里的结果进入算子链后才会被 Checkpoint 覆盖；异步请求中挂了可能重放。要保证下游幂等。
- **Source 并行度和 Kafka Partition 不匹配？** → 设 Source 并行度 = Topic 的 Partition 数，每个 Subtask 至少分一个 Partition。

## 自测

1. 用 `map + filter + keyBy + window` 写出一条 Kafka 订单流的 5 分钟用户级聚合（只写关键骨架代码）。
2. KeyedProcessFunction 相对普通 ProcessFunction 多了哪些能力？这些能力怎么和 Checkpoint 配合？
3. 同步调一个 HTTP 接口（平均延迟 50ms），Source 吞吐 1000 QPS，DataStream 并行度 4。算一下同步 vs 异步的理论吞吐差异（假设单并行度同步 QPS = 20）。
4. Sink 端要实现 Exactly-Once，除了 Checkpoint 还需要什么？

## 参考与官方文档

- [DataStream API 官方文档](https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/overview/)
- [ProcessFunction](https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/process_function/)
- [Async I/O](https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/asyncio/)
- [New Source Interface](https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/sources/)
