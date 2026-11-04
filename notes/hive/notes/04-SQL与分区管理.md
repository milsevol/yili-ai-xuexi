# 04 SQL与分区管理

## 一句话

HiveQL 是类 SQL 方言，**DDL 建库建表分区分桶、DML INSERT OVERWRITE/INTO 是日常主力**；性能关键是 **分区裁剪**（WHERE 命中分区键），高级特性有 CTE、LATERAL VIEW explode、UDF/UDAF/UDTF。

## DDL 速查

### 建库

```sql
CREATE DATABASE IF NOT EXISTS shop
  COMMENT '电商数仓'
  WITH DBPROPERTIES ('owner'='dwd-team', 'retention'='365d');

DROP DATABASE shop CASCADE;  -- CASCADE 会连同该库下所有表一起删
```

### 建表（含分区 + 分桶 + 存储格式 + 压缩）

```sql
CREATE TABLE IF NOT EXISTS dwd_order (
  order_id    BIGINT       COMMENT '订单主键',
  user_id     BIGINT       COMMENT '用户ID',
  product_id  BIGINT       COMMENT '商品ID',
  amount      DECIMAL(12,2) COMMENT '金额',
  pay_status  TINYINT      COMMENT '支付状态 0/1',
  create_time TIMESTAMP    COMMENT '创建时间'
)
PARTITIONED BY (dt STRING COMMENT '分区键 yyyy-MM-dd')
CLUSTERED BY (user_id) INTO 16 BUCKETS
ROW FORMAT DELIMITED FIELDS TERMINATED BY '\t'
STORED AS ORC
TBLPROPERTIES (
  'orc.compress'='SNAPPY',
  'hive.exec.dynamic.partition'='true'
);

-- 查看表结构
DESCRIBE dwd_order;
DESCRIBE FORMATTED dwd_order;  -- 看分区、桶数、TBLPROPERTIES、LOCATION
```

### 分区操作

```sql
-- 添加分区（外部表常用，内部表 LOAD/INSERT 自动建分区）
ALTER TABLE dwd_order ADD PARTITION (dt='2026-11-03')
  LOCATION '/data/dwd_order/dt=2026-11-03';

-- 重命名分区
ALTER TABLE dwd_order PARTITION (dt='2026-11-01') RENAME TO PARTITION (dt='2026-11-02');

-- 删除分区（Metastore + 数据都删）
ALTER TABLE dwd_order DROP PARTITION (dt='2026-11-01');

-- 修复分区（HDFS 上手动放了新分区目录但 Metastore 还不知道）
MSCK REPAIR TABLE dwd_order;
```

### 修改表结构

```sql
-- 加列
ALTER TABLE dwd_order ADD COLUMNS (ext_info STRING COMMENT '扩展字段');

-- 改列（名字、类型、注释）
ALTER TABLE dwd_order CHANGE COLUMN user_id user_id BIGINT COMMENT '用户ID（已确认）';

-- 改表属性
ALTER TABLE dwd_order SET TBLPROPERTIES ('comment'='订单明细层-2025重构');
```

## DML 速查

### INSERT OVERWRITE vs INSERT INTO

| 语法 | 行为 | 场景 |
| --- | --- | --- |
| `INSERT OVERWRITE` | 先删目标分区/表全部数据，再写入新数据 | **日常 ETL 主力**（幂等） |
| `INSERT INTO` | 追加写入，不删旧数据 | 补数、增量写入 |

```sql
-- OVERWRITE 单分区（幂等重跑，推荐）
INSERT OVERWRITE TABLE dwd_order PARTITION (dt='2026-11-01')
SELECT order_id, user_id, product_id, amount, pay_status, create_time
FROM ods_order WHERE dt='2026-11-01';

-- INTO 全表追加（小心重复）
INSERT INTO TABLE dwd_order PARTITION (dt='2026-11-01')
SELECT * FROM ods_order WHERE dt='2026-11-01';

-- 多分区动态写入（一次写多天数据）
INSERT OVERWRITE TABLE dwd_order PARTITION (dt)
SELECT order_id, user_id, product_id, amount, pay_status, create_time, dt
FROM ods_order WHERE dt BETWEEN '2026-11-01' AND '2026-11-07';

-- 多表多分区同时写（减少扫描）
FROM ods_order
INSERT OVERWRITE TABLE dwd_order PARTITION (dt)
  SELECT order_id, user_id, product_id, amount, pay_status, create_time, dt
INSERT OVERWRITE TABLE dwd_order_daily PARTITION (dt)
  SELECT COUNT(*), SUM(amount), dt GROUP BY dt;
```

### LOAD DATA

```sql
-- 本地文件到 Hive 表（内部表：移动文件到 warehouse）
LOAD DATA LOCAL INPATH '/tmp/demo.csv'
OVERWRITE INTO TABLE dwd_order PARTITION (dt='2026-11-01');

-- HDFS 文件到 Hive 表（内部表：移动；外部表：引用）
LOAD DATA INPATH '/data/raw/2026-11-01.csv'
INTO TABLE dwd_order PARTITION (dt='2026-11-01');
```

## 分区裁剪：性能第一口诀

**WHERE 条件里的分区键必须写成等值比较**，Hive 才能做目录级裁剪。

```sql
-- ✅ 好：分区裁剪生效
SELECT SUM(amount) FROM dwd_order WHERE dt='2026-11-01';
SELECT * FROM dwd_order WHERE dt IN ('2026-11-01', '2026-11-02');
SELECT * FROM dwd_order WHERE dt BETWEEN '2026-11-01' AND '2026-11-07';

-- ❌ 不好：分区裁剪失效，全表扫描
SELECT * FROM dwd_order WHERE substr(dt, 1, 7)='2026-11';
SELECT * FROM dwd_order WHERE dt LIKE '2026-11%';
SELECT * FROM dwd_order WHERE concat('2026', '-', '11', '-', '01') = dt;

-- ❌ 绝对禁止：WHERE 里没有分区键
SELECT * FROM dwd_order WHERE user_id=123;
-- → 全量扫描所有分区，数据量大时直接挂
```

用 `EXPLAIN` 验证分区裁剪：

```sql
EXPLAIN SELECT SUM(amount) FROM dwd_order WHERE dt='2026-11-01';
-- 输出会显示: Partition Specs: [(dt='2026-11-01')] ← 只扫这一个分区

EXPLAIN SELECT * FROM dwd_order WHERE substr(dt,1,7)='2026-11';
-- Partition Specs: [(dt='*')] ← 全分区扫描
```

## CTE（WITH 子句）

```sql
WITH daily_stats AS (
  SELECT dt, user_id, COUNT(*) AS cnt, SUM(amount) AS total
  FROM dwd_order WHERE dt >= '2026-11-01'
  GROUP BY dt, user_id
)
SELECT u.user_id, u.nickname, SUM(ds.total) AS nov_amount
FROM daily_stats ds
JOIN dwd_user u ON ds.user_id = u.user_id
WHERE ds.dt LIKE '2026-11%'
GROUP BY u.user_id, u.nickname;
```

CTE 让复杂查询可读，Hive 会内联展开（不会物化）。

## LATERAL VIEW + explode

把数组/Map 列「炸开」成多行，是宽表中处理 JSON/数组字段的利器：

```sql
-- products 列是 array<struct<id:bigint,name:string,qty:int>>
SELECT order_id, p.id AS product_id, p.name, p.qty
FROM dwd_order_raw
LATERAL VIEW explode(products) ex AS p
WHERE order_id = 1000001;
```

输出：

```
order_id | product_id | name    | qty
---------|------------|---------|-----
1000001  | 501        | 键盘    | 2
1000001  | 502        | 鼠标    | 1
1000001  | 503        | 显示器  | 1
```

### LATERAL VIEW + posexplode

保留数组下标（位置）：

```sql
SELECT order_id, idx, item
FROM dwd_order_raw
LATERAL VIEW posexplode(gift_items) ex AS idx, item;
```

## UDF / UDAF / UDTF

| 类型 | 输入 → 输出 | 例子 |
| --- | --- | --- |
| **UDF**（普通函数） | 一行 → 一行 | `upper()`, `date_add()`, `coalesce()` |
| **UDAF**（聚合函数） | 多行 → 一行 | `COUNT()`, `SUM()`, `AVG()`, `GROUP_CONCAT()` |
| **UDTF**（表生成函数） | 一行 → 多行 | `explode()`, `lateral view` 搭配 |

### 内置函数速查

```sql
-- 字符串
SELECT lower('HELLO'), concat('a','b','c'), split('a,b,c',','), substr('hello',1,3);

-- 日期
SELECT current_date(), date_add('2026-11-01', 7), datediff('2026-11-07','2026-11-01');
SELECT from_unixtime(unix_timestamp(), 'yyyy-MM-dd HH:mm:ss');

-- 条件
SELECT CASE WHEN amount > 1000 THEN 'high' WHEN amount > 100 THEN 'mid' ELSE 'low' END;
SELECT COALESCE(status, 0), IF(amount > 0, 'paid', 'unpaid');

-- 窗口函数（Hive 2.1+）
SELECT user_id, dt, amount,
       SUM(amount) OVER (PARTITION BY user_id ORDER BY dt ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS rolling_7d
FROM dwd_order WHERE dt >= '2026-10-26';
```

### 自定义 UDF（Java 写）

```java
// 简化示例：把金额放大 n 倍
public class MultiplyUDF extends GenericUDF {
  @Override
  public Object evaluate(DeferredObject[] args) throws HiveException {
    Double amount = (Double) args[0].get();
    Double factor = (Double) args[1].get();
    if (amount == null || factor == null) return null;
    return amount * factor;
  }
  // ... 其他方法省略
}
```

```sql
-- 注册临时函数（当前会话有效）
ADD JAR /path/to/my-udf.jar;
CREATE TEMPORARY FUNCTION multiply AS 'com.example.MultiplyUDF';

-- 使用
SELECT multiply(amount, 1.1) AS amount_after_tax FROM dwd_order;
```

## 关键配置

```properties
# —— 动态分区 ——
hive.exec.dynamic.partition=true
hive.exec.dynamic.partition.mode=nonstrict   # strict 至少一个静态分区；nonstrict 允许全动态
hive.exec.max.dynamic.partitions=1000        # 单次 INSERT 最多动态分区数
hive.exec.max.dynamic.partitions.pernode=100

# —— 执行引擎相关 ——
hive.execution.engine=tez
hive.tez.container.size=4096
hive.tez.java.opts=-Xmx3072m

# —— 小文件合并（INSERT OVERWRITE 自动合并）——
hive.merge.mapfiles=true
hive.merge.mapredfiles=true
hive.merge.size.per.task=256000000          # 256MB
hive.merge.smallfiles.avgsize=128000000      # 小于 128MB 触发合并

# —— 自动转换 ——
hive.auto.convert.join=true                  # 小表自动转 MapJoin
hive.auto.convert.join.noconditionaltask.size=10000000  # ≤10MB 自动广播
```

## 常见问题

**Q：INSERT OVERWRITE 跑一半失败，分区数据还在吗？**
A：INSERT OVERWRITE 是先写临时目录 `_tmp`，全部写完再 rename 覆盖目标。中途失败目标分区原有数据不受影响（除非 overwrite 刚开始就删了旧数据）。Hive 4.x 行为更安全。

**Q：动态分区报「Max dynamic partition exceeded」怎么办？**
A：调大 `hive.exec.max.dynamic.partitions` 或 `hive.exec.max.dynamic.partitions.pernode`。但如果单次插入要生成上千分区，建议拆成多次写入。

**Q：EXPLAIN 里 Partitions 显示 `(dt='*')` 是什么意思？**
A：分区裁剪没有生效，会扫所有分区。检查 WHERE 条件里分区键的写法，避免函数包裹分区键。

## 自测

1. 内部表 `t1 PARTITIONED BY (dt)` 有 10 天数据，写一条 INSERT OVERWRITE 只更新 dt='2026-11-01' 的分区，其他分区数据会被删掉吗？
2. 写出一个 INSERT 语句，从 ods_order（有 dt 分区）取 dt='2026-11-01' 到 dt='2026-11-07' 的数据，写入 dwd_order 的对应分区（动态分区）。
3. WHERE 条件里 `substr(dt,1,7)='2026-11'` 和 `dt BETWEEN '2026-11-01' AND '2026-11-30'` 哪个会触发分区裁剪？为什么？
4. LATERAL VIEW explode 是什么？举一个 JSON 数组字段展开的例子。

## 参考与官方链接

- [Hive DDL 官方文档](https://cwiki.apache.org/confluence/display/Hive/LanguageManual+DDL)
- [Hive DML 官方文档](https://cwiki.apache.org/confluence/display/Hive/LanguageManual+DML)
- [Hive UDF 列表](https://cwiki.apache.org/confluence/display/Hive/LanguageManual+UDF)
- [分区裁剪详解](https://cwiki.apache.org/confluence/display/Hive/Partition+Pruning)
