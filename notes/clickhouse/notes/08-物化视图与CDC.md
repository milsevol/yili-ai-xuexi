# 08-物化视图与CDC

## 一句话

ClickHouse 的 **Materialized View（物化视图）** 是一个**写入触发器**——往源表 INSERT 时，自动把 SELECT 结果 INSERT 到目标表。配合 Kafka / MySQL 引擎可以实现 CDC（变更数据捕获），把外部系统的实时变更入 ClickHouse。TTL 自动过期让历史数据管理省心。

## Materialized View 基础

### 概念

普通视图（VIEW）只是 SELECT 语句的别名，每次查询时动态跑 SELECT。**物化视图**会在**写入时**把 SELECT 结果**持久化**到目标表——相当于预计算 + 缓存。

```sql
-- ❌ 普通视图（动态计算，每次查都跑 SELECT）
CREATE VIEW daily_orders AS
SELECT dt, count() FROM orders GROUP BY dt;

-- ✅ 物化视图（预计算，结果存在目标表里）
CREATE TABLE daily_orders_mv (
  dt Date,
  cnt AggregateFunction(sum, UInt64)
) ENGINE = AggregatingMergeTree()
ORDER BY dt;

CREATE MATERIALIZED VIEW daily_orders TO daily_orders_mv AS
SELECT dt, count() AS cnt
FROM orders
GROUP BY dt;
```

### Materialized View 结构

```
┌─────────────┐     INSERT 触发     ┌──────────────────┐     自动写入     ┌──────────────┐
│   源表       │ ──────────────────→ │   物化视图（MV）   │ ──────────────→ │   目标表       │
│   orders    │     执行 SELECT      │  SELECT ... FROM  │                 │  daily_orders │
│             │                      │  orders GROUP BY  │                 │   (MergeTree) │
└─────────────┘                      └──────────────────┘                 └──────────────┘
```

**关键**：物化视图本身**不存数据**，它只是「SQL + 触发器」。数据全部在目标表里。

### 同步 vs 异步刷新

ClickHouse 物化视图写入时**同步触发**——INSERT 源表的线程会同时执行物化视图的 SELECT 并 INSERT 到目标表。

| 特性 | 说明 |
| --- | --- |
| 触发时机 | 源表 INSERT 完成前（阻塞式） |
| 同步/异步 | **同步**（源表写入会等待物化视图执行完） |
| 失败处理 | 物化视图失败会让源表 INSERT 也失败 |
| 延迟 | 几乎 0（同一批次写入） |
| 并发 | 多个物化视图各自独立，不串行 |

```sql
-- 控制物化视图行为
SET max_materialized_views_per_query = 16;
SET throw_on_max_materialized_views_exceeded = 1;
```

### CREATE MATERIALIZED VIEW TO 语法

```sql
-- 完整语法
CREATE MATERIALIZED VIEW [IF NOT EXISTS] [db.]mv_name
TO [db.]target_table              -- ✅ 必须指定目标表
[ON CLUSTER cluster]              -- 集群级创建
AS SELECT ...                     -- ✅ 必须有 SELECT
```

**目标表必须是 MergeTree 家族**（MergeTree / ReplacingMergeTree / SummingMergeTree / AggregatingMergeTree / ...）。选择什么引擎决定了物化视图的行为：

| 目标表引擎 | 物化视图效果 |
| --- | --- |
| MergeTree | 每批 INSERT 都直接写入（可能重复） |
| ReplacingMergeTree | 相同 ORDER BY 键后台去重 |
| SummingMergeTree | 相同 ORDER BY 键后台预求和 |
| AggregatingMergeTree | 写入 xxxState()，查询 xxxMerge() 合并 |

### 实战示例：实时聚合加速

```sql
-- 源表：原始用户行为日志（每事件一行）
CREATE TABLE user_events (
  user_id UInt64,
  event_id UInt64,
  city String,
  event_time DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(event_time)
ORDER BY (user_id, event_time);

-- 目标表：按城市 + 天预聚合（SummingMergeTree 去重求和）
CREATE TABLE city_daily_metrics (
  city String,
  dt Date,
  event_cnt UInt64
) ENGINE = SummingMergeTree()
PARTITION BY dt
ORDER BY (city, dt);

-- 物化视图：写入源表时自动聚合到目标表
CREATE MATERIALIZED VIEW mv_city_daily TO city_daily_metrics AS
SELECT
  city,
  toDate(event_time) AS dt,
  count() AS event_cnt
FROM user_events
GROUP BY city, dt;

-- 现在，每秒向 user_events INSERT 10 万行：
INSERT INTO user_events VALUES
(101, 1, '北京', now()), (102, 2, '上海', now()), ...;

-- 查目标表，秒级返回（已经预先聚合好了）
SELECT city, sum(event_cnt) FROM city_daily_metrics
WHERE dt BETWEEN '2026-11-01' AND '2026-11-07'
GROUP BY city;
```

### 删除物化视图

```sql
-- 只删物化视图定义，目标表数据保留
DROP MATERIALIZED VIEW mv_city_daily;

-- 同时删物化视图和目标表
DROP TABLE mv_city_daily SYNC;  -- SYNC 确保后台清理完成
DROP TABLE city_daily_metrics;
```

## TTL 自动过期

TTL（Time-To-Live）让 ClickHouse **自动管理历史数据的生命周期**——到期删除或移动分区，不需要手动 `DROP PARTITION`。

### 表级 TTL

```sql
CREATE TABLE orders_with_ttl (
  id UInt64,
  user_id UInt64,
  amount Float64,
  dt Date,
  created DateTime
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(dt)
ORDER BY (user_id, id)

-- 分区 TTL：dt 超过 180 天 → 整个分区删除
TTL dt + INTERVAL 180 DAY

-- 行级 TTL：created 超过 7 天 → 单行删除（需要 ALTER 触发重写）
-- 注意：行级 TTL 实际上是通过后台重写 Part 实现的，昂贵
TTL dt + INTERVAL 180 DAY, created + INTERVAL 7 DAY

-- 分区移动 TTL：180 天的分区移到冷存储
TTL dt + INTERVAL 180 DAY TO DISK 'cold', dt + INTERVAL 365 DAY DELETE;
```

### TTL 后台调度

TTL 由后台线程定期检查并执行：

```sql
-- 服务器级配置 TTL 调度间隔
-- config.xml
<merge_with_ttl_timeout>86400</merge_with_ttl_timeout>  <!-- 24 小时检查一次 -->

-- SQL 级强制立即执行（慎用！）
SYSTEM FLUSH TTL orders_with_ttl;
```

| TTL 类型 | 执行成本 | 适用场景 |
| --- | --- | --- |
| **分区 TTL**（推荐） | 低（标记 + 后台删除） | 按日期过期 |
| **行级 TTL** | 高（需要 Part 重写） | 行级精确过期 |
| **移动 TTL** | 中（Move Partition） | 冷热分层存储 |

### 修改 TTL

```sql
-- 添加新 TTL 条件
ALTER TABLE orders_with_ttl MODIFY TTL dt + INTERVAL 90 DAY;

-- 移除 TTL
ALTER TABLE orders_with_ttl MODIFY TTL;
```

## CDC：实时变更入 ClickHouse

CDC（Change Data Capture）是把外部系统（MySQL、PostgreSQL、MongoDB）的**实时变更**同步到 ClickHouse 的核心方案。

### 方案一：Kafka 引擎 + Materialized View

ClickHouse 内置 Kafka 引擎，可以直接消费 Kafka Topic：

```sql
-- 1. 创建 Kafka 引擎表（Source 表，不存数据）
CREATE TABLE orders_kafka_source (
  id UInt64,
  user_id UInt64,
  amount Float64,
  status UInt8,
  dt String
) ENGINE = Kafka()
SETTINGS
  kafka_broker_list = 'kafka1:9092,kafka2:9092',
  kafka_topic_list = 'mysql_orders_binlog',
  kafka_group_name = 'clickhouse_orders',
  kafka_format = 'JSONEachRow',
  kafka_num_consumers = 2;

-- 2. 创建目标 MergeTree 表
CREATE TABLE orders_real_time (
  id UInt64,
  user_id UInt64,
  amount Float64,
  status UInt8,
  dt Date
) ENGINE = ReplacingMergeTree()
PARTITION BY toYYYYMMDD(dt)
ORDER BY id;

-- 3. 物化视图：Kafka 消息自动入目标表
CREATE MATERIALIZED VIEW mv_kafka_to_orders TO orders_real_time AS
SELECT
  id,
  user_id,
  amount,
  status,
  toDate(dt) AS dt
FROM orders_kafka_source;
```

```
数据流向:
  MySQL → Debezium CDC → Kafka Topic → Kafka 引擎表 → 物化视图 → ReplacingMergeTree 本地表
```

**特性**：
- Kafka 引擎表本身**不存数据**，只做流式读取
- 物化视图**持续触发**（每条消息），实时入 ClickHouse
- 消费组名管理 offset，支持断线重连继续消费

### 方案二：Flink CDC + Kafka + ClickHouse

生产更常用 Flink CDC 做变更捕获 + 数据清洗，然后写入 ClickHouse：

```yaml
# Flink SQL CDC 作业
-- 1. Flink CDC 读 MySQL
CREATE TABLE mysql_orders_source (
  id BIGINT,
  user_id BIGINT,
  amount DOUBLE,
  status INT,
  dt DATE,
  PRIMARY KEY (id) NOT ENFORCED
) WITH (
  'connector' = 'mysql-cdc',
  'hostname' = 'mysql',
  'database-name' = 'shop',
  'table-name' = 'orders',
  'username' = 'root',
  'password' = 'root',
  'scan.startup.mode' = 'initial'
);

-- 2. Flink 写入 ClickHouse（Sink）
CREATE TABLE clickhouse_orders (
  id BIGINT,
  user_id BIGINT,
  amount DOUBLE,
  status INT,
  dt DATE,
  PRIMARY KEY (id) NOT ENFORCED
) WITH (
  'connector' = 'clickhouse',
  'url' = 'http://clickhouse:8123',
  'database-name' = 'default',
  'table-name' = 'orders_real_time',
  'sink.batch-size' = '5000',
  'sink.write-method' = 'insert'
);

-- 3. 简单同步（也可以加清洗逻辑）
INSERT INTO clickhouse_orders SELECT * FROM mysql_orders_source;
```

| 方案 | 延迟 | 清洗能力 | 维护成本 | 适用 |
| --- | --- | --- | --- | --- |
| ClickHouse Kafka 引擎 + MV | 毫秒级 | 弱（只做简单 SELECT 转换） | 低 | 直接入仓，不复杂清洗 |
| Flink CDC + ClickHouse Sink | 毫秒级 | 强（Flink SQL 全能力） | 中 | 需要清洗/转换/多源合并 |
| Canal/Debezium → Kafka → Spark → ClickHouse | 秒级 | 强 | 高 | 已有 Spark 生态 |

### MySQL 引擎直连（不推荐长期）

```sql
-- 直接查 MySQL 表
CREATE TABLE mysql_orders (... ) ENGINE = MySQL('mysql-host:3306', 'db', 'table', 'user', 'pass');

-- 但 ClickHouse MySQL 引擎不支持实时同步！每次查询才拉数据
-- 适合偶尔 JOIN，不适合作为主数据链路
```

## 高级 Materialized View 模式

### ON CLUSTER 创建

在集群所有节点同时创建物化视图：

```sql
CREATE MATERIALIZED VIEW mv_city_daily ON CLUSTER 'production'
TO city_daily_metrics AS
SELECT ...;
```

### 嵌套物化视图

物化视图的目标表可以再作为另一个物化视图的源表——但**每个物化视图都会阻塞写入**，建议控制层级（最多 2 层）。

### POPULATE 关键字

```sql
-- CREATE MATERIALIZED VIEW 默认不回填历史数据
-- 写入 POPULATE 会立即扫描源表并回填
CREATE MATERIALIZED VIEW mv_populated TO target_table POPULATE AS
SELECT ... FROM source_table;
```

**POPULATE 的坑**：如果同时有源表 INSERT 进行中，可能漏掉部分数据。生产建议先建空物化视图，再手动回填：

```sql
-- 安全步骤
CREATE MATERIALIZED VIEW mv_orders TO target_table AS SELECT ... FROM source_table;
INSERT INTO target_table SELECT ... FROM source_table WHERE ...;  -- 手动回填
```

## 关键配置

```sql
-- Kafka 引擎相关
SET kafka_default_cluster_timeout_ms = 5000;
SET kafka_handle_error_mode = 'default';    -- 或 'stream' 让错误通过 MV 传入错误表

-- 物化视图并行度
SET max_threads = 8;
SET max_materialized_views_per_query = 16;  -- 单个 INSERT 触发多少 MV
```

```xml
<!-- config.xml TTL 相关 -->
<merge_with_ttl_timeout>86400</merge_with_ttl_timeout>
<replication_merge_select_sleep_ms>50</replication_merge_select_sleep_ms>
```

## 常见问题

**Q：物化视图的源表写入慢怎么办？**
A：因为物化视图阻塞式同步执行，建议：① 物化视图里的 SELECT 尽量简单（少 JOIN、少复杂函数）；② 批量写入源表（减少触发次数）；③ 多个物化视图拆成不同层级；④ 必要时考虑 Kafka 异步解耦。

**Q：TTL 删分区是立即执行吗？**
A：不是。TTL 是后台线程定时检查（默认 24 小时一次），到了才标记删除。删除前会做 backup（如果配置了）。可以用 `SYSTEM FLUSH TTL` 强制立即执行。

**Q：Kafka 引擎表数据存在哪？**
A：**不存在 ClickHouse 里**——Kafka 引擎表是 Reader，物化视图写入目标 MergeTree 表后才真正存下来。Kafka 引擎表本身只是消费 Kafka 消息然后交给物化视图。

**Q：ReplacingMergeTree 作为物化视图目标表，去重什么时候生效？**
A：和平时一样，后台 Merge 时生效。刚写入的重复数据可能还在。如果需要立即去重查询，用 `FINAL` 关键字。

## 自测

1. 用一句话说清普通视图和物化视图的核心区别。ClickHouse 的物化视图目标表必须是什么引擎类型？
2. TTL 有哪几种类型？分区 TTL 和行级 TTL 的执行成本差异来自哪里？
3. ClickHouse Kafka 引擎 + Materialized View 的 CDC 方案和 Flink CDC 方案各自的优缺点是什么？适用什么场景？
4. POPULATE 关键字的作用是什么？为什么生产建议不直接用 POPULATE，而是先建 MV 再手动 INSERT 回填？

## 参考与官方链接

- [Materialized View（官方文档）](https://clickhouse.com/docs/en/guides/materialized-views)
- [Kafka 引擎](https://clickhouse.com/docs/en/engines/table-engines/integrations/kafka)
- [TTL 文档](https://clickhouse.com/docs/en/engines/table-engines/mergetree-family/mergetree#table_engine-mergetree-ttl)
- [Flink CDC + ClickHouse Sink](https://nightlies.apache.org/flink/flink-cdc-docs/latest/)
- [CDC 最佳实践（ClickHouse 博客）](https://clickhouse.com/blog/clickhouse-change-data-capture)
