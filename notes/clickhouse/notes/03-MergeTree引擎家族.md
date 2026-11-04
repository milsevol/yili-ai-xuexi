# 03 MergeTree引擎家族

## 一句话

**MergeTree 是 ClickHouse 的核心引擎家族**，有 6 种变体：MergeTree 基类（普通 OLAP）、ReplacingMergeTree（去重）、SummingMergeTree（预求和）、AggregatingMergeTree（预聚合）、CollapsingMergeTree（抵消删除）、VersionedCollapsingMergeTree（带版本抵消）。选择哪个引擎，直接决定数据写入后的存储行为和查询性能。

## MergeTree 基类

最基础的 MergeTree，所有变体都继承它的行为：

```sql
CREATE TABLE orders (
  id UInt64,
  user_id UInt64,
  amount Float64,
  dt Date
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(dt)
ORDER BY (user_id, id);
```

**核心行为**：
- 写入：append-only，每次 INSERT 生成一个新 Part
- Merge：后台线程按 ORDER BY 归并排序合并同分区 Part
- 特性：无去重、无预聚合、无事务控制——最灵活

| 特性 | 说明 |
| --- | --- |
| PARTITION BY | 分区键，决定磁盘目录划分，强烈建议用时间字段 |
| ORDER BY | 排序键（必填），决定数据物理顺序和主索引 |
| PRIMARY KEY | 主键，可选；默认等于 ORDER BY |
| SAMPLE BY | 采样键，支持 `SELECT ... SAMPLE 0.1` |
| TTL | 过期删除/移动分区，异步后台执行 |

## 六种 MergeTree 变体

### 1. ReplacingMergeTree — 去重

```sql
CREATE TABLE t_replacing (
  id UInt64,
  value String,
  version UInt32
) ENGINE = ReplacingMergeTree(version)
ORDER BY id;
```

**核心行为**：后台 Merge 时，相同 ORDER BY 键的多行只保留一行（取 `version` 最大的或最后写入的）。

| 参数 | 含义 |
| --- | --- |
| ReplacingMergeTree(version) | 指定版本列，保留版本值最大的行 |
| ReplacingMergeTree() | 无版本列，保留**最后写入**的行 |

**使用场景**：用户画像表、维表（同 id 更新属性）、多源合并去重。

**注意**：去重只在后台 Merge 时生效——刚 INSERT 的重复数据可能还在。查询时如果要临时去重，用 `FINAL` 关键字（但慢）。

```sql
-- 临时去重查询
SELECT * FROM t_replacing FINAL WHERE id = 123;
```

### 2. SummingMergeTree — 预求和

```sql
CREATE TABLE t_summing (
  city String,
  channel String,
  amount Float64,    -- 求和字段
  clicks UInt64      -- 求和字段
) ENGINE = SummingMergeTree()
PARTITION BY toYYYYMMDD(dt)
ORDER BY (city, channel);
```

**核心行为**：后台 Merge 时，相同 ORDER BY 键的多行，数值列自动求和合并。

```
写入 3 条：(北京, A, 100, 50), (北京, A, 200, 30), (北京, B, 50, 10)
Merge 后： (北京, A, 300, 80),  (北京, B, 50, 10)
```

**使用场景**：指标系统、监控系统、SaaS 仪表盘——写入原始数据但查询时直接读到**预先合并好**的聚合值。

**语法**：
```sql
-- SummingMergeTree() 默认除 ORDER BY 外所有数值列求和
-- SummingMergeTree(amount, clicks) 指定只有这些列求和
ENGINE = SummingMergeTree(amount, clicks)
```

### 3. AggregatingMergeTree — 预聚合（最灵活）

```sql
CREATE TABLE t_agg (
  city String,
  dt Date,
  count_u AggregateFunction(uniq, UInt64),
  sum_amount AggregateFunction(sum, Float64)
) ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMMDD(dt)
ORDER BY (city, dt);
```

**核心行为**：列类型用 `AggregateFunction(函数名, 参数类型)`，写入时用 `xxxState()` 函数，查询时用 `xxxMerge()` 函数合并状态。

```sql
-- 写入（用 State 函数）
INSERT INTO t_agg VALUES ('北京', '2026-11-03', uniqState(user_id), sumState(amount));

-- 查询（用 Merge 函数）
SELECT city, uniqMerge(count_u) AS uv, sumMerge(sum_amount) AS amount
FROM t_agg GROUP BY city;
```

| AggregateFunction 类型 | 写入函数 | 查询函数 | 说明 |
| --- | --- | --- | --- |
| `uniq, UInt64` | `uniqState(user_id)` | `uniqMerge(count_u)` | 去重计数（HyperLogLog 近似） |
| `sum, Float64` | `sumState(amount)` | `sumMerge(sum_amount)` | 求和 |
| `avg, Float64` | `avgState(amount)` | `avgMerge(avg_val)` | 平均值（状态含 count + sum） |
| `quantile, Float64` | `quantileState(amount)` | `quantileMerge(q_val)` | 分位数（t-digest 近似） |

**使用场景**：需要精确控制聚合函数、要做近似去重（uniq）、分位数统计的场景。比 SummingMergeTree 更灵活但写法更复杂。

### 4. CollapsingMergeTree — 抵消删除

```sql
CREATE TABLE t_collapsing (
  id UInt64,
  value String,
  sign Int8          -- sign = 1（新增）, sign = -1（删除）
) ENGINE = CollapsingMergeTree(sign)
ORDER BY id;
```

**核心行为**：写入时标记操作类型，后台 Merge 时 sign=1 和 sign=-1 成对抵消。

```
写入：(1, 'hello', 1), (1, 'hello', -1), (1, 'updated', 1)
Merge 后抵消：(1, 'updated', 1)

抵消逻辑：相同 ORDER BY 键的 sign=1 和 sign=-1 互相抵消，剩下的保留
```

**使用场景**：MySQL / Kafka CDC 变更同步（UPDATE/DELETE 需要被抵消）。

**注意**：同一条记录的 sign=1 和 sign=-1 必须**在不同 Part 里**才能正确抵消——如果在同一个 Part 里写入（同一次 INSERT），ClickHouse 会按 sign 值排序，-1 排在 1 前面不会抵消。这是 CollapsingMergeTree 的一个微妙坑。

### 5. VersionedCollapsingMergeTree — 带版本的抵消

```sql
CREATE TABLE t_vcollapsing (
  id UInt64,
  value String,
  version UInt64,     -- 版本号，越大越新
  sign Int8
) ENGINE = VersionedCollapsingMergeTree(sign, version)
ORDER BY id;
```

和 CollapsingMergeTree 类似，但多一个 `version` 列。后台 Merge 时，相同 id 且 version 相同的 sign=1 和 sign=-1 才会抵消。解决了 CollapsingMergeTree 中版本交错的问题。

**使用场景**：CDC + 乱序到达场景（Kafka 消息可能乱序，需要靠 version 对齐）。

## 引擎选择决策树

```
你的数据有什么特性？
│
├─ 需要按 ORDER BY 键去重吗？
│   ├─ 有版本字段 → ReplacingMergeTree(version)
│   └─ 无版本字段 → ReplacingMergeTree()
│
├─ 需要预聚合吗？（指标系统、实时看板）
│   ├─ 只有简单求和 → SummingMergeTree(指定求和列)
│   └─ 需要 uniq/quantile 等复杂函数 → AggregatingMergeTree()
│
├─ 需要处理变更/删除吗？（CDC、多源合并）
│   ├─ 有 sign 标记（+1/-1），无乱序 → CollapsingMergeTree(sign)
│   └─ 有 sign + version 乱序 → VersionedCollapsingMergeTree(sign, version)
│
└─ 以上都不需要 → MergeTree() 基类
```

## Materialized View 与 MergeTree 的关系

物化视图本身**不是存储引擎**——它是一张带有**写入触发器**的视图：

```sql
-- 物化视图：写入时自动聚合到目标表
CREATE TABLE daily_stats (
  city String,
  amount AggregateFunction(sum, Float64)
) ENGINE = AggregatingMergeTree()
ORDER BY city;

CREATE MATERIALIZED VIEW daily_stats_mv TO daily_stats AS
SELECT
  city,
  sumState(amount) AS amount
FROM orders
GROUP BY city;
```

**关系总结**：
- Materialized View **必须有一个 MergeTree 家族的目标表**（普通 MergeTree 或任何变体）
- 物化视图的 SELECT 结果会自动 INSERT 到目标表
- 目标表的引擎类型**直接决定聚合/去重行为**

## 关键配置

```sql
-- 控制 Merge 行为
SET max_merge_select_sleep_ms = 50;          -- 两次 Merge 选择间隔
SET max_parts_to_merge_at_once = 100;        -- 单次 Merge 最多合并多少 Part

-- ReplacingMergeTree 查询临时去重
SELECT ... FINAL ...;   -- FINAL 强制在查询时合并（慎用！慢）
SET max_final_threads = 4;  -- FINAL 查询的线程数

-- CollapsingMergeTree 抵消检查
SET enable_collapsing_merge_tree = 1;
```

## 常见问题

**Q：ReplacingMergeTree 的去重能实时生效吗？**
A：不能！去重只在后台 Merge 时生效。如果刚写了重复数据又查，可能还读到重复的。想临时去重用 `FINAL` 关键字，但 FINAL 强制查询时合并，性能差。

**Q：SummingMergeTree 的求和字段写错了怎么办？**
A：写错的列会走默认求和逻辑（所有数值列都求）。可以用 `DESCRIBE TABLE` 查看 MergeTree 列的 `comment` 字段确认哪些是求和列。

**Q：CollapsingMergeTree 的 sign 是必填 Int8 列，为什么？**
A：因为后台 Merge 时需要知道哪行是「新增（sign=+1）」哪行是「删除（sign=-1）」。这是 ClickHouse 处理删除的官方方式——它没有逐行 DELETE。

**Q：物化视图的目标表可以是 Distributed 引擎吗？**
A：可以但不推荐。Distributed 引擎写入多一层网络跳转，增加延迟。更推荐物化视图写入本地 MergeTree，Distributed 层只做查询路由。

## 自测

1. 用一句话说清 ReplacingMergeTree、SummingMergeTree、AggregatingMergeTree 各自的核心行为和典型使用场景。
2. CollapsingMergeTree 和 VersionedCollapsingMergeTree 的区别是什么？各自解决什么问题？
3. AggregatingMergeTree 的写入和查询分别用什么函数？为什么不直接写 `sum(amount)`？
4. 物化视图和 MergeTree 引擎是什么关系？CREATE MATERIALIZED VIEW TO ... 里的 TO 后面必须是什么类型的表？

## 参考与官方链接

- [MergeTree 家族（官方文档）](https://clickhouse.com/docs/en/engines/table-engines/mergetree-family)
- [ReplacingMergeTree](https://clickhouse.com/docs/en/engines/table-engines/mergetree-family/replacingmergetree)
- [SummingMergeTree](https://clickhouse.com/docs/en/engines/table-engines/mergetree-family/summingmergetree)
- [AggregatingMergeTree](https://clickhouse.com/docs/en/engines/table-engines/mergetree-family/aggregatingmergetree)
- [CollapsingMergeTree](https://clickhouse.com/docs/en/engines/table-engines/mergetree-family/collapsingmergetree)
- [Materialized View](https://clickhouse.com/docs/en/guides/materialized-views)
