# 06 执行引擎与 Tez/Spark 切换

## 一句话

Hive 的 SQL 解析和元数据是固定的，但**真正跑查询的执行引擎可以换**——从最早的 **MapReduce**（3.x 默认，4.x 废弃）→ **Tez**（4.x 默认，DAG 减少中间落盘）→ **Spark**（可选，迭代计算快，支持 Catalyst）→ **Flink**（4.x 新增，流批一体）。切换只需一条 `SET hive.execution.engine=xxx`。

## 三种核心引擎对比

| 维度 | MapReduce | Tez | Spark |
| --- | --- | --- | --- |
| **引入** | Hive 1.x 默认 | Hive 0.14+ 支持，4.x 默认 | Hive 1.5+ 支持，Spark 是独立项目 |
| **依赖** | YARN | YARN + Tez DAGAppMaster | YARN / Standalone / K8s |
| **计算模型** | Map → Reduce（至少 2 阶段） | 通用 DAG（任意拓扑，无固定 2 阶段） | RDD + DataFrame + Catalyst |
| **中间结果** | **必须落盘**（Map 输出 → Reduce 拉取） | **内存优先，溢写磁盘** | 默认内存，Spark Shuffle 可配置磁盘 |
| **迭代支持** | ❌（多个 MR 作业链式跑，反复落盘） | ❌（DAG 一次跑完，不支持循环） | ✅（原生支持循环、RDD lineage） |
| **性能（同查询）** | 基准 1x | **5–10x** | **10–30x**（依赖 Spark 版本与 Catalyst 优化） |
| **默认引擎状态** | 3.x 默认，4.x **deprecated** | 4.x 默认 | 可选，需预装 Spark |

## 为什么 MapReduce 被淘汰

MapReduce 的本质是**固定两阶段 + 强制落盘**：

```
MapReduce 跑一条 JOIN 要 4 阶段落盘：
  Map(orders) → Shuffle 落盘 → Reduce(SortMerge 阶段 1)
  Map(users)  → Shuffle 落盘 → Reduce(SortMerge 阶段 2) → 最终 JOIN → Output
```

每一次 Shuffle 都意味着「网络传输 + 磁盘随机写」，延迟高、带宽浪费。Hive 3.x 的 MR 引擎就是不断提交 MR 作业，一个复杂查询可能拆成 5–10 个 MR。

## Tez：把多个 MR 合并成一个 DAG

Tez 的核心思想是 **有向无环图（DAG）**，一次提交一个 DAG，中间节点不落盘：

```
Tez DAG（一条 JOIN 查询）：
  Source(orders) ─→ Filter ──┐
                              ├→ Map端本地聚合 → Shuffle（一次）→ Reduce端 JOIN → Aggregate → Sink
  Source(users)  ─→ Filter ──┘
                              ↑
                         只有这一处需要跨节点 Shuffle
```

| Tez 相比 MR 的优势 | 说明 |
| --- | --- |
| **减少 Shuffle 次数** | MR 至少两次 Shuffle（Map→Reduce），Tez 只在必要时 Shuffle |
| **中间不落盘** | Map 输出直接推送到下游 Reduce（管道式传输） |
| **通用 Task 类型** | Mapper / Reducer / Processer / Merge / Composite — 自定义，不限于 Map/Reduce |
| **AM 常驻** | DAGAppMaster 一次启动，多个 Task 在同一个 JVM 里跑 |

### Tez DAG 真实截图含义

Hive on Tez 提交到 YARN 后，YARN UI 里可以看到一个 DAGAppMaster（ApplicationMaster）。AM 的 Web UI（通常在 YARN Container Logs 里）会展示 DAG 拓扑：

```
DAG: [Map 1] → [Shuffle 1] → [Reduce 1] → [Map 2] → [Shuffle 2] → [Reduce 2]
      (orders filter)                        (join 执行)
```

每个节点显示：输入 records、输出 records、平均 task 时间、是否有 data skew。

## Spark：Catalyst + 迭代

Hive on Spark 的本质是：**Hive 负责 SQL 解析和 Metastore 查询，Spark 负责物理计划生成和执行**。

```
用户提交: SELECT COUNT(*) FROM orders JOIN users ...

Hive 侧：
  Parse（Antlr）→ AST → 语义分析（查 Metastore 拿表结构/分区）
  → 生成逻辑计划（Hive Logical Plan）
  → 转成 Spark Logical Plan（SparkPlan）

Spark 侧：
  Catalyst 优化器（Rule 遍历）→ 物理计划选择
  → RDD DAG → Stage 划分 → Task 分发
  → Executor 执行
```

| 场景 | 谁赢 | 原因 |
| --- | --- | --- |
| 一次性大表 JOIN（GB 级，静态分区） | Tez 或 Spark 持平 | 都是 Shuffle + SortMergeJoin |
| 迭代查询（先聚合 A，聚合结果再聚合 B） | **Spark** | 可以把中间结果缓存，Tez 只能跑一次 DAG |
| 机器学习（MLlib / 图计算） | **只能 Spark** | Tez 和 MR 完全不支持 |
| 小表 JOIN（< 10MB 广播） | **Spark** | Catalyst 自动转 BroadcastHashJoin，Tez 也要配 hive.auto.convert.join |
| 写 HDFS（INSERT OVERWRITE） | Tez 略稳 | Spark 写小文件问题需要额外处理（coalesce / repartition） |

## Flink：4.x 新选项

Hive 4.x 新增了 `hive.execution.engine=flink` 的支持，本质是把 HiveQL 解析后转成 Flink 的 Table API。优势是**流批一体**——同一个建表，Flink 可以做流式写入，Hive on Flink 可以做批式查询。但目前社区还在完善，生产主流仍是 Tez 和 Spark。

## 引擎切换实战

### 切到 Tez（Hive 4.x 默认）

```bash
# 1) 确认 Tez 依赖已部署（Hadoop 集群要有 Tez 的 tar.gz）
ls /opt/hadoop/share/hadoop/tools/lib/hive-hcatalog-core-*.jar
# 或：hive --version 看 Tez 相关 jar 是否在 CLASSPATH

# 2) hive-site.xml 配置
```

```xml
<property>
  <name>hive.execution.engine</name>
  <value>tez</value>
</property>
<!-- Tez 容器大小 -->
<property>
  <name>hive.tez.container.size</name>
  <value>4096</value>    <!-- MB，单个 Tez Task 的 YARN 容器 -->
</property>
<property>
  <name>hive.tez.java.opts</name>
  <value>-Xmx3072m</value> <!-- JVM 堆，比容器小 ~20% -->
</property>
```

### 切到 Spark

```bash
# 1) 集群上必须有 Spark（Spark 3.x，与 Hive 版本对应）
export SPARK_HOME=/opt/spark
export SPARK_YARN_JAR=/opt/spark/jars/spark-yarn_*.jar

# 2) hive-site.xml
```

```xml
<property>
  <name>hive.execution.engine</name>
  <value>spark</value>
</property>
<!-- Spark AM 内存 -->
<property>
  <name>spark.yarn.am.memory</name>
  <value>4g</value>
</property>
<!-- Spark 执行器内存 -->
<property>
  <name>spark.executor.memory</name>
  <value>8g</value>
</property>
```

```sql
-- 会话级别切，不用重启 HS2
SET hive.execution.engine=spark;
SELECT * FROM dwd_order_detail WHERE dt='2026-11-03';
-- Spark UI 可以看到对应的 SQL 查询在跑
```

### 运行时看引擎

```sql
-- Beeline 会话里可以随时切
SET hive.execution.engine=tez;
SELECT * FROM dwd_order_detail LIMIT 10;  -- 用 Tez

SET hive.execution.engine=spark;
SELECT * FROM dwd_order_detail LIMIT 10;  -- 用 Spark

SET hive.execution.engine=mr;             -- 4.x 会提示 deprecated
```

EXPLAIN 可以看引擎生成的物理计划：

```sql
EXPLAIN FORMATTED
SELECT COUNT(*) FROM dwd_order_detail WHERE dt='2026-11-03';
```

| 引擎 | EXPLAIN 关键输出 |
| --- | --- |
| Tez | `Stage-0: Map → Reduce`、`Edge [SHUFFLE]`、`Vertex CustomName` |
| Spark | `Project`、`HashAggregate`、`Exchange`、`SortMergeJoin`、`BroadcastHashJoin` |
| MR | `Map Operator Tree`、`Reduce Operator Tree` |

## Tez DAG vs Spark DAG 内部对比

```
同一个复杂查询：
SELECT o.order_id, u.nickname, p.product_name, SUM(o.amount)
FROM dwd_order_detail o
JOIN dwd_user u ON o.user_id = u.user_id
JOIN dwd_product p ON o.product_id = p.product_id
WHERE o.dt='2026-11-03'
GROUP BY o.order_id, u.nickname, p.product_name;
```

```
Tez 生成的 DAG（3 源 + 2 JOIN + 聚合 + Sink）：

  [Source orders] → [Filter] → [Map端聚合]
                                      ├→ [Shuffle 1] → [Reducer: 第一阶段 Join]
  [Source users]  → [Filter] → [Map端聚合]
                                      ├→ [Shuffle 2] → [Reducer: 第二阶段 Join + 聚合] → [Sink]
  [Source product]→ [Filter] → [Map端聚合]

特点：2 次 Shuffle，DAGAM 常驻，中间结果不落盘
```

```
Spark 生成的 DAG（Catalyst 先做谓词下推 + 列裁剪）：

  [orders Partition(dt)] → [Filter(dt=...)] → [Exchange] → [Shuffle]
                                                              ↓
  [users] → [Exchange] → [Shuffle] → [SortMergeJoin: orders × users]
                                              ↓
  [product] → [Broadcast（< spark.sql.autoBroadcastJoinThreshold）]
                                              ↓
                              [BroadcastHashJoin: × product]
                                              ↓
                                        [HashAggregate]
                                              ↓
                                           [Exchange → Collect]

特点：Catalyst 可能把 product 广播掉（<10MB），2 次 Exchange（Shuffle）可合并，
      中间结果在 Executor 内存，有 lineage 容错
```

## 引擎选择建议

| 场景 | 推荐引擎 | 理由 |
| --- | --- | --- |
| 离线数仓 ETL（每日批量写入） | **Tez**（4.x 默认） | 稳定成熟、DAG 紧凑、社区主力 |
| 交互式 ad-hoc（秒级返回） | **Spark** 或 Trino | Spark Catalyst 快；Trino 纯内存列式更快 |
| 迭代式聚合 / 机器学习 | **Spark** | Tez 和 MR 完全不支持迭代 |
| 需要流批一体 | **Spark Structured Streaming** / **Flink** | Hive on Spark 可以接 Structured Streaming |
| 存量 Hive 3.x 集群 | 先 **MR**，逐步切 **Tez** | 切引擎需验证现有 SQL 的行为变化 |

## 关键配置

```properties
# ============ hive-site.xml 必须项 ============
hive.execution.engine=tez   # tez | spark | mr | flink

# ============ Tez 相关 ============
hive.tez.container.size=4096
hive.tez.java.opts=-Xmx3072m
hive.tez.dag.recovery.enabled=true        # DAG 失败自动重试
hive.tez.dag.recovery.duplicate.task.status.check.interval.ms=1000

# ============ Spark 相关 ============
spark.yarn.am.memory=4g
spark.executor.memory=8g
spark.executor.cores=4
spark.sql.autoBroadcastJoinThreshold=10485760   # 10MB
spark.sql.adaptive.enabled=true                 # AQE 自适应执行
spark.sql.shuffle.partitions=200

# ============ MR（3.x 常用） ============
mapreduce.job.maps=-1                 # 自动按 Split 数
mapreduce.job.reduces=-1              # Hive 自动算 Reducer 数
mapreduce.map.memory.mb=4096
mapreduce.reduce.memory.mb=8192
```

## 常见问题

**Q：Hive on Tez 和 Hive on Spark 哪个快？**
A：简单聚合查询 Tez 快一点（AM 常驻 + DAG 紧凑）；涉及多次 JOIN、大表 Shuffle、需要广播小表时，Spark Catalyst 优化后可能更快。实测为准。

**Q：切了 Spark 之后，原来 Tez 下的 SQL 会报错吗？**
A：绝大多数不会。HiveQL 解析层是一样的，Spark 执行层只是换了执行器。但极少数函数（如 Hive 特有的 UDF）需要 Spark 里也注册。

**Q：Hive 4.x 彻底移除 MR 了吗？**
A：没有彻底移除，但标记为 `[deprecated]`，新版本不再维护 MR 相关代码。建议新项目直接用 Tez 或 Spark。

**Q：如何确认集群上 Tez 正常？**
A：`hive --service tez-dag` 跑一个简单查询看 DAG 生成；或者 `hive.execution.engine=tez` 后 `EXPLAIN FORMATTED SELECT 1` 看是否有 Tez Stage。

## 自测

1. 用一句话说清 MR、Tez、Spark 各自的核心计算模型，以及为什么 MR 被淘汰。
2. Hive 里切换执行引擎的 SQL SET 命令是什么？切了之后 Metastore 会不会跟着换？
3. Tez 的 DAG 相比 MR 的两阶段模型，在同一个 JOIN 查询上减少了什么开销？
4. Spark on Hive 和原生 Spark SQL 连接 Hive Metastore，有什么本质区别？（提示：SQL 解析层）

## 参考与官方链接

- [Hive on Tez 官方文档](https://cwiki.apache.org/confluence/display/Hive/Hive+on+Tez)
- [Hive on Spark 官方文档](https://cwiki.apache.org/confluence/display/Hive/Hive+on+Spark%3A+Getting+Started)
- [Apache Tez 项目站](https://tez.apache.org/)
- [Spark Catalyst 优化器深入](https://spark.apache.org/docs/latest/sql-performance-tuning.html)
