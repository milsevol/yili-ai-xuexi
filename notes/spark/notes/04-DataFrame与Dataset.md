# 04 DataFrame 与 Dataset

## 一句话

**DataFrame = 带 Schema 的分布式数据表**：在 RDD 之上加「列名 + 类型」结构，让 Catalyst 优化器和 Tungsten 内存引擎替你优化执行——日常开发的主力抽象。

> Dataset 是「带类型的 DataFrame」，仅 Scala/Java 有；**PySpark 里只有 DataFrame**，本章统一讲 DataFrame。

## 三种抽象的取舍

| 维度 | RDD | DataFrame | Dataset（仅 JVM） |
| --- | --- | --- | --- |
| 结构信息 | 无（一堆 Python 对象） | 有 Schema（列名+类型） | 有 Schema + 强类型 |
| 优化器 | 无，原样执行 | Catalyst 全图优化 | 同左 |
| 内存布局 | 堆内对象，开销大 | Tungsten 二进制行格式，省空间 | 同左 |
| 表达能力 | 最自由（任意函数） | 结构化操作 + UDF 兜底 | 两者兼得 |
| 序列化开销（PySpark） | Python↔JVM 全量序列化 | 可用 Arrow 加速 | N/A |
| 适用 | 非结构化、精细控制 | **结构化数据首选** | JVM 强类型项目 |

结论：**PySpark 开发 = DataFrame 优先，RDD 兜底**。性能差距通常 2~5 倍，因为 Catalyst 能做谓词下推、列裁剪、常量折叠，Tungsten 能避免 JVM GC 压力。

## 创建 DataFrame 的常见方式

```python
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, IntegerType

spark = SparkSession.builder.master("local[*]").appName("ch04").getOrCreate()

# 1. 内存数据 + 显式 Schema（推荐：避免类型推断踩坑）
schema = StructType([
    StructField("name", StringType(), True),
    StructField("age",  IntegerType(), True),
])
df1 = spark.createDataFrame([("张三", 30), ("李四", None)], schema)

# 2. 读文件（Parquet 自带 Schema，最省心；CSV/JSON 建议显式给 Schema）
df2 = spark.read.parquet("s3://bucket/events/")
df3 = (spark.read.schema(schema)
            .option("header", True)
            .csv("hdfs:///data/users.csv"))

# 3. 读 Hive 表 / JDBC
df4 = spark.table("ods.user_profile")
df5 = (spark.read.format("jdbc")
            .option("url", "jdbc:mysql://host:3306/db")
            .option("dbtable", "t_order")
            .option("user", "u").option("password", "p")
            .load())
```

**显式 Schema 的三个理由**：① 类型推断要预扫数据，慢；② 推断可能猜错（整数列被猜成 string）；③ 生产代码需要稳定契约。

## 核心操作速查

### 列与行的选择

```python
df.select("name", "age")                          # 选列
df.select(F.col("name"), (F.col("age") + 1).alias("age_next"))
df.selectExpr("name", "age + 1 as age_next")      # SQL 表达式风格
df.withColumn("age2", F.col("age") * 2)           # 增列/覆盖列
df.drop("age")                                    # 删列
df.filter(F.col("age") > 18)                      # = df.where(...)
df.distinct()                                     # 全行去重
df.dropDuplicates(["name"])                       # 按列去重
```

### 聚合与分组

```python
(df.groupBy("dept")
   .agg(F.count("*").alias("cnt"),
        F.avg("salary").alias("avg_sal"),
        F.max("age").alias("max_age"))
   .orderBy(F.desc("cnt")))

df.agg(F.sum("amount"))          # 全局聚合，无 groupBy
df.cube("a", "b").count()        # 多维上卷（还有 rollup）
```

### Join

```python
df1.join(df2, on="id", how="inner")                    # 等值 join
df1.join(df2, df1["a"] == df2["b"], "left")            # 条件 join
df1.join(F.broadcast(df2), "id")                       # 强制广播小表（重要优化）
```

Join 类型：`inner`（默认）`left` `right` `full` `left_semi`（只留匹配行）`left_anti`（只留不匹配行——「剔除黑名单」神器）。

### 行转列 / 列转行 / 炸裂

```python
df.groupBy("day").pivot("city").agg(F.sum("pv"))       # 行转列
df.select("id", F.explode("tags").alias("tag"))        # 数组炸裂成行
df.select("id", F.posexplode("tags"))                  # 带下标炸裂
df.selectExpr("stack(2, 'a', a, 'b', b) as (k, v)")    # 列转行
```

### 窗口函数（分析型需求主力）

```python
from pyspark.sql.window import Window

w = Window.partitionBy("dept").orderBy(F.desc("salary"))
(df.withColumn("rn",   F.row_number().over(w))        # 组内排名（无并列）
   .withColumn("rk",   F.rank().over(w))              # 有并列跳号
   .withColumn("dens", F.dense_rank().over(w))        # 有并列不跳号
   .withColumn("cum",  F.sum("salary").over(w.rowsBetween(
                        Window.unboundedPreceding, Window.currentRow))))
```

经典套路：`row_number() over (partition by 主键 order by 时间 desc) = 1` → **取每组最新一条**（数据去重、拉链表必用）。

## 写出与文件格式

```python
(df.write.mode("overwrite")              # overwrite/append/ignore/error
        .partitionBy("dt", "hour")       # 分区目录，Hive 风格
        .parquet("s3://bucket/dwd/events/"))

df.write.format("delta").save(...)       # 湖仓格式（需装对应包）
```

| 格式 | 特点 | 何时用 |
| --- | --- | --- |
| **Parquet** | 列存、带 Schema、压缩好、谓词下推 | 数仓默认选择 |
| ORC | 列存，Hive 生态亲儿子 | Hive 重度用户 |
| CSV | 文本、无 Schema、慢 | 仅给人看/对接老系统 |
| JSON | 半结构化 | 日志、对接 API |
| Avro | 行存、Schema 演进好 | 流式落盘、数据交换 |

## PySpark 特别注意事项

### 1. UDF 的性能陷阱

```python
# ❌ 普通 Python UDF：每一行都要 JVM → Python 序列化往返，慢一个数量级
@F.udf("string")
def bad_upper(s):
    return s.upper() if s else None

# ✅ 方案一：优先用内置函数（Catalyst 原生执行，零序列化）
df.withColumn("u", F.upper(F.col("name")))

# ✅ 方案二：必须自定义时用 Pandas UDF（Arrow 批量化传输）
from pyspark.sql.functions import pandas_udf

@pandas_udf("string")
def fast_upper(s):
    return s.str.upper()          # 一次处理一批 pandas.Series
```

经验：**能用内置函数就不用 UDF，能 Pandas UDF 就不普通 UDF**。普通 row-at-a-time UDF 是 PySpark 慢的第一大元凶。

### 2. collect / toPandas 的 OOM 陷阱

```python
rows = df.collect()        # ❌ 全量拉回 Driver 内存，大表必死
pdf = df.limit(1000).toPandas()   # ✅ 先限量
pdf = df.toPandas()        # ⚠️ 同上风险；可开 Arrow 加速：
# spark.conf.set("spark.sql.execution.arrow.pyspark.enabled", "true")
```

### 3. Python 与 JVM 的双进程模型

PySpark = Python 进程（你的代码）↔ Py4J ↔ JVM（真正的 Spark 引擎）。跨进程传输越少越好，所以内置函数（在 JVM 内完成）远快于 Python UDF（每行跨进程）。

## 链式风格实战：一个完整的清洗例子

```python
result = (
    spark.read.schema(schema).json("s3://raw/click_log/")
    .filter(F.col("event") == "pay")
    .filter(F.col("amount") > 0)
    .withColumn("dt", F.to_date("ts"))
    .withColumn("hour", F.hour("ts"))
    .dropDuplicates(["order_id"])
    .groupBy("dt", "hour", "channel")
    .agg(F.count("*").alias("orders"),
         F.sum("amount").alias("gmv"))
    .repartition("dt")                       # 按天重分区，便于落盘
    .write.mode("overwrite")
    .partitionBy("dt")
    .parquet("s3://dwd/pay_summary/")
)
```

这段代码值得逐行品味：**读 → 过滤（下推）→ 派生列 → 去重 → 聚合（两阶段）→ 重分区 → 分区落盘**，是离线 ETL 的标准骨架。

## 自测

1. 为什么 DataFrame 通常比手写 RDD 快？说出至少两个机制。
2. `left_semi` join 和 `left_anti` join 分别等价于 SQL 里的什么写法？
3. 生产代码里为什么推荐显式声明 Schema 而不是 `inferSchema`？
4. PySpark 里一个普通 Python UDF 慢在哪一层？两种优化路径是什么？
5. 「取每个用户最近一次登录记录」用窗口函数怎么写？

## 参考与官方文档

- [Spark SQL, DataFrames and Datasets Guide](https://spark.apache.org/docs/latest/sql-programming-guide.html)
- [pyspark.sql.functions 全量函数列表](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/functions.html)
- [Pandas UDF（Vectorized UDF）说明](https://spark.apache.org/docs/latest/api/python/user_guide/sql/arrow_pandas.html)
