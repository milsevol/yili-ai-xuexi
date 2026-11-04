# 05 Window 窗口机制

## 一句话

**Flink Window** 把无限流切成有限块做聚合——四种内置 Assigners（滚动/滑动/会话/全局），配合 **WindowFunction** 产出结果，**Trigger** 控制何时触发，**Evictor** 可选清理桶数据，**Incremental AggregateFunction** 边收边聚合省状态。迟到数据靠 `allowedLateness` + 侧输出流处理。

## 窗口的整体模型

```
        DataStream → .keyBy() → .window(WindowAssigner) → [.trigger() .evictor()] 
                              → [.allowedLateness() .sideOutputLateData()] 
                              → .aggregate() / .apply() / .process() → DataStream
```

一个窗口由四部分组成：

| 组件 | 职责 |
| --- | --- |
| **WindowAssigner** | 定义窗口边界：怎么把元素分配到窗口桶里 |
| **WindowFunction** | 窗口触发后产出结果的聚合逻辑 |
| **Trigger** | 决定窗口何时触发计算 |
| **Evictor** | 可选，在聚合前/后清理窗口中的元素 |

## 四种内置窗口

### 1. 滚动窗口（Tumbling Window）

固定长度，不重叠：

```
窗口大小 10min:
[00:00, 00:10) [00:10, 00:20) [00:20, 00:30) ...
```

```java
. window(TumblingEventTimeWindows.of(Time.minutes(10)))
// 或 Processing-Time:
. window(TumblingProcessingTimeWindows.of(Time.minutes(10)))
```

### 2. 滑动窗口（Sliding Window）

固定长度 + 滑动步长，窗口重叠：

```
窗口 10min, 步长 5min:
[00:00, 00:10)
      [00:05, 00:15)
            [00:10, 00:20)
```

```java
.window(SlidingEventTimeWindows.of(Time.minutes(10), Time.minutes(5)))
```

### 3. 会话窗口（Session Window）

基于**会话间隙**划分：相邻事件超过 gap 就算一个新会话：

```
gap = 5min:
事件流:  --e1--e2----e3---------------------e4--e5----
         ├─ 会话 1 ─┤   (空窗 5min)          ├─ 会话 2 ─┤
```

```java
.window(EventTimeSessionWindows.withGap(Time.minutes(5)))
// 动态 gap（根据事件属性决定）
.window(EventTimeSessionWindows.withDynamicGap((ev) -> Time.minutes(ev.getGapMinutes())))
```

### 4. 全局窗口（Global Window）

所有 Key 的所有数据进一个窗口，需要**自定义 Trigger** 触发：

```java
.window(GlobalWindows.create())
.trigger(CustomTrigger)  // 必须自己定义何时触发
```

> **默认 Trigger**：Event-Time 窗口用 `EventTimeTrigger`（Watermark ≥ 窗口结束触发）；Processing-Time 窗口用 `ProcessingTimeTrigger`（系统时间到了触发）。

## WindowAssigner 一览

| Assigner | 时间语义 | 描述 |
| --- | --- | --- |
| `TumblingEventTimeWindows` | EventTime | 滚动，按事件时间 |
| `TumblingProcessingTimeWindows` | ProcessingTime | 滚动，按机器时间 |
| `SlidingEventTimeWindows` | EventTime | 滑动 |
| `EventTimeSessionWindows` | EventTime | 会话 |
| `GlobalWindows` | - | 全局 |
| `CustomWindowAssigner` | 自定义 | 实现 `assignWindows()` |

## WindowFunction 选择

### 增量聚合（推荐）——AggregateFunction

**边收到边聚合**，状态里只存一个累加器，省内存：

```java
// 累加器：[sum, count]
AggregateFunction<Order, Tuple2<Long, Integer>, Double> avgAmount = 
    new AggregateFunction<>() {
        @Override public Tuple2<Long, Integer> createAccumulator() { return Tuple2.of(0L, 0); }
        @Override public Tuple2<Long, Integer> add(Order o, Tuple2<Long, Integer> acc) {
            return Tuple2.of(acc.f0 + o.getAmount(), acc.f1 + 1);
        }
        @Override public Double getResult(Tuple2<Long, Integer> acc) {
            return acc.f0 / (double) acc.f1;
        }
        @Override public Tuple2<Long, Integer> merge(Tuple2<Long, Integer> a, Tuple2<Long, Integer> b) {
            return Tuple2.of(a.f0 + b.f0, a.f1 + b.f1);
        }
    };

orders.keyBy(Order::getUserId)
      .window(TumblingEventTimeWindows.of(Time.minutes(10)))
      .aggregate(avgAmount);
```

### 全量聚合——ProcessWindowFunction

触发时**拿到窗口内全部元素**，可以访问 Key、窗口元数据、输出到侧输出流：

```java
orders.keyBy(Order::getUserId)
      .window(TumblingEventTimeWindows.of(Time.minutes(10)))
      .process(new ProcessWindowFunction<Order, String, String, TimeWindow>() {
          @Override
          public void process(String key, Context context, Iterable<Order> elements, Collector<String> out) {
              long count = elements.spliterator().getExactSizeIfKnown();
              TimeWindow w = context.window();
              out.collect(String.format(
                  "user=%s window=[%d,%d) count=%d",
                  key, w.getStart(), w.getEnd(), count
              ));
          }
      });
```

### 两者结合——AggregateFunction + ProcessWindowFunction

增量聚合省状态，最后 ProcessWindowFunction 拿窗口元数据：

```java
orders.keyBy(Order::getUserId)
      .window(TumblingEventTimeWindows.of(Time.minutes(10)))
      .aggregate(new SumAgg<>(), (ProcessWindowFunction<Tuple2<Long, Integer>, Double, String, TimeWindow>)
          (key, ctx, acc, out) -> {
              double avg = acc.f0 / (double) acc.f1;
              out.collect(avg);
          });
```

> **实战建议**：优先 `aggregate()` 增量聚合；需要窗口元数据时用 `aggregate + ProcessWindowFunction` 组合；不得已才用纯 `process()` 全量聚合（状态吃紧）。

## 迟到数据处理

回顾上一章三种策略：

```java
OutputTag<Order> lateTag = new OutputTag<>("late", Order.class);

orders.keyBy(Order::getUserId)
      .window(TumblingEventTimeWindows.of(Time.minutes(10)))
      .allowedLateness(Time.minutes(2))
      .sideOutputLateData(lateTag)
      .aggregate(...)
      .getSideOutput(lateTag)  // 拿到迟到流，做补算
      .addSink(...);
```

窗口 [10:00, 10:10) 的生命周期：

```
Watermark ≥ 10:10 → 首次触发（输出第一条）
事件 10:08 到达（Watermark 仍 < 10:12）→ 二次触发（allowedLateness 生效）
事件 10:06 到达 → 三次触发
Watermark ≥ 10:12 → 窗口关闭，状态清理
事件 10:07 到达 → 进 sideOutputLateData（不再触发）
```

## Trigger——自定义触发时机

默认 Trigger 可能不够（比如需要**提前触发**、**按数量触发**）：

```java
// 数量触发：窗口每攒够 100 条就触发一次，同时保留默认 EventTime 触发
Trigger<Order, TimeWindow> countTrigger = TriggerHelper
    .countTrigger(100L, TriggerHelper.TriggerState.FIRE_ONCE);

// 自定义 Trigger 实现
public class MyTrigger extends Trigger<Order, TimeWindow> {
    @Override public TriggerResult onElement(Order e, long t, TimeWindow w, TriggerContext ctx) {
        // 每 100 条触发一次
        CountState count = ctx.getPartitionedState(new ValueStateDescriptor<>("cnt", Integer.class));
        int c = count.value() == null ? 0 : count.value();
        count.update(c + 1);
        if (c + 1 >= 100) { count.update(0); return TriggerResult.FIRE; }
        return TriggerResult.CONTINUE;
    }
    @Override public TriggerResult onEventTime(long time, TimeWindow w, TriggerContext ctx) {
        return time >= w.getEnd() ? TriggerResult.FIRE_AND_PURGE : TriggerResult.CONTINUE;
    }
    @Override public void clear(TimeWindow w, TriggerContext ctx) {}
}
```

## Evictor——窗口前清理元素

```java
// 只保留最新的 100 条做聚合
.evictor(CountEvictor.of(100))

// 只保留最近 5 分钟
.evictor(TimeEvictor.of(Time.minutes(5)))
```

> Evictor 会遍历整个窗口，状态开销大。能不用就不用。

## 关键配置

```properties
# Checkpoint 对窗口状态的影响：
# 窗口状态跟着 Keyed State 一起 Checkpoint，自动恢复
# 所以窗口的 allowedLateness 越大 → 状态越大 → Checkpoint 越慢
```

## 常见问题

- **滑动窗口为什么状态是滚动窗口的 N 倍？** 因为一个事件同时进入多个窗口（步长 = 5min、窗口 = 10min 时，一个事件进 2 个窗口）。注意内存预算。
- **会话窗口状态怎么清理？** 会话结束（Watermark 超过会话 end + gap）后自动清理；allowedLateness 内保留。
- **Global Window 有什么用？** 当你需要「所有 Key 一起触发」（比如每分钟所有 Key 汇总）或自定义极特殊触发规则时。
- **aggregate 和 process 能不能只用一个？** 能。`aggregate()` 只返回聚合结果；`process()` 返回窗口全部元素。推荐用 `aggregate` 省状态。

## 自测

1. 画出 10min 窗口 + 5min 步长滑动窗口在 1 小时内的窗口覆盖示意。
2. 滚动窗口 10min，allowedLateness 2min。Watermark 到达首次触发时间后，窗口会经历哪些状态？最终何时完全关闭？
3. AggregateFunction 和 ProcessWindowFunction 的本质差别是什么？在生产上优先哪个，为什么？
4. 会话窗口 gap = 5min。事件流：0, 1, 3, 7, 15, 16, 20, 30。每个事件时间戳秒。划分出哪几个会话？

## 参考与官方文档

- [Windows 官方文档](https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/window/overview/)
- [Window API](https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/window/window-assigners/)
- [AggregateFunction](https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/window/window-functions/#aggregatefunction)
