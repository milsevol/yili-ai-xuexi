# 08 ACID 与事务

## 一句话

Hive 的 ACID 是 **3.x 引入、4.x 加强** 的特性——核心是 **ORC 文件格式 + Bucket 分桶表 + Compaction 文件合并机制**，解决「HDFS 文件不能原地改写」的限制，实现 **MERGE/UPDATE/DELETE** 以及事务型写入。但相比 Iceberg/Hudi/Delta Lake，Hive ACID 只支持 ORC、只能操作 Bucket 表，功能边界有限。

## 为什么 HDFS 不支持事务

HDFS 文件是**只追加（append-only）**的，不能原地修改。这意味着：

| 关系型数据库 | HDFS |
| --- | --- |
| UPDATE t SET x=2 WHERE id=1 → 直接改文件中的行 | 只能**新建一个包含修改后数据的新文件**，再覆盖旧文件 |
| DELETE FROM t WHERE id=1 → 直接标记行删除 | 只能**新建一个去掉被删行的新文件**，再覆盖旧文件 |
| 事务（BEGIN/COMMIT/ROLLBACK）有 WAL 日志 | 没有 WAL，写失败只能重试，回滚靠「不提交 rename」 |

Hive ACID 的思路：**把「原地更新」翻译成「生成新文件 + 后台定期合并（Compaction）」**。

## Hive ACID 的三个必要条件

```
Hive ACID = ORC 文件格式 × Bucket 分桶表 × Compaction
```

| 条件 | 原因 |
| --- | --- |
| **ORC 存储格式** | ORC 有 ACID 专用的文件 Footer 和 Delta 目录结构，支持 Base → Delta 合并 |
| **Bucket 分桶表** | 同一 bucket 的所有行在物理上集中在一个文件组，Compaction 才能合并 |
| **Compaction 后台服务** | 定期把 Base + Delta 合并成新的 Base，控制文件数量 |

### 创建事务表

```sql
CREATE TABLE IF NOT EXISTS dwd_order_txn (
  order_id    BIGINT        COMMENT '订单ID',
  user_id     BIGINT        COMMENT '用户ID',
  amount      DECIMAL(12,2) COMMENT '金额',
  pay_status  TINYINT       COMMENT '支付状态',
  pay_time    TIMESTAMP     COMMENT '支付时间'
)
PARTITIONED BY (dt STRING)
CLUSTERED BY (user_id) INTO 16 BUCKETS    -- ✅ 必须分桶
STORED AS ORC                              -- ✅ 必须 ORC
TBLPROPERTIES (
  'transactional' = 'true',                -- ✅ 标记事务表
  'orc.compress' = 'SNAPPY',
  'hive.acid.version' = '2'                -- ACID v2（默认）
);
```

**非事务表（对比）**：

```sql
-- 普通 ORC 表，不是事务表，不能 UPDATE/DELETE
CREATE TABLE dwd_order_normal (...)
STORED AS ORC
TBLPROPERTIES ('transactional'='false');
```

## 文件结构：Base + Delta + Compaction

ACID 表在 HDFS 上的目录结构：

```
/user/hive/warehouse/default.db/dwd_order_txn/dt=2026-11-03/
  ├── base_0000001/           ← 初始数据（Insert Into）
  │   ├── bucket_00000.orc
  │   └── ...
  ├── delta_0000001_0000001/  ← 第 1 次 UPDATE/DELETE
  │   └── bucket_00000.orc    ← 只存变化行（带 OPERATION_TYPE 元数据）
  ├── delta_0000002_0000002/  ← 第 2 次操作
  │   └── bucket_00000.orc
  └── ...
```

**每次 UPDATE/DELETE 不会修改 base 文件**，只会生成一个新的 delta 目录。查询时 Hive ORC Reader 会自动 merge base + 所有 delta。

### Compaction 合并

delta 文件太多会让查询变慢（每次要合并 N 个 delta）。**Compaction** 就是后台服务定期把 base + 多个 delta 合并成一个新的 base：

```
Compaction 之前：
  base_1 + delta_2 + delta_3 + delta_4   → 查询时 merge 3 次

Compaction 之后：
  base_5（合并了 base_1 + delta_2 + delta_3 + delta_4）→ 查询时只读 1 个 base
```

两种 Compaction 策略：

| 策略 | 做法 | 触发条件 |
| --- | --- | --- |
| **Minor Compaction** | 多个 delta 合并成一个 delta（不改 base） | delta 文件数 > hive.compaction.min.filecount |
| **Major Compaction** | base + 所有 delta 合并成新 base | delta 文件数 > hive.compaction.max.filecount |

```properties
# Compaction 配置（4.x 默认开启）
hive.compactor.initiator.on=true                      # 开启 Compaction 服务
hive.compactor.worker.threads=1                       # worker 线程数

hive.compaction.min.filecount=4                       # delta 超过 4 个触发 Minor
hive.compaction.max.filecount=50                      # delta 超过 50 个触发 Major
hive.compaction.min.size=200000000                    # base 小于 200MB 时更积极合并
hive.compaction.delay.between.runs.insec=100          # Compaction 检查间隔
```

**手动触发 Compaction**：

```sql
-- Minor Compaction
ALTER TABLE dwd_order_txn PARTITION (dt='2026-11-03') COMPACT 'MINOR';

-- Major Compaction
ALTER TABLE dwd_order_txn PARTITION (dt='2026-11-03') COMPACT 'MAJOR';

-- 查看状态
SHOW COMPACTIONS;
```

## MERGE / UPDATE / DELETE 语法

### MERGE INTO（最强大：同时做 INSERT + UPDATE + DELETE）

```sql
-- 场景：CDC 落了一份订单增量，MERGE 合并到事务表
MERGE INTO dwd_order_txn t
USING ods_order_inc s
ON t.order_id = s.order_id AND t.dt = s.dt
WHEN MATCHED AND s.pay_status = 2 THEN DELETE           -- 退款 → 删除
WHEN MATCHED THEN UPDATE SET t.amount = s.amount, t.pay_status = s.pay_status
WHEN NOT MATCHED THEN INSERT (order_id, user_id, amount, pay_status, pay_time)
       VALUES (s.order_id, s.user_id, s.amount, s.pay_status, s.pay_time);
```

### UPDATE

```sql
UPDATE dwd_order_txn
SET pay_status = 1, pay_time = CURRENT_TIMESTAMP
WHERE order_id = 1000001 AND dt = '2026-11-03';
```

### DELETE

```sql
DELETE FROM dwd_order_txn
WHERE pay_status = 2 AND dt = '2026-11-03';  -- 删除所有退款订单
```

**注意**：WHERE 条件里最好包含分区键（dt），否则会扫所有分区，性能极差。

## ACID v1 vs ACID v2

| 版本 | 引入 | 区别 |
| --- | --- | --- |
| ACID v1 | Hive 0.13 | 每一行带 `ROW_ID`（全局唯一递增 ID），Merge 逻辑简单但空间浪费 |
| **ACID v2** | Hive 2.0 | **不需要 ROW_ID**，Compaction 更高效，支持 CDC |

**4.x 默认 v2**。新表直接用 v2，旧表可以升级（建一个新表 v2 格式 + INSERT OVERWRITE 迁移数据）。

## ACID 的限制

Hive ACID 功能相对有限，这也是 Iceberg/Hudi/Delta 流行的原因：

| 限制 | 说明 |
| --- | --- |
| **只支持 ORC** | Parquet / TextFile / Avro 都不支持 |
| **必须 Bucket 分桶** | 分桶数一旦建表固定，不能改 |
| **Bucket 表不能 Insert Into（只能 Insert Overwrite）** | 3.x 限制，4.x 部分放开 |
| **不支持直接 Update 非 Bucket 表** | 只能 MERGE |
| **不支持跨分区 Update/Delete** | 每次操作只能涉及一个分区或用动态分区 |
| **Compaction 有延迟** | delta 文件存在期间查询性能略差 |

## CDC 写入场景

CDC（Change Data Capture）把 MySQL/PostgreSQL 的变更实时同步到数仓，Hive ACID 是承接 CDC 的天然载体：

```
MySQL 业务库 → Debezium CDC → Kafka → Flink 消费 → MERGE INTO Hive ACID 表
                                                          ↓
                                              Hive 事务表（实时同步的业务镜像）
```

```sql
-- Flink CDC 直接写 Hive 事务表（Hive Catalog + MERGE）
-- Flink SQL 示例（简化）
CREATE TABLE mysql_cdc_source (...) WITH ('connector'='mysql-cdc', ...);
CREATE TABLE hive_acid_target (...) WITH ('connector'='hive',
  'hive-version'='4.0',
  'table.transactional'='true',
  'sink.merge-key'='order_id,dt');

INSERT INTO hive_acid_target
SELECT order_id, user_id, amount, pay_status, pay_time, dt
FROM mysql_cdc_source;
```

## Hive ACID vs Iceberg vs Hudi vs Delta

| 维度 | Hive ACID | Iceberg | Hudi | Delta Lake |
| --- | --- | --- | --- | --- |
| 引入 | Hive 0.13 | Netflix 2018 | Uber 2018 | Databricks 2019 |
| 存储格式 | **只能 ORC** | **ORC / Parquet / Avro 都支持** | **ORC / Parquet / Avro** | **Parquet 为主** |
| 分桶要求 | **必须 Bucket 分桶** | 可选分桶 | 可选 Bucket | 可选 Bucket |
| Compaction | Minor + Major，后台 | **可手动 / 自动 / 调度** | **Clustering + Compaction** | OPTIMIZE / ZORDER |
| Schema 演进 | 只支持加列/改列类型 | **完整支持**（加/删/改/重命名） | **支持** | **完整支持** |
| Time Travel | 不支持 | ✅ 支持 Snapshot | ✅ 支持 Timeline | ✅ 支持 Version |
| 生态 | 只 Hive | Spark / Flink / Trino / Hive | Spark / Flink / Hive / Presto | Spark / Flink / Hive / Trino |
| 成熟度 | 够用但有限 | 最成熟、社区最大 | 活跃中 | Spark 生态最完善 |

**湖仓一体趋势**：Iceberg/Hudi/Delta 正在取代 Hive ACID 的地位，因为它们不绑定 ORC、不强制 Bucket、Schema 演进更灵活。今天新项目直接用 Iceberg 作为表格式，Hive Metastore 继续作为元数据中心。

## 关键配置

```properties
# ============ ACID 开启 ============
hive.txn.manager=org.apache.hadoop.hive.ql.lockmgr.DbTxnManager   # 默认 DbTxnManager
hive.compactor.initiator.on=true
hive.compactor.worker.threads=1

# ============ Compaction 参数 ============
hive.compaction.min.filecount=4
hive.compaction.max.filecount=50
hive.compaction.min.size=200000000

# ============ 事务超时 ============
hive.txn.timeout=300                   # 事务超时 300s
hive.txn.max.open.txns=10000

# ============ 强制 ACID 写入（避免误写非事务表） ============
hive.strict.checks.bucketing=true
```

## 常见问题

**Q：非事务表（TBLPROPERTIES('transactional'='false')）能执行 MERGE 吗？**
A：不能。MERGE 会报错误：`MERGE is not supported for non-transactional tables`. 事务写入前先 DESCRIBE FORMATTED 确认表是事务表。

**Q：Compaction 会让查询变慢吗？**
A：Compaction 本身是读旧文件 + 写新文件，CPU/IO 开销大，建议低峰期（凌晨）跑。Compaction 完之后查询会变快（少了 N 个 delta 需要 merge）。

**Q：Hive ACID 表怎么从旧版本迁移？**
A：最稳妥：新建事务表（带 CLUSTERED BY + TBLPROPERTIES），然后 `INSERT OVERWRITE 新表 SELECT * FROM 旧表`。也可以直接 `ALTER TABLE ... SET TBLPROPERTIES('transactional'='true')`（但要求已有 bucket 分桶）。

**Q：Iceberg/Hudi/Delta 能不能接 Hive Metastore？**
A：**完全可以**。湖仓表的 Catalog 后端支持 Hive Metastore，Spark/Flink/Trino 通过 Hive Metastore 拿到表结构后直接读 Iceberg/Hudi/Delta 的文件格式。Hive Metastore 继续当"元数据中心"，Hive ACID 则逐步被湖仓表取代。

## 自测

1. 用一句话说清 Hive ACID 的三个必要条件（ORC + Bucket + Compaction）各自解决什么问题。
2. 写出一个 MERGE INTO 示例：从 ods_order_inc（增量）合并到 dwd_order_txn（事务表），有三种情况：INSERT / UPDATE / DELETE。
3. 说说 delta 文件太多会对查询性能造成什么影响，Compaction 是怎么解决的。
4. Hive ACID 为什么正在被 Iceberg/Hudi/Delta 取代？从存储格式、分桶要求、Schema 演进三个维度对比。

## 参考与官方链接

- [Hive Transactions 官方文档](https://cwiki.apache.org/confluence/display/Hive/Hive+Transactions)
- [ACID v2 设计文档](https://cwiki.apache.org/confluence/display/Hive/Acid+Transactions+Beeline+Examples)
- [Iceberg vs Hudi vs Delta 对比（2026）](https://github.com/apache/iceberg)
- [Hive 4.x ACID 新特性](https://cwiki.apache.org/confluence/display/hive/Hive4NewFeatures)
