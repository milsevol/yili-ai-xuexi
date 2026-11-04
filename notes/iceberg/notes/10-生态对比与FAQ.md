# 10 生态对比与 FAQ

## 一句话

Iceberg、Hudi、Delta Lake、Paimon 都是「湖仓表格式」，解决的痛点是同一组（ACID、演进、Time Travel），但**写入模型、索引设计、生态绑定**不同：**通用开放 + 多引擎选 Iceberg，高频 CDC Upsert 选 Hudi，深度绑定 Spark/Databricks 选 Delta，Flink 流批一体选 Paimon**。

## 四者定位

| | Iceberg | Hudi | Delta Lake | Paimon |
| --- | --- | --- | --- | --- |
| 出身 | Netflix → Apache | Uber → Apache | Databricks → Linux 基金会 | Flink 社区 → Apache |
| 元数据 | 元数据树 + Manifest | Timeline（instant 序列） | `_delta_log` JSON | 快照 + Manifest（类 Iceberg） |
| 写入模型 | COW + MOR（delete file） | COW + MOR（最成熟） | COW（Deletion Vector 补 MOR） | COW + MOR（LSM 风格） |
| 隐藏分区 | ✅ | ❌ | ❌ | ✅（部分） |
| 分区演进 | ✅ 不重写 | 有限 | 有限 | ✅ |
| 多引擎 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐（Flink 最强） |
| 社区 | 最活跃 | 活跃 | 活跃（Databricks 主导） | 快速增长（国内尤其） |
| 最强场景 | 多引擎开放表格式 | CDC Upsert / 增量拉取 | Spark / Databricks 一体 | Flink 流批一体 |

## 深度对比：写入模式

### Copy-on-Write（COW）

```
UPDATE id=1：
  读包含 id=1 的整个 Data File
  → 重写去掉旧行、加上新行的新文件
  → 旧文件标记删除
优点：读快（没有 delete file 要合并）
缺点：写放大（改 1 行可能重写 128MB）
```

### Merge-on-Read（MOR）

```
UPDATE id=1：
  写一个 delete file（记录 id=1 的位置/值）+ 一个包含新行的 data file
  → 查询时 merge
优点：写快（适合高频 CDC）
缺点：读慢（要合并 delete file），需要定期 compaction
```

| | COW | MOR | 说明 |
| --- | --- | --- | --- |
| Iceberg | ✅ `write.*.mode=copy-on-write` | ✅ v2 delete file | 模式可按操作粒度配置 |
| Hudi | ✅ COW 表 | ✅ MOR 表（avro 日志） | 建表时确定，MOR 最成熟 |
| Delta | ✅ 默认 | ⚠️ Deletion Vector（1.2+） | 主要靠 COW + OPTIMIZE |
| Paimon | ✅ | ✅ LSM 合并 | 流式写入友好 |

## 深度对比：索引与裁剪

| | Iceberg | Hudi | Delta | Paimon |
| --- | --- | --- | --- | --- |
| 分区 | 隐藏分区（transform） | 显式分区 | 显式分区 | 隐藏分区 |
| 文件统计 | min/max/null_count | 列统计 + 布隆 | min/max | min/max |
| 额外索引 | 可选 sort / Z-order | HFile、Bloom、Record index | Z-Order | 主键索引（LSM） |
| 点查能力 | 中（靠 bucket/排序） | 强（Record index） | 中 | 强（主键） |
| 增量读 | ✅ `start-snapshot-id` | ✅ 增量视图（最强） | ✅ CDF | ✅ |

## Paimon 简介

Apache Paimon（原 Flink Table Store）是 Flink 社区主导的湖仓表格式，2023 年进入 Apache。

- **流批一体**：Flink 原生，写入即流、查询即批
- **LSM 树结构**：主键表（Primary Key Table）支持高效 Upsert，不像 Iceberg 那样产生大量 delete file
- **实时更新**：适合 Flink CDC 直接入湖
- **小文件自动合并**：内建 compaction，无需外部调度

| | Iceberg | Paimon |
| --- | --- | --- |
| 主键 Upsert | 靠 delete file（MOR） | LSM 树（原生） |
| Flink 集成 | 好（1.5+） | 极好（原生） |
| 多引擎 | 最广 | 较窄（Trino/StarRocks 支持中） |
| 生态成熟度 | 最成熟 | 快速增长 |

两者可以共存：实时层 Paimon，共享层 Iceberg（Flink 双写或迁移）。

## 什么时候选 Iceberg

✅ 适合：

- 需要 **Spark / Flink / Trino / Hive / OLAP 多引擎共享同一份数据**
- 需要**隐藏分区 + 分区演进**（业务变化快，不想重写历史）
- 需要**完整 Schema 演进**（列增删改、嵌套结构）
- 需要 **Time Travel / 分支 / 标签**做审计或回测
- 数据在 **S3 / OSS / GCS**，想避免厂商锁定

❌ 不太适合：极端高频单行 Upsert（Hudi/Paimon 索引更强）、只用 Spark 且深度使用 Databricks、表非常小（< 10GB）。

## 什么时候选 Hudi

✅ 适合：

- **CDC 入湖**（MySQL → Kafka → Hudi），需要高效 Upsert
- 需要**增量拉取**（下游只消费变化数据）
- 需要**记录级索引**做点查
- 已在用 AWS EMR / Hudi 生态

❌ 不太适合：需要隐藏分区 / 分区演进、需要最广的多引擎支持、团队不想维护复杂 compaction。

## 什么时候选 Delta Lake

✅ 适合：

- **Databricks / Spark 深度绑定**
- 需要 Unity Catalog、Photon 等商业能力
- 已有大量 Delta 表和 Spark 作业

❌ 不太适合：多引擎（尤其 Flink/Trino/Hive）混合、需要隐藏分区、想避免 Databricks 生态锁定。

## 湖仓一体落地架构

```
┌──────────── 数据源 ────────────┐
│ MySQL (CDC)  日志(Kafka)  文件(S3) │
└───────────────┬────────────────┘
        ┌───────┴────────┐
        │ 接入：Flink CDC / Kafka / DataX │
        └───────┬────────┘
        ┌───────┴────────────────────────────┐
        │ 存储：Iceberg on S3/OSS             │
        │ ODS（原始）→ DWD（明细）→ DWS（汇总）│
        │ Catalog：Hive Metastore / REST      │
        └───────┬────────────────────────────┘
        ┌───────┴────────────────────────────┐
        │ 计算：Spark（批 ETL / 维护）         │
        │       Flink（实时写入）              │
        │       Trino（交互查询 / 联邦）        │
        │       StarRocks（极速 OLAP）         │
        └───────┬────────────────────────────┘
        ┌───────┴────────┐
        │ 应用：BI / 报表 / API / ML │
        └────────────────┘
```

| 阶段 | 动作 | 产出 |
| --- | --- | --- |
| 1. POC | 选一张 100GB 表，Spark + Iceberg 跑通读写、Time Travel | 验证功能 |
| 2. 选型 | 确认 Catalog、文件格式（Parquet）、分区策略 | 技术方案 |
| 3. 迁移 | `CALL system.migrate('db.tbl')` 原地迁移 Hive 表 | 存量切换 |
| 4. 接入 | Flink CDC 写 ODS；Spark 批处理 DWD/DWS | 链路打通 |
| 5. 治理 | compaction / expire / manifest 重写定时化 | 稳定运行 |
| 6. 多引擎 | Trino / StarRocks / Hive 4 接入 | 查询提速 |

## 常见面试题

**Q1：Iceberg 为什么能实现 ACID？**
A：所有元数据文件不可变，写入只产生新文件；提交时通过 Catalog 的 CAS 原子切换 `metadata_location` 指针。这一个动作是唯一生效点，读查询绑定某个 snapshot，因此满足原子性与隔离性。

**Q2：Iceberg 的元数据分几层？各自作用？**
A：五层：Catalog（指针）→ metadata.json（表定义 + 快照）→ Manifest List（manifest 清单 + 分区摘要）→ Manifest（data file 清单 + 列统计）→ Data File。逐层裁剪，避免打开所有文件。

**Q3：隐藏分区是什么？相比 Hive 分区有什么优势？**
A：分区由 `days(ts)` 等转换函数从业务列派生，不存储为真实列。优势：① 查询不用写分区列；② spec 可演进而不重写历史；③ 避免分区列与业务耦合。

**Q4：Iceberg 的 Schema 演进为什么安全？**
A：因为用**列 ID** 而不是列名定位列。列 ID 分配后永不复用，重命名/删列/加列都不影响历史文件读取。

**Q5：COW 和 MOR 的区别？**
A：COW 更新时重写整个文件，读快写慢；MOR 写 delete file + 新数据文件，写快读慢，需要 compaction。Iceberg 两种都支持。

**Q6：Iceberg 和 Hudi、Delta 怎么选？**
A：多引擎开放共享 → Iceberg；高频 CDC Upsert / 增量拉取 → Hudi；Databricks/Spark 深度绑定 → Delta；Flink 流批一体 → Paimon。

**Q7：Flink 写 Iceberg 怎么保证 exactly-once？**
A：基于 checkpoint 的两阶段提交：checkpoint 期间写 pending 文件，`notifyCheckpointComplete` 后才真正 commit；失败重启时未提交文件被清理。

**Q8：小文件怎么治理？**
A：写入端控制 `write.target-file-size-bytes`（128MB）和 `write.distribution-mode=hash`；定期跑 `rewrite_data_files`（binpack）；配合 `expire_snapshots` 清理。

**Q9：Iceberg 的查询为什么快？**
A：三层裁剪：分区裁剪（Manifest List 分区摘要）→ 文件裁剪（Manifest 里的 min/max/null_count）→ 行组裁剪（Parquet Row Group 统计），再加列裁剪。

**Q10：Iceberg 表能被 Hive 读吗？**
A：Hive 4 支持只读（需 `iceberg-hive-runtime` + `iceberg.engine.hive.enabled=true`）；Hive 3 及以下不支持，需通过 Spark/Trino 读取。

## 关键配置速查

```properties
format-version=2
write.format.default=parquet
write.parquet.compression-codec=zstd
write.target-file-size-bytes=134217728
write.delete.mode=merge-on-read
write.update.mode=merge-on-read
write.merge.mode=merge-on-read
history.expire.max-snapshot-age-ms=604800000
```

## 自测

1. 用一张表对比 Iceberg / Hudi / Delta / Paimon 的写入模型与最强场景。
2. 什么情况下你会选 Hudi 而不是 Iceberg？举两个具体场景。
3. Paimon 的 LSM 主键表和 Iceberg 的 MOR 有什么本质差异？
4. 描述一个湖仓一体的落地架构，说明每层用什么组件。
5. 面试题 Q1–Q10 任选 3 个，用自己的话复述一遍。

## 参考与官方链接

- [Iceberg 官方文档](https://iceberg.apache.org/docs/latest/)
- [Apache Hudi 官方文档](https://hudi.apache.org/docs/overview/)
- [Delta Lake 官方文档](https://docs.delta.io/latest/index.html)
- [Apache Paimon 官方文档](https://paimon.apache.org/docs/master/)
- [Iceberg 表格式规范](https://iceberg.apache.org/spec/)
- [Trino Iceberg Connector](https://trino.io/docs/current/connector/iceberg.html)
- [Iceberg GitHub](https://github.com/apache/iceberg)
