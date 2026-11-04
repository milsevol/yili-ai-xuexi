# 04-数据类型与SQL

## 一句话

ClickHouse 的 SQL 是**类 PostgreSQL 方言**，但有自己的数据类型系统（UInt/Int、FixedString、AggregateFunction）、NULLABLE 设计、和大量高性能函数。核心要避开的坑：**Nullable 列会影响 MergeTree 压缩率和查询性能**、**INSERT 用 VALUES 批量、**函数名大小写敏感**。

## 数据类型大全

### 整数与浮点

| 类型 | 范围 | 存储空间 | 说明 |
| --- | --- | --- | --- |
| Int8 / UInt8 | -128~127 / 0~255 | 1 字节 | — |
| Int16 / UInt16 | -32K~32K / 0~65K | 2 字节 | — |
| Int32 / UInt32 | -21亿~21亿 / 0~42亿 | 4 字节 | — |
| Int64 / UInt64 | ±9.2e18 | 8 字节 | 最常用的整型 |
| Float32 | ±3.4e38（单精度） | 4 字节 | 精度 ~7 位 |
| Float64 | ±1.7e308（双精度） | 8 字节 | 精度 ~15 位，推荐用 |
| Decimal(P, S) | 高精度定点数 | 变长 | P=精度（总位数），S=小数位数 |

```sql
-- Decimal 精确计算，避免浮点误差
CREATE TABLE t_price (
  product_id UInt32,
  price Decimal(10, 2)      -- 最大 99999999.99
) ENGINE = MergeTree() ORDER BY product_id;
```

### 字符串

| 类型 | 说明 | 存储 |
| --- | --- | --- |
| **String** | 变长字符串，UTF-8 或二进制 | 前缀长度 + 内容，LZ4 压缩 |
| FixedString(N) | 定长 N 字节字符串 | 固定 N 字节 |

```sql
-- String 最常用，自动处理压缩
CREATE TABLE t_user (
  name String,              -- 任意长度，LZ4 压缩
  code FixedString(8)       -- 固定 8 字节，短自动补 \0
) ENGINE = MergeTree() ORDER BY name;
```

### 日期与时间

| 类型 | 范围 | 精度 | 说明 |
| --- | --- | --- | --- |
| **Date** | 1970-01-01 ~ 2149-06-06 | 天 | 存储为 UInt16（days since epoch） |
| **Date32** | 1900-01-01 ~ 2299-12-31 | 天 | 存储为 Int32 |
| **DateTime** | 1970-01-01 ~ 2106-02-07 | 秒 | 存储为 UInt32（Unix timestamp） |
| **DateTime64(precision)** | 同上 | 毫秒/微秒/纳秒 | precision: 0~9 |

```sql
-- DateTime64 高精度时间戳
CREATE TABLE t_log (
  ts DateTime64(3),          -- 毫秒精度
  msg String
) ENGINE = MergeTree() ORDER BY ts;

-- 日期分区键常用函数
toYYYYMMDD(dt)     -- 20261103（整数字面量）
toYYYYMM(dt)       -- 202611
toStartOfDay(dt)   -- 2026-11-03 00:00:00
toStartOfHour(dt)  -- 2026-11-03 14:00:00
```

### 复杂类型

| 类型 | 说明 | 示例 |
| --- | --- | --- |
| Array(T) | 同类型数组 | `Array(String)`、`Array(UInt32)` |
| Tuple(T1, T2, ...) | 不同类型元组（命名/不命名） | `Tuple(name String, age UInt32)` |
| Nested | 嵌套表（等价 Array(Tuple(...))) | `Nested(id UInt64, val String)` |
| Map(K, V) | 键值对（24.x 稳定） | `Map(String, UInt64)` |
| AggregateFunction(Func, Args) | 聚合函数状态 | `AggregateFunction(uniq, UInt64)` |
| SimpleAggregateFunction(Func, Args) | 简单聚合函数状态 | `SimpleAggregateFunction(sum, Float64)` |

### Nullable 的坑

**原则：尽量不要用 Nullable！**

```sql
-- ❌ 不推荐
CREATE TABLE t_bad (
  id UInt64,
  amount Nullable(Float64)     -- Nullable 列
) ENGINE = MergeTree() ORDER BY id;

-- ✅ 推荐：给默认值或用默认常量
CREATE TABLE t_good (
  id UInt64,
  amount Float64 DEFAULT 0     -- 给默认值
) ENGINE = MergeTree() ORDER BY id;
```

| 问题 | 原因 |
| --- | --- |
| 压缩率下降 | Nullable 列多一个 `_null` 位图列（单独存储），降低列压缩比 |
| 查询性能下降 | 读两个文件（数据 + null 位图），SIMD 处理时要额外判断 null |
| ORDER BY / PARTITION BY 不能用 | MergeTree 的 ORDER BY 和 PARTITION BY 列**必须是非 Nullable** |
| 类型推断坑 | `Nullable(UInt32)` 和 `UInt32` 混 JOIN 或比较时 ClickHouse 会报错 |

**什么时候可以用 Nullable**：外部 MySQL / Kafka 源数据本身有 NULL，且不会用于 ORDER BY / PARTITION BY。

## DDL：CREATE / ALTER / DROP

### CREATE TABLE

```sql
-- MergeTree 基础建表
CREATE TABLE IF NOT EXISTS orders (
  id UInt64,
  user_id UInt64,
  amount Float64,
  status Enum('pending' = 1, 'paid' = 2, 'cancelled' = 3),
  dt Date DEFAULT today()
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(dt)
ORDER BY (user_id, id)
PRIMARY KEY (user_id, id)
TTL dt + INTERVAL 180 DAY
SETTINGS index_granularity = 8192;

-- 从已有表创建（复制结构）
CREATE TABLE orders_v2 AS orders
ORDER BY id;

-- 临时表（会话级）
CREATE TEMPORARY TABLE t_temp (
  id UInt64, name String
);
```

### ALTER

```sql
-- 添加列
ALTER TABLE orders ADD COLUMN province String DEFAULT '';

-- 修改列类型（要兼容！）
ALTER TABLE orders MODIFY COLUMN amount Decimal(10, 2);

-- 删除列
ALTER TABLE orders DROP COLUMN province;

-- 修改排序键（23.x 后支持）
ALTER TABLE orders MODIFY ORDER BY (id, dt);

-- 添加跳数索引
ALTER TABLE orders ADD INDEX idx_user_id user_id TYPE set(100) GRANULARITY 4;

-- 删除跳数索引
ALTER TABLE orders DROP INDEX idx_user_id;

-- 手动触发 Merge（紧急！一般不需要）
OPTIMIZE TABLE orders FINAL;   -- 强制所有 Part 合并成一个
```

### DROP

```sql
-- 删表（本地表：删物理数据；Distributed：只删定义）
DROP TABLE IF EXISTS orders;

-- 删分区
ALTER TABLE orders DROP PARTITION '20261103';
```

## DML：INSERT / SELECT

### INSERT

```sql
-- ✅ 推荐：批量 VALUES（一次几千行以上）
INSERT INTO orders VALUES
(1, 101, 99.0, 2, '2026-11-03'),
(2, 102, 199.0, 2, '2026-11-03'),
...;

-- ✅ 推荐：从另一个表 SELECT 写入
INSERT INTO orders
SELECT id, user_id, amount, status, dt
FROM staging_orders;

-- ⚠️ 避免：单行多次 INSERT（每个 INSERT 产生一个 Part！）
INSERT INTO orders VALUES (1, 101, 99.0, 2, '2026-11-03');
INSERT INTO orders VALUES (2, 102, 199.0, 2, '2026-11-03');
-- 两次 INSERT = 两个 Part，后续要等 Merge
```

### SELECT

```sql
-- 基础查询
SELECT
  city,
  count() AS total,
  uniqExact(user_id) AS uv,
  sum(amount) AS gmv,
  quantileApprox(0.95)(amount) AS p95_amount
FROM orders
WHERE dt BETWEEN '2026-11-01' AND '2026-11-07'
GROUP BY city
ORDER BY gmv DESC
LIMIT 20;

-- 子查询 + CTE（WITH）
WITH top_cities AS (
  SELECT city, count() AS cnt
  FROM orders WHERE dt >= today() - 30
  GROUP BY city
  ORDER BY cnt DESC
  LIMIT 10
)
SELECT o.city, sum(o.amount)
FROM orders o
INNER JOIN top_cities t ON o.city = t.city
WHERE o.dt >= today() - 7
GROUP BY o.city;

-- FINAL 关键字（查询时强制合并去重，慢）
SELECT * FROM orders FINAL WHERE user_id = 101;
```

## 函数大全

### 聚合函数

| 函数 | 说明 | 示例 |
| --- | --- | --- |
| `count()` | 行数 | `count()` |
| `count(expr)` | 非空值行数 | `count(user_id)` |
| `sum(expr)` | 求和 | `sum(amount)` |
| `avg(expr)` | 平均 | `avg(amount)` |
| `min(expr)` / `max(expr)` | 最小/最大 | `max(amount)` |
| `uniq(expr)` | 去重计数（近似，HyperLogLog） | `uniq(user_id)` |
| `uniqExact(expr)` | 精确去重（慢） | `uniqExact(user_id)` |
| `quantileApprox(q)(expr)` | 分位数（t-digest 近似） | `quantileApprox(0.95)(amount)` |
| `quantileExact(q)(expr)` | 精确分位数（很慢） | — |
| `argMax(val, key)` | key 最大时的 val | `argMax(name, created)` |
| `groupArray(expr)` | 聚合成数组 | `groupArray(product_id)` |

### 窗口函数

```sql
SELECT
  id, user_id, amount,
  row_number() OVER (PARTITION BY user_id ORDER BY amount DESC) AS rn,
  rank() OVER (PARTITION BY city ORDER BY amount DESC) AS rk,
  sum(amount) OVER (PARTITION BY city ORDER BY dt) AS running_sum
FROM orders
WHERE dt >= today() - 7;
```

### 时间函数

| 函数 | 说明 | 示例 |
| --- | --- | --- |
| `now()` | 当前 DateTime | `now()` → `2026-11-04 14:30:00` |
| `today()` | 今天 Date | `today()` → `2026-11-04` |
| `yesterday()` | 昨天 Date | — |
| `toDate(dt)` | DateTime → Date | `toDate(now())` |
| `toYYYYMMDD(dt)` | Date → UInt32 | `toYYYYMMDD(today())` → `20261104` |
| `toStartOfDay(dt)` | 当天 00:00:00 | — |
| `toStartOfMonth(dt)` | 当月第一天 | — |
| `dateDiff('day', d1, d2)` | 日期差 | — |
| `addDays(dt, n)` | 加 n 天 | — |
| `formatDateTime(dt, fmt)` | 格式化 | `formatDateTime(now(), '%Y-%m-%d')` |

### 字符串函数

| 函数 | 说明 |
| --- | --- |
| `length(s)` | 字符串长度（字节） |
| `toUTF8(s)` | 转 UTF-8 |
| `substring(s, start, len)` | 子串 |
| `concat(s1, s2, ...)` | 拼接 |
| `replaceAll(s, old, new)` | 全局替换 |
| `startsWith(s, prefix)` | 前缀判断 |
| `splitByChar(sep, s)` | 按分隔符拆分数组 |

### JSON 支持（22.x+）

```sql
-- 建表时指定 JSON 类型
CREATE TABLE t_events (
  id UInt64,
  data JSON
) ENGINE = MergeTree() ORDER BY id;

-- JSON 类型会自动展开成嵌套列结构
-- 查询 JSON 字段直接用点号
SELECT data.properties.city FROM t_events;

-- 也可以用 JSONExtract 手动解析 String
SELECT
  JSONExtractString(json_column, 'city') AS city,
  JSONExtractInt(json_column, 'count') AS count
FROM t_raw_events;
```

## 关键配置

```sql
-- SQL 级设置
SET max_insert_block_size = 1048576;      -- INSERT 单次 block 行数
SET max_memory_usage = 10000000000;       -- 单查询内存上限（默认 10GB）
SET max_threads = 8;                       -- 查询并行线程数
SET prefer_column_name_to_alias = 1;       -- GROUP BY 中优先用别名

-- 服务器级（config.xml）
<max_server_memory_usage_ratio>0.9</max_server_memory_usage_ratio>
<max_table_size_to_drop>100000000000</max_table_size_to_drop>
```

## 常见问题

**Q：INSERT 为什么慢？**
A：ClickHouse 写入是异步合并模式。如果每次只写几十行、每秒几百次 INSERT，会产生大量小 Part 拖慢查询。**推荐批量写入（单次 5000+ 行）**。

**Q：函数名大小写敏感吗？**
A：默认敏感。`toYYYYMMDD` 和 `toyyyymmdd` 是不同函数。但 ClickHouse 的函数名不区分大小写配置项是 `settings` 里改。

**Q：Array(String) 里能放 NULL 吗？**
A：不能！Array 里的元素不支持 Nullable。如果需要可以用 `Array(Nullable(String))` 但会非常慢。更推荐用特殊值（空字符串）代替 NULL。

**Q：ALTER TABLE MODIFY COLUMN 失败？**
A：通常是新类型和旧类型不兼容。比如 `UInt32 → UInt64` 可以，`Float64 → Decimal(10,2)` 也可以。但 `String → UInt32` 不行。修改是同步重写所有 Part。

## 自测

1. 为什么不推荐在 MergeTree 表的列上用 Nullable？列出三个具体原因。
2. INSERT 写入 ClickHouse 时，批量 VALUES 和单行多次 INSERT 有什么性能差异？原因是什么？
3. ClickHouse 的窗口函数支持哪些？举一个 `row_number() over partition by` 的例子。
4. AggregateFunction 类型在 INSERT 和 SELECT 时分别用什么函数？

## 参考与官方链接

- [数据类型大全](https://clickhouse.com/docs/en/data-types)
- [SQL 语法参考](https://clickhouse.com/docs/en/sql-reference)
- [聚合函数](https://clickhouse.com/docs/en/sql-reference/aggregate-functions)
- [JSON 类型](https://clickhouse.com/docs/en/data-types/json)
- [Nullable 的坑（官方博客）](https://clickhouse.com/blog/nullable-in-clickhouse)
