# 04 ACID 与快照隔离

## 一句话

Iceberg 的 ACID 不靠锁、不靠数据库，而靠「**所有元数据不可变 + 只在最后一步原子切换 Catalog 指针**」：写入过程中产生的文件对读者完全不可见，只有指针切换成功的那一刻新快照才生效；并发写用**乐观并发控制（OCC）**，冲突就重试或失败。

## 为什么「不可变 + 原子指针」就够了

回忆第 02 章的提交流程：

```
1. 写新 Data File         → data/xxx.parquet        （不可见）
2. 写新 Manifest          → metadata/xxx-m0.avro    （不可见）
3. 写新 Manifest List     → metadata/snap-xxx.avro  （不可见）
4. 写新 metadata.json     → metadata/00003-xxx.json （不可见）
5. Catalog CAS 换指针     → 00002 换成 00003        （★ 原子提交）
```

前 4 步都是**新文件名**，从不覆盖旧文件。因此：

- 读 `00002.metadata.json` 的查询**完全不受影响**（快照隔离）
- 第 5 步失败 = 提交失败，垃圾文件后续清理，表状态不变
- 第 5 步成功 = 新快照立即可见，且是完整一致的状态

| 特性 | 实现方式 |
| --- | --- |
| **A** 原子性 | 只有第 5 步是指针切换，二值状态 |
| **C** 一致性 | 新 metadata 引用完整的一组 manifest，不会半新半旧 |
| **I** 隔离性 | 读写各自看到某个完整 snapshot |
| **D** 持久性 | 指针切换成功即持久 |

## 原子切换的具体实现

不同 Catalog 的 CAS 实现不同：

| Catalog | 原子性机制 |
| --- | --- |
| **Hive Metastore** | `ALTER TABLE ... SET TBLPROPERTIES('metadata_location'=...)`，靠 HMS 事务 + 版本校验 |
| **REST Catalog** | HTTP `POST /tables/{table}` 带 `If-Match: <etag>`，服务端做 CAS |
| **JDBC** | `UPDATE ... WHERE version = ?`，影响行数为 1 才算成功 |
| **AWS Glue** | `UpdateTable` + 版本校验 |
| **Hadoop（文件系统）** | 靠 `rename` 原子性（HDFS）；S3 上**不可靠** |

S3 的特殊性：**没有原子 rename，也没有原生 CAS**。所以：

- 用 `S3FileIO`（Iceberg 自带），它用 DynamoDB 表做提交协调
- 或用 REST / Glue Catalog，把原子性交给外部服务
- 生产不要用 `HadoopCatalog` + S3，会丢数据

## 快照隔离（Snapshot Isolation）

```
时间 →

Writer:   [写文件...] [写 manifest...] [写 metadata...] [CAS 切换]
                                                          ↓
Reader A:  ──────── 读到 snapshot N（旧）─────────────────┤
Reader B:                                              ├──── 读到 snapshot N+1（新）
Reader C:  ──────────────────── 读到 N ─────────────────┘
```

每个读者在**开始查询时**确定 `current-snapshot-id`，整个查询都读这个快照的 manifest 列表。中途有写入提交也不影响本次查询：读不阻塞写，写不阻塞读。

Iceberg 提供的是 **Snapshot Isolation**，不是 Serializable：

- ✅ 不出现脏读（只读已提交快照）
- ✅ 不出现不可重复读（查询内快照固定）
- ⚠️ 可能出现**写偏斜（write skew）**：两个事务各读旧快照、写不同文件、都提交成功，业务约束可能被破坏
- ⚠️ 不支持跨表事务（除 Nessie 等多表 Catalog）

## 并发写：乐观并发控制

Iceberg 不做悲观锁，而是「先写、提交时检测冲突、冲突则重试」。

### 正常情况：两个写者写不同分区

```
Writer 1: base=snapshot N → 写 dt=11-01 → 尝试 CAS N→N+1  ✅
Writer 2: base=snapshot N → 写 dt=11-02 → 尝试 CAS N→N+2  ❌（已是 N+1）
                                             ↓
                                     重新读取 snapshot N+1
                                     重新计算（N+1 + 自己的文件）
                                     尝试 CAS N+1→N+3  ✅
```

注意：**Writer 2 的 Data File 已经写好，不需要重写**，只是重新生成 manifest / metadata 再提交一次。这叫 **retry with rebase**。

### 冲突检测规则

| 操作 | 冲突条件 |
| --- | --- |
| `append`（只加文件） | 几乎不冲突，并发 append 都能合并 |
| `overwrite`（按分区覆盖） | 两个写者覆盖同一分区 → 冲突 |
| `delete` / `update`（行级） | 删/改的文件已被别人改过 → 冲突 |
| `rewrite`（compaction） | 要重写的文件已被删除 → 跳过 |
| Schema / 分区 spec 变更 | 两个写者同时改 → 后者冲突 |

### 冲突后怎么办

```java
int attempts = 0;
while (true) {
  try {
    Table t = catalog.loadTable(identifier);   // 重新拿最新快照
    // 用最新快照重新计算并提交
    break;
  } catch (CommitFailedException e) {
    if (++attempts > 3) throw e;
    Thread.sleep(100L * attempts);
  }
}
```

Spark / Flink 的写入器内置重试。但注意：

- **重试会重新读元数据**，高并发下开销不可忽略
- **长事务**更容易冲突（持旧快照越久，别人提交越多）
- 高频小批量写入建议**降低并发度**或按分区打散

## 并发写冲突的典型场景

- **两个 Flink 任务写同一张表**：都只 append 则不冲突；但没做分区隔离时容易产生小文件。
- **Compaction 与写入并发**：compaction 发现要重写的文件已被删除会跳过；不会删正在被读的快照文件。建议用 `where` 限定分区。
- **两个 UPDATE 改同一行**：先提交者赢，后者冲突失败，**不会出现两个都成功、结果不确定**。

## 小文件合并（Compaction）

ACID 的代价是「每次写入都产生新文件」，写多了就有小文件：

```
写入 100 次微批 → 100 个 1MB 文件 → 查询要 open 100 个文件
```

Iceberg 用 **rewrite_data_files** 解决：

```sql
CALL local.system.rewrite_data_files(
  table => 'db.orders',
  strategy => 'binpack',
  options => map(
    'target-file-size-bytes', '134217728',
    'min-input-files', '5',
    'max-concurrent-file-group-rewrites', '5'
  )
);

-- 只合并某个分区
CALL local.system.rewrite_data_files(
  table => 'db.orders',
  where => "ts_day = '2026-11-01'"
);
```

| 策略 | 做什么 | 适用 |
| --- | --- | --- |
| `binpack` | 小文件按大小装箱合并 | 通用小文件治理 |
| `sort` | 合并 + 按指定列排序 | 提升范围查询效果 |
| `zorder` | 合并 + 多维 Z-Order 聚簇 | 多列组合查询 |

Compaction 本质是一次 `overwrite` 提交：读旧文件 → 写新文件 → 新 manifest 替换旧 manifest。**旧快照仍可读**，直到 `expire_snapshots` 清理。

## 事务的边界与限制

| 能力 | Iceberg | 说明 |
| --- | --- | --- |
| 单表 ACID | ✅ | 快照隔离 |
| 行级 UPDATE/DELETE | ✅ | v2 delete file |
| MERGE INTO | ✅ | Spark/Flink 支持 |
| 多表事务 | ❌（Nessie ✅） | 需要 Catalog 支持 |
| 跨表原子提交 | ❌ | 各表独立快照 |
| 唯一约束 / 外键 | ❌ | 表格式不提供约束 |

## 关键配置

```properties
# ============ 提交重试 ============
commit.retry.num-retries=4                    # 提交冲突重试次数
commit.retry.total-timeout-ms=1800000         # 总超时 30 分钟

# ============ 并发 ============
write.spark.fanout.enabled=false              # Spark 写入是否 fanout

write.target-file-size-bytes=134217728
```

## 常见问题

**Q：Iceberg 会加锁吗？**
A：不加业务锁，只在「切换指针」时做 CAS（短暂的元数据层原子操作）。写写并发不互相阻塞，只冲突重试。

**Q：两个任务同时写同一张表会不会丢数据？**
A：不会。要么都能提交（append 合并），要么后者收到 `CommitFailedException` 并重试/失败。绝不会静默丢数据（最多留下垃圾文件）。

**Q：为什么我的任务报 `CommitFailedException`？**
A：并发冲突。处理：① 降低并发写同一张表；② 按分区打散；③ 增大重试次数；④ 检查长事务；⑤ compaction 与写入错峰。

**Q：快照隔离下读到的是「查询开始时刻」还是「最新」？**
A：取决于引擎。Spark 默认在查询计划生成时确定快照；长查询读开始时那一版。

**Q：Iceberg 支持跨表事务吗？**
A：原生不支持，需要 Nessie 这类支持多表原子提交的 Catalog，或业务层用「两阶段提交 + 幂等」保证。

## 自测

1. 为什么「不可变文件 + 原子指针切换」能满足 ACID？逐条对应说明。
2. S3 上为什么不能用 HadoopCatalog？正确做法是什么？
3. 两个 Writer 同时 append 同一张表会发生什么？同时 overwrite 同一分区呢？
4. 快照隔离和可串行化的区别？什么场景会出现写偏斜？
5. `rewrite_data_files` 解决什么问题？它和普通写入在提交层面有什么相似之处？

## 参考与官方链接

- [Iceberg 表格式规范（Snapshots / Commit）](https://iceberg.apache.org/spec/#snapshots)
- [Iceberg 可靠性](https://iceberg.apache.org/docs/latest/reliability/)
- [Iceberg 表维护](https://iceberg.apache.org/docs/latest/maintenance/)
- [S3FileIO 与 DynamoDB 锁](https://iceberg.apache.org/docs/latest/aws/)
- [Nessie 多表事务](https://projectnessie.org/features/)
- [Iceberg GitHub](https://github.com/apache/iceberg)
