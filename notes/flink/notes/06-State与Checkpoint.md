# 06 State 与 Checkpoint

## 一句话

**State（状态）** 是 Flink 算子在处理过程中持有的中间数据——按是否和 Key 绑定分为 **Keyed State**（自动按 Key Group 分片，绝大多数场景用这个）和 **Operator State**（每个并行实例一份，Source/Sink 常用）。**Checkpoint** 是 Flink 的容错机制：把所有算子的 State 快照持久化到 HDFS/S3，失败后从最近一次 Checkpoint 恢复，靠 **Barrier 对齐** 实现 Exactly-Once。生产推荐 **RocksDBStateBackend**，它把 State 存在磁盘上，内存可控。

## State 分类

```
State
├── Keyed State（绑定某个 Key，自动分片、自动恢复）
│   ├── ValueState<T>         单值
│   ├── ListState<T>          列表
│   ├── MapState<K,V>         HashMap
│   ├── ReducingState<T>      滚动规约
│   └── AggregatingState<I,OA,O> 滚动聚合
│
└── Operator State（每个并行实例一份）
    ├── ListState<T>          可在并行度变化时重分配
    └── Broadcast State       广播状态（所有并行实例同一份）
```

### Keyed State 详细

| State 类型 | 存储内容 | 典型场景 |
| --- | --- | --- |
| **ValueState** | 一个类型 T 的值 | 用户计数器、当前会话结束时间 |
| **ListState** | 元素列表 | 窗口内缓存事件、会话窗口 |
| **MapState** | K→V | 用户属性 Map、指标维度 Map |
| **ReducingState** | 累加单值，合并时自定义 | 简单求和、最大/最小 |
| **AggregatingState** | AggregatingFunction 累加器 | 自定义聚合（如平均、百分位） |

### 代码示例

```java
// 在 KeyedProcessFunction / RichFlatMapFunction 中声明 Keyed State
ValueStateDescriptor<Long> counterDesc = new ValueStateDescriptor<>("counter", Long.class);
ListStateDescriptor<Event> bufferDesc = new ListStateDescriptor<>("buffer", Event.class);

// open() 里初始化
private ValueState<Long> counter;
private ListState<Event> buffer;

@Override
public void open(Configuration conf) {
    counter = getRuntimeContext().getState(counterDesc);
    buffer  = getRuntimeContext().getListState(bufferDesc);
}

// processElement 中读写
@Override
public void processElement(Event e, Context ctx, Collector<Result> out) throws Exception {
    Long c = counter.value();
    counter.update((c == null ? 0 : c) + 1);
    buffer.add(e);
}
```

### Operator State 用在哪

- **Source**：Kafka Source 存 Offset（`operatorState`，每个 Partition 一个）
- **Sink**：批量 Sink 存未刷出的数据
- **普通算子**：需要和 Key 无关的状态时（少见）

```java
// Operator State 示例（自定义 Source 存进度）
public class MySource implements SourceFunction<String> {
    private ListState<Long> offsets;

    @Override
    public void run(SourceContext<String> ctx) {}

    @Override
    public void cancel() {}
}

// checkpoint() 方法返回 Operator State 快照
// snapshotState() 快照，initializeState() 恢复
```

### Broadcast State

一种特殊的 Operator State：**配置流 + 数据流**模式下，把配置流广播到所有并行实例：

```java
// 配置流（小而频繁更新）
DataStream<Rule> rules = env.fromSource(ruleSource, ...);
BroadcastStream<Rule> broadcastRules = rules.broadcast(rulesStateDescriptor);

// 主数据流 connect 广播流
DataStream<Event> events = env.fromSource(eventSource, ...);
events.connect(broadcastRules)
      .process(new KeyedBroadcastProcessFunction<Key, Event, Rule, Result>() {
          @Override public void processElement(Event e, ReadOnlyContext ctx, Collector<Result> out) {
              MapState<Key, Rule> ruleState = ctx.getBroadcastState(rulesStateDescriptor);
              Rule rule = ruleState.get(e.getRuleKey());
              // 按规则处理事件
          }
          @Override public void processBroadcastElement(Rule r, Context ctx, Collector<Result> out) {
              BroadcastState<Key, Rule> ruleState = ctx.getBroadcastState(rulesStateDescriptor);
              ruleState.put(r.getKey(), r);  // 更新广播配置
          }
      });
```

## State Backend 选型

| Backend | 存储位置 | 内存模型 | 适用场景 |
| --- | --- | --- | --- |
| **HashMapStateBackend** | TM 堆内存 + Checkpoint 持久化 | 全部在内存 | 本地调试、小状态（< 10MB/Key） |
| **RocksDBStateBackend** | TM 本地磁盘 + Off-Heap 内存 + Checkpoint 持久化 | 磁盘为主、内存做 cache | **生产首选**，状态 > 100MB 必选 |
| **FsStateBackend** | 同 HashMap（旧名） | 内存 | 兼容老配置，新项目不用 |

### RocksDBStateBackend 详解

- 状态存 **TM 本地临时目录**（`taskmanager.tmp.dirs`）
- Flink 在 TM 上嵌入 RocksDB 实例，通过 JNI 访问
- Checkpoint 时用 RocksDB 的 SST 文件直接上传 → **非常快**（无需序列化/反序列化）
- 内存可控：每个 TM 的 Managed Memory 分配给 RocksDB 的 Write Buffer + Block Cache

```properties
state.backend: rocksdb
state.checkpoints.dir: hdfs:///flink/checkpoints

# RocksDB 内存分配（全局，每个 TM）
taskmanager.memory.managed.size: 4gb
# 每个 Slot 分得 RocksDB 内存 ≈ managed.size / numberOfTaskSlots

# RocksDB 调优
state.backend.rocksdb.localdir: /data1/flink-rocksdb,/data2/flink-rocksdb
state.backend.rocksdb.predefined-options: SPINNING_DISK_OPTIMIZED_HIGH_MEM
state.backend.rocksdb.compaction-task-threads: 4
```

> **SPINNING_DISK_OPTIMIZED** vs **FLASH_SSD_OPTIMIZED**：根据你的磁盘类型选，RocksDB 内置预配置。

## Checkpoint 原理

### Barrier 对齐机制

Flink 往 Source 注入一条特殊记录 **Checkpoint Barrier**：

```
时间 →

Source ──► OP1 ──► OP2 ──► Sink
   │         │        │        │
   Barrier   Barrier  Barrier  Barrier到达这里
   到达      到达     到达      后 Sink flush
   开始快照  等待     等待     所有 Barrier 都到齐
             其他    其他
             上游    上游
```

对于多输入（如 Join、Union）的算子：

- Barrier 分别从每个上游到达
- 算子**缓存**先到达的 Barrier 之前的数据
- 等**所有上游的 Barrier 都到齐**后才开始快照 → **对齐**
- 快照完成后释放缓存的数据继续处理

### Exactly-Once vs At-Least-Once

| 模式 | 算子行为 | Sink 端要求 |
| --- | --- | --- |
| **EXACTLY_ONCE** | Barrier 对齐，中间缓存 | Sink 必须是事务型（Kafka 0.11+ Producer 两阶段提交）或幂等 |
| **AT_LEAST_ONCE** | 不对齐，Barrier 到达即快照 | 要求 Sink 幂等（重复写无害） |

> **EXACTLY_ONCE + 非事务型 Sink = 矛盾**。你说你保证 Exactly-Once，但 Sink 幂等不了，其实还是会重复。

### Checkpoint vs Savepoint

| | Checkpoint | Savepoint |
| --- | --- | --- |
| 触发方式 | 周期性自动 | 手动 API / CLI |
| 元数据 | 最小化（作业拓扑） | 完整（算子 ID 映射） |
| 用途 | 故障恢复 | 升级、扩缩、版本迁移 |
| 恢复后作业 ID | 相同 | 新作业 ID |
| 性能 | 高（增量、无元数据开销） | 较低（全量） |

```bash
# 手动触发 Savepoint
flink savepoint <jobId> hdfs:///flink/savepoints/

# 从 Savepoint 启动新作业
flink run -s hdfs:///flink/savepoints/<savepoint-path> -d myjob.jar
```

### 增量 Checkpoint（RocksDB 专属）

```properties
state.backend.incremental: true
```

RocksDB 的 SST 文件是不可变的，增量 Checkpoint 只上传新生成的 SST 文件（老文件继续引用）：

```
Checkpoint 1: upload sst1, sst2, sst3  → 全部
Checkpoint 2: sst1, sst2 不变，sst3 有更新产生 sst4 → 只上传 sst4 + 新元数据
Checkpoint 3: ... → 只上传新增 SST
```

这大大降低了 Checkpoint 压力，但代价是 RocksDB 本地磁盘要保留历史 SST 直到没有 Checkpoint 引用（Flink 自动 GC）。

## Checkpoint 慢怎么排查

```
Checkpoint 慢？
│
├─ 1. Barrier 对齐超时
│   ├─ 上游反压 → 查哪个算子堵了
│   └─ Source 多 Partition，某 Partition 慢 → 查 Kafka 延迟
│
├─ 2. State 快照慢
│   ├─ HashMapStateBackend → 序列化 + 上传，State 大了一定慢 → 换 RocksDB
│   ├─ RocksDB → 磁盘 IO 满 → 查 iostat，换 SSD / 加盘
│   └─ 远程存储慢 → HDFS/S3 带宽不够
│
├─ 3. Async 阶段（上传到远程）
│   └─ 远程存储带宽瓶颈
│
└─ 4. Checkpoint 间隔太小
    └─ 间隔 = 快照时间 * 3 以上（建议 60s+）
```

## 关键配置

```properties
# 启用
execution.checkpointing.enabled: true
execution.checkpointing.mode: EXACTLY_ONCE

# 间隔 & 超时
execution.checkpointing.interval: 60000    # 60s
execution.checkpointing.timeout: 600000    # 10min，超时则取消 Checkpoint
execution.checkpointing.min-pause: 10000   # 两次之间至少等 10s，别叠在一起
execution.checkpointing.max-concurrent-checkpoints: 1

# 增量（RocksDB）
state.backend.incremental: true

# 状态目录
state.checkpoints.dir: hdfs:///flink/checkpoints
state.savepoints.dir: hdfs:///flink/savepoints

# 重启策略
restart-strategy: fixed-delay
restart-strategy.fixed-delay.attempts: 5
restart-strategy.fixed-delay.delay: 10s

# 本地状态保留（升级用）
state.backend.local-recovery: true
```

## 常见问题

- **State 超过 TM 内存怎么办？** 换 RocksDBStateBackend，把溢出到磁盘；检查 Key 是否过多、ListState 是否设上限。
- **Checkpoint 对齐时数据丢了？** 不会。EXACTLY_ONCE 模式下 Barrier 对齐期间数据只是暂存算子内部队列，不会丢。
- **RocksDBStateBackend 会吃 TM 本地磁盘吗？** 会。`taskmanager.tmp.dirs` 要给够空间。磁盘满 → TM 挂。
- **并行度变化后 Keyed State 怎么办？** Flink 自动按 Key Group 重新分配；恢复时从 Savepoint 读，128 Key Group 按新并行度重分片。

## 自测

1. Keyed State 和 Operator State 的核心差别是什么？各自典型用在哪？
2. 解释 Checkpoint Barrier 对齐的全过程。为什么 EXACTLY_ONCE 需要对齐、AT_LEAST_ONCE 不需要？
3. 生产环境 State Backend 选 RocksDB 还是 HashMap？给出判断依据（State 大小、作业性质、磁盘条件）。
4. Checkpoint 慢，你会按什么顺序排查？写出 3 步排查路径。

## 参考与官方文档

- [State 官方文档](https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/fault-tolerance/state/)
- [Checkpointing](https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/fault-tolerance/checkpointing/)
- [RocksDBStateBackend](https://nightlies.apache.org/flink/flink-docs-stable/docs/ops/state/state_backends/#rocksdbstatebackend)
- [Incremental Checkpoints](https://nightlies.apache.org/flink/flink-docs-stable/docs/ops/state/incremental_checkpoints/)
