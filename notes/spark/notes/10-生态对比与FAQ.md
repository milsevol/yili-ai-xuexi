# 10 生态对比与 FAQ

## 一句话

**学完 Spark 后，还需要知道它「在生态里的位置」**：什么时候该换 Flink、PySpark 和 Scala 怎么选、湖仓格式解决什么痛点、以及面试/工作中的高频问题怎么答。

## Spark vs Flink（选型高频题）

| 维度 | Spark（3.x） | Flink（1.x） |
| --- | --- | --- |
| 核心模型 | 微批（可低到 1 秒）；3.x 有持续处理模式（实验） | 原生流（毫秒级），批是流的特例 |
| 批处理 | **强项**：成熟、生态大、SQL 强 | 可以，但生态和工具链不如 Spark |
| 流处理延迟 | 秒级 | **毫秒级** |
| 状态管理 | 有（mapGroupsWithState），但生态弱 | **强项**：Savepoint、大状态、TTL |
| Exactly-Once | 端到端需 Source/Sink 配合 | **内建两阶段提交 + Checkpoint** |
| 生态/社区 | 大数据事实标准，ML/图/湖仓全 | 实时领域快速增长，阿里背书 |
| 学习曲线 | 平缓（SQL/DataFrame 统一） | 较陡（DataStream API 概念多） |
| 典型场景 | 离线数仓、T+1、交互式分析、ML | 实时风控、实时数仓、CDC、CEP |

**决策树**：

```
需要亚秒级延迟或复杂事件处理（CEP）？ ──是──→ Flink
   │否
   ▼
强状态、大状态、需要 Savepoint 精准控制？ ──是──→ Flink
   │否
   ▼
团队已有 Spark 栈、以离线为主、实时为辅？ ──是──→ Spark
   │否
   ▼
需要 MLlib / 图计算 / 丰富湖仓生态？ ──是──→ Spark
```

**经验**：国内大厂常见「Spark 离线 + Flink 实时」双引擎并存；中小团队若实时要求不高，Spark 一套搞定更简单。

## PySpark vs Scala（语言选择）

| 维度 | PySpark | Scala Spark |
| --- | --- | --- |
| 性能 | 内置函数/UDF 走 JVM，**与 Scala 相当**；普通 Python UDF 慢 | 全部原生 JVM，最快 |
| UDF 生态 | pandas_udf（Arrow 加速）好用 | 原生 UDF 最直接 |
| 源码调试 | 需跳到 JVM 层，栈跨语言 | 直接 |
| 学习门槛 | Python 用户零成本 | 需学 Scala 语法 |
| 社区/岗位 | 数仓、算法、数据科学主流 | 平台/引擎侧、大厂中间件 |
| 新特性 | 跟随 Scala API，偶有延迟 | 首发 |

**结论**：**数据分析/数仓/算法选 PySpark，平台/引擎研发选 Scala**。本系列 PySpark 已覆盖 95% 场景；剩下的 5%（如自定义 Catalyst 规则、复杂状态算子）再补 Scala 不迟。

## 湖仓格式：Delta / Iceberg / Hudi

传统 Hive 表的痛点：不支持 ACID、Schema 演进难、更新删除要整分区重写、批流两份存储。

| 格式 | 背后公司 | 强项 | Spark 集成 |
| --- | --- | --- | --- |
| **Delta Lake** | Databricks | 与 Spark 血缘最深，OPTIMIZE/ZORDER 成熟 | 原生支持最好 |
| **Apache Iceberg** | Netflix/Apple | 隐藏分区、快照隔离、引擎中立（Spark/Flink/Trino 通吃） | 良好，社区增长最快 |
| **Apache Hudi** | Uber |  upsert 强、CDC 场景、增量视图 | 良好 |

**共同能力**：ACID 事务、时间旅行（查历史快照）、Schema 演进、Merge Into、小文件合并。

```python
# Delta Lake 示例（pip install delta-spark）
spark = (SparkSession.builder
         .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
         .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
         .getOrCreate())

df.write.format("delta").mode("overwrite").save("s3://lake/orders")
spark.sql("SELECT * FROM delta.`s3://lake/orders` VERSION AS OF 5")  # 时间旅行
spark.sql("MERGE INTO delta.`s3://lake/orders` t USING updates s ON t.id=s.id WHEN MATCHED THEN UPDATE SET *")
```

**建议**：新项目直接上湖仓格式（Iceberg 引擎中立性最好，Delta 与 Spark 最顺），别再裸 Parquet + Hive 表。

## MLlib 与机器学习生态

Spark MLlib 提供分布式机器学习：

| 模块 | 内容 |
| --- | --- |
| **特征工程** | StringIndexer、OneHotEncoder、VectorAssembler、Bucketizer |
| **算法** | LR/线性回归、随机森林、GBT、KMeans、ALS 推荐、FP-Growth |
| **Pipeline** | 特征 → 训练 → 评估 → 保存，一整套链式 API |
| **分布式** | 数据并行，适合「样本多、特征不极端宽」的场景 |

```python
from pyspark.ml import Pipeline
from pyspark.ml.feature import StringIndexer, VectorAssembler
from pyspark.ml.classification import LogisticRegression

pipeline = Pipeline(stages=[
    StringIndexer(inputCol="label_str", outputCol="label"),
    VectorAssembler(inputCols=["f1","f2","f3"], outputCol="features"),
    LogisticRegression(maxIter=100)
])
model = pipeline.fit(train_df)
model.transform(test_df).select("prediction", "label").show()
```

**什么时候不用 MLlib**：深度学习（用 TensorFlow/PyTorch 单卡或分布式框架）、超宽稀疏特征（用 XGBoost/LightGBM 单机或专用平台）、小数据（pandas/sklearn 单机足够）。

## 高频面试/工作 FAQ

### Q1：Spark 为什么比 MapReduce 快？

**答**：① 内存计算（中间结果尽量不落盘）；② DAG 调度（全局优化，流水线执行）；③ 线程模型（Task 是线程，MR 是进程，启动开销小）。

### Q2：RDD 的弹性体现在哪？

**答**：① 数据弹性（可缓存到内存/磁盘，可重算）；② 容错弹性（血缘重算丢失分区）；③ 资源弹性（动态扩缩 Executor）。

### Q3：宽依赖和窄依赖怎么区分？各自影响？

**答**：看「子分区数据是否来自多个父分区」。窄依赖一对一/多对一，可流水线、容错代价小；宽依赖一对多（Shuffle），切 Stage、容错代价大、是性能瓶颈。

### Q4：cache 和 checkpoint 的区别？

**答**：cache 存内存/磁盘、保留血缘、加速复用；checkpoint 写可靠存储（HDFS）、切断血缘、防长链路重算与栈溢出。常配合用：先 cache 再 checkpoint。

### Q5：什么时候用广播 Join？有什么风险？

**答**：小表（默认 ≤10MB，可调）join 大表时，把小表广播到各 Executor 本地 join，消灭 Shuffle。风险：表太大导致 Executor OOM；`broadcastTimeout` 超时。

### Q6：数据倾斜怎么发现和处理？

**答**：UI 看 Task 耗时/Shuffle Read 分布是否均匀。处理：① 广播小表；② 热点 key 单独处理；③ 加盐两阶段聚合；④ AQE skewJoin；⑤ 过滤/打散无效 key。

### Q7：Spark SQL 的 Catalyst 做了什么？

**答**：把 SQL/DataFrame 解析成逻辑计划 → 规则优化（谓词下推/列裁剪/常量折叠）→ 代价优化选物理计划（Join 策略）→ 全阶段代码生成。用户只需「写对写法」即可白嫖。

### Q8：`spark.sql.shuffle.partitions` 怎么定？

**答**：目标单 Task 处理 100~200MB。总 Shuffle 数据量 ÷ 200MB ≈ 分区数。开 AQE 后可由它自动合并小分区，但上限仍需人工设。

### Q9：PySpark 慢，先查什么？

**答**：① 是否用了普通 Python UDF（换内置函数/pandas_udf）；② 是否 collect/toPandas 了大表；③ Shuffle 是否过重；④ Python worker 内存是否 OOM；⑤ 数据倾斜。

### Q10：流批一体在 Spark 里怎么体现？

**答**：Structured Streaming 用同一套 DataFrame/SQL API 处理流数据，业务逻辑不感知流批；同一份 `process(df)` 函数可跑批也可跑流。

### Q11：Spark 作业的提交流程？

**答**：spark-submit 启动 Driver → 构建 DAG → 遇 Action 生成 Job → DAGScheduler 按 Shuffle 切 Stage → TaskScheduler 分发 Task → Executor 执行 → 结果回 Driver/写存储。

### Q12：Executor 内存怎么分？

**答**：`executor-memory` 堆内分 Execution（Shuffle/聚合缓冲）和 Storage（cache）两区，默认各 50% 可互借；另有 `memoryOverhead` 堆外（网络/PySpark worker）。`spark.memory.fraction=0.6` 控制堆内占比。

## 学习资源与下一步

| 类型 | 推荐 |
| --- | --- |
| 官方文档 | https://spark.apache.org/docs/latest/（常读常新） |
| 书 | 《Learning Spark 2nd Edition》（免费 PDF）、《Spark 快速大数据分析》 |
| 源码 | `sql/core`、`sql/catalyst` 模块（Scala） |
| 社区 | Databricks 博客、Spark Summit 视频 |
| 下一步 | ① 把本系列例子在本机 PySpark 全跑一遍；② 找一个公开数据集（如 NYC Taxi）做端到端 ETL + 调优；③ 学 Delta Lake 或 Iceberg；④ 需要实时再看 Flink |

## 自测

1. 你们团队要做「实时反欺诈（200ms 内响应）」和「T+1 离线报表」，分别推荐什么引擎？为什么？
2. 为什么湖仓格式（Delta/Iceberg）正在取代裸 Hive 表？至少说出三个能力。
3. PySpark 和 Scala Spark 在「内置函数调用」上性能有差异吗？差异主要在哪类操作上？
4. 一个 5GB 的日批 ETL，你会把 `spark.sql.shuffle.partitions` 设成多少？依据？
5. MLlib 不适合哪三类场景？分别推荐什么工具？

## 参考与官方文档

- [Spark 官方文档总入口](https://spark.apache.org/docs/latest/)
- [Delta Lake 官方](https://delta.io/) / [Apache Iceberg](https://iceberg.apache.org/) / [Apache Hudi](https://hudi.apache.org/)
- [Flink 官方（对比参考）](https://nightlies.apache.org/flink/flink-docs-stable/)
- [MLlib 指南](https://spark.apache.org/docs/latest/ml-guide.html)
