# 05 Spark SQL 与 Catalyst

## 一句话

**Spark SQL = SQL 语法 + DataFrame API 共享同一套优化器（Catalyst）和执行引擎（Tungsten）**：同一条逻辑，写 SQL 或写 DataFrame，最终生成的物理执行计划几乎一样，性能也几乎一样。

## SQL 的三种使用姿势

```python
# ① 纯 SQL：临时视图
df.createOrReplaceTempView("orders")
spark.sql("""
    SELECT channel, COUNT(*) AS cnt, SUM(amount) AS gmv
    FROM orders
    WHERE dt = '2026-10-31'
    GROUP BY channel
    ORDER BY gmv DESC
""").show()

# ② 全局临时视图（跨 SparkSession 共享，访问要带前缀）
df.createOrReplaceGlobalTempView("g_orders")
spark.sql("SELECT * FROM global_temp.g_orders")

# ③ 查 Hive 表（需开启 Hive 支持，见下节）
spark.sql("SELECT * FROM ods.user_profile WHERE dt='2026-10-31'")
```

SQL 与 DataFrame 自由混用是常态：**复杂分析写 SQL 表达直观，精细控制切回 DataFrame**。二者结果可以互相转换（`spark.sql()` 返回的就是 DataFrame）。

## 与 Hive 集成

```python
spark = (SparkSession.builder
         .appName("ch05")
         .config("spark.sql.warehouse.dir", "hdfs:///user/hive/warehouse")
         .enableHiveSupport()              # 关键：接管 Hive metastore
         .getOrCreate())
```

| 要点 | 说明 |
| --- | --- |
| 元数据 | 直接复用 Hive Metastore（需把 `hive-site.xml` 放 classpath） |
| 读写 Hive 表 | `spark.table("db.t")`、`df.write.saveAsTable("db.t")` |
| SQL 方言 | Spark SQL 方言与 HiveQL 高度重合但不完全一致；`spark.sql.dialect` 可调 |
| 无 Hive 时 | Spark 用内置 Derby 存元数据（仅本地测试，勿生产） |

常用 SQL 配置开关：

```python
spark.conf.set("spark.sql.shuffle.partitions", 200)      # Shuffle 后默认分区数（重点参数）
spark.conf.set("spark.sql.adaptive.enabled", True)        # AQE（3.x 默认开）
spark.conf.set("spark.sql.parquet.filterPushdown", True)  # Parquet 谓词下推
```

## DataSource API：统一的读写抽象

```
spark.read.format("parquet|json|csv|orc|avro|jdbc|delta|iceberg...")
    .option(...)
    .load(path)

df.write.format(...).mode(...).save(path)
```

| 数据源 | 备注 |
| --- | --- |
| Parquet / ORC | 列存，**生产首选**；支持谓词下推、列裁剪 |
| JDBC | 并行读要配 `partitionColumn/lowerBound/upperBound/numPartitions`，否则单线程拉全表 |
| Kafka | 见第 9 章（流批皆可） |
| Delta / Iceberg / Hudi | 湖仓格式，支持 ACID、时间旅行、Schema 演进，需额外依赖包 |

JDBC 并行读示例：

```python
df = (spark.read.format("jdbc")
      .option("url", "jdbc:mysql://host/db")
      .option("dbtable", "t_order")
      .option("partitionColumn", "id")
      .option("lowerBound", 1).option("upperBound", 10_000_000)
      .option("numPartitions", 20)          # 20 个并行 Task，每个查一段 id 区间
      .option("fetchsize", 10000)
      .load())
```

## Catalyst 优化器：SQL 为什么能自动变快

Catalyst 是 Spark 的查询优化器，把「你写的查询」变成「高效的物理执行」，四个阶段：

```
SQL / DataFrame
   │
   ▼
① 未解析逻辑计划（Unresolved Logical Plan）：列名、表名还是符号
   │  ← Analyzer：查 Catalog 把符号绑定到真实表/列/类型
   ▼
② 逻辑计划（Logical Plan）
   │  ← Optimizer：规则优化（常量折叠、谓词下推、列裁剪、Join 重排…）
   ▼
③ 物理计划（Physical Plan）：候选多个，按代价选最优
   │  ← 如 join 可选 Broadcast / SortMerge / ShuffledHash
   ▼
④ 代码生成（Whole-Stage Codegen）：把多个算子融合生成单条 Java 字节码，消除虚函数调用
```

**你日常能白嫖到的优化**（写对写法就自动生效）：

| 优化规则 | 效果 | 你要做的配合 |
| --- | --- | --- |
| 谓词下推（Predicate Pushdown） | 过滤条件推到数据源层，少读数据 | 用 Parquet；过滤写在读之后尽早 |
| 列裁剪（Column Pruning） | 只扫描用到的列 | 别 `SELECT *` 带着走全程 |
| 常量折叠 / 公共子表达式消除 | 预计算常量、复用计算 | 自动生效 |
| Join 策略选择 | 小表自动广播 | 表统计信息要新鲜（`ANALYZE TABLE`） |
| 动态分区裁剪（3.x DPP） | Join 侧过滤再裁剪扫描分区 | AQE 开启 + 分区表 |

## explain：看懂执行计划（调优起点）

```python
df.explain(True)          # 打印四个阶段的完整计划
df.explain("formatted")   # 只看物理计划（最常用）
```

```
== Physical Plan ==
*(2) Project [channel#12, cnt#34L, gmv#56]
+- *(2) HashAggregate(keys=[channel#12], functions=[count(1), sum(amount#23)])
   +- Exchange hashpartitioning(channel#12, 200)      ← Shuffle 边界
      +- *(1) HashAggregate(keys=[channel#12], functions=[partial_count(1), partial_sum(amount#23)])
         +- *(1) FileScan parquet [channel#12,amount#23] 
                 PushedFilters: [IsNotNull(dt), EqualTo(dt,2026-10-31)],   ← 谓词已下推
                 ReadSchema: struct<channel:string,amount:double>          ← 列已裁剪
```

读计划三看：

1. **看 Exchange**：出现即 Shuffle，数一数几次，是否合理。
2. **看 PushedFilters / PartitionFilters**：过滤有没有推到文件层。
3. **看 Scan 的 ReadSchema**：是不是只读了需要的列。

更细的 `explain("cost")` 还能看 Catalyst 使用的统计信息（行数、大小估计）。

## 统计信息与 CBO

Catalyst 的代价优化（CBO）依赖表统计信息：

```sql
ANALYZE TABLE dwd.orders COMPUTE STATISTICS;                 -- 表级
ANALYZE TABLE dwd.orders COMPUTE STATISTICS FOR COLUMNS id;  -- 列级（含直方图）
```

统计信息陈旧 → Join 策略选错（该广播没广播）→ 任务莫名慢。大表 ETL 后记得更新统计信息。

## 常用 SQL 语法速查（Spark 方言）

```sql
-- LATERAL VIEW：数组/Map 炸裂（等价 DataFrame 的 explode）
SELECT id, tag FROM t LATERAL VIEW explode(tags) x AS tag;

-- 多行转一行
SELECT user_id, collect_list(item_id) AS items, concat_ws(',', collect_set(tag)) 
FROM t GROUP BY user_id;

-- 一行转多行（列转行）
SELECT id, stack(3, 'a', a, 'b', b, 'c', c) AS (k, v) FROM t;

-- 分组取 TopN（窗口）
SELECT * FROM (
  SELECT *, row_number() OVER (PARTITION BY dept ORDER BY salary DESC) rn
  FROM emp
) t WHERE rn <= 3;

-- 拉链表常用：merge（需 Delta/Iceberg）
MERGE INTO target t USING source s ON t.id = s.id
WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *;
```

## 自测

1. 为什么「SQL 写的」和「DataFrame 写的」最终性能几乎一致？
2. `EXPLAIN` 输出里的 `Exchange` 和 `PushedFilters` 各说明什么？
3. JDBC 读大表时，`numPartitions` 少了会怎样？`partitionColumn` 选倾斜列会怎样？
4. 大表 join 后任务突然变慢，怀疑统计信息过期，你会执行什么命令验证/修复？
5. Whole-Stage Codegen 解决的是哪一层开销？

## 参考与官方文档

- [Spark SQL 编程指南](https://spark.apache.org/docs/latest/sql-programming-guide.html)
- [Catalyst 深度剖析（Databricks 博客）](https://www.databricks.com/blog/2015/04/13/deep-dive-into-spark-sqls-catalyst-optimizer.html)
- [Performance Tuning 官方指南](https://spark.apache.org/docs/latest/sql-performance-tuning.html)
