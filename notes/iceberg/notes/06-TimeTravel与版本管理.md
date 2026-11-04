# 06 Time Travel 与版本管理

## 一句话

Iceberg 的每一次提交都产生一个**不可变快照（Snapshot）**，并记录在 `metadata.json` 的 `snapshots` 与 `snapshot-log` 里；于是「查历史版本」「回滚到某一版」「在快照上开分支做实验」都只是**选择读哪个 snapshot**，不需要任何数据复制。

## Snapshot 是什么

```json
{
  "snapshot-id": 3051729675574597004,
  "parent-snapshot-id": 3051729675574597003,
  "sequence-number": 12,
  "timestamp-ms": 1730000000000,
  "manifest-list": "s3://wh/db/orders/metadata/snap-30517-1-xxx.avro",
  "summary": { "operation": "append", "added-data-files": "2", "total-records": "1200000" }
}
```

| 字段 | 作用 |
| --- | --- |
| `snapshot-id` | 全局唯一，Time Travel 的句柄 |
| `parent-snapshot-id` | 形成版本链（可用于增量读） |
| `sequence-number` | 单调递增，v2 用于 delete file 的先后关系 |
| `timestamp-ms` | 提交时间，`TIMESTAMP AS OF` 靠它定位 |
| `manifest-list` | 这个快照的文件清单入口 |
| `summary` | 操作类型与文件/记录数统计 |

**Snapshot 不可变**：一旦提交，它的 manifest list 永远不会改。回滚不是「删除新快照」，而是「把当前指针指回旧快照」。

## Time Travel 查询语法

### Spark SQL

```sql
-- 按 snapshot id 查
SELECT * FROM db.orders VERSION AS OF 3051729675574597004;

-- 按时间戳查（取该时刻「之前最近」的快照）
SELECT * FROM db.orders TIMESTAMP AS OF '2026-11-01 10:00:00';

-- 查快照元数据与历史
SELECT snapshot_id, parent_id, committed_at, operation FROM db.orders.snapshots;
SELECT * FROM db.orders.history;
```

### Flink SQL

```sql
SELECT * FROM orders /*+ OPTIONS('snapshot-id' = '3051729675574597004') */;
SELECT * FROM orders /*+ OPTIONS('as-of-timestamp' = '1730000000000') */;
```

Java API 对应 `table.newScan().useSnapshot(id)` / `.asOfTime(ts)`，再 `planFiles()`。

## 回滚与快照操作

### rollback_to_snapshot：把表指针指回旧版本

```sql
CALL local.system.rollback_to_snapshot('db.orders', 3051729675574597004);
CALL local.system.rollback_to_timestamp('db.orders', TIMESTAMP '2026-11-01 00:00:00');
```

语义：**不是删除新数据**，而是让 `current-snapshot-id` 指向旧快照。新快照仍在 `snapshots` 列表里，直到过期。

### cherrypick / set_current

```sql
-- 把某个快照的变更摘到当前分支（回滚后只恢复某一次写入）
CALL local.system.cherrypick_snapshot('db.orders', 3051729675574597004);

-- 直接切换指针，不生成 rollback 审计快照
CALL local.system.set_current_snapshot('db.orders', 3051729675574597004);
```

区别：`rollback` 会生成一个 `operation=rollback` 的新快照（有审计记录），`set_current` 直接改指针。

## branch 与 tag

| 类型 | 可变 | 用途 |
| --- | --- | --- |
| **Branch（分支）** | ✅ 可继续写入 | 隔离实验环境、灰度发布 |
| **Tag（标签）** | ❌ 只读 | 标记里程碑（v1.0、月末快照） |

它们都是「指向某个 snapshot 的命名引用」，存在 `metadata.json` 的 `refs` 里：

```json
"refs": {
  "main": { "snapshot-id": 3051729675574597005, "type": "branch" },
  "audit-2026-11": { "snapshot-id": 3051729675574597000, "type": "tag" }
}
```

```sql
ALTER TABLE db.orders CREATE BRANCH experiment;              -- 从 main 派生
INSERT INTO db.orders.branch_experiment VALUES (...);        -- 分支写入，不影响 main
SELECT * FROM db.orders.branch_experiment;                   -- 查分支
ALTER TABLE db.orders CREATE TAG audit_2026_11 RETAIN 365 DAYS;
SELECT * FROM db.orders VERSION AS OF 'audit_2026_11';       -- 查标签
ALTER TABLE db.orders FAST FORWARD main TO experiment;       -- 合并分支
ALTER TABLE db.orders DROP BRANCH experiment;                -- 删除分支
```

```
main         ──●────●────●────●────────►  生产数据
                \         /
experiment       ●────●───           实验（不污染 main）
audit tag       ▲（固定指向某快照）
```

典型用法：数据回测 / 模型训练（branch 上重算，验证后 fast-forward）、多环境隔离（需 Nessie）、审计留档（每月打 tag）。

## 快照过期与元数据清理

### expire_snapshots

```sql
-- 清理 7 天前的快照（保留最近 10 个）
CALL local.system.expire_snapshots(
  table => 'db.orders',
  older_than => TIMESTAMP '2026-10-28 00:00:00',
  retain_last => 10
);
```

**注意**：

- 被 branch/tag 引用的快照**不会被清理**（除非显式过期）
- 清理快照 ≠ 删除数据文件；数据文件要等 `remove_orphan_files`
- 清理后 Time Travel 就回不去了，**生产环境要留足窗口**

### remove_orphan_files

清理「不在任何快照里」的孤儿文件（写入失败留下的垃圾）：

```sql
CALL local.system.remove_orphan_files(
  table => 'db.orders',
  older_than => TIMESTAMP '2026-10-25 00:00:00'
);
```

### 完整维护顺序

```
rewrite_data_files → rewrite_manifests → expire_snapshots → remove_orphan_files
```

顺序很重要：先合并、再过期，避免过期把还需引用的文件删掉。

## 时间旅行的一致性保证

| 问题 | 答案 |
| --- | --- |
| 回滚后，新写入的数据会丢吗？ | 不会立刻删。新快照还在 `snapshots` 里，直到 expire |
| 两个查询读不同版本会互相影响吗？ | 不会。每个查询绑定自己的 snapshot |
| 回滚能撤销 schema 变更吗？ | 能，回到当时 metadata.json 里的 schema |
| Time Travel 会读旧文件吗？ | 会，所以旧文件必须保留到快照过期之后 |
| 快照过期后报什么错？ | `Cannot find snapshot with ID ...` 或 `Snapshot expired` |

## 关键配置

```properties
# ============ 快照保留 ============
history.expire.max-snapshot-age-ms=604800000       # 快照最长保留 7 天
history.expire.min-snapshots-to-keep=1             # 至少保留 1 个
history.expire.max-ref-age-ms=9223372036854775807  # tag 默认永不过期

# ============ 元数据保留 ============
write.metadata.delete-after-commit.enabled=true
write.metadata.previous-versions-max=100
```

## 常见问题

**Q：Time Travel 会不会很慢？**
A：不会。它读旧的 manifest list，索引结构与当前一致，裁剪逻辑一致。唯一区别是数据文件更旧。

**Q：回滚之后还能再回到「回滚前」的版本吗？**
A：能，只要那个快照还没过期。回滚只是改指针。

**Q：branch 和 tag 存在哪里？**
A：存在 `metadata.json` 的 `refs` 字段。每次创建/删除 ref 都会生成新的 metadata.json。

**Q：`VERSION AS OF` 后面的数字是 snapshot id 还是版本号？**
A：Spark SQL 里 `VERSION AS OF <long>` 是 **snapshot-id**，不是递增版本号。

**Q：为什么我的 `expire_snapshots` 没删掉旧数据？**
A：① 旧快照被 tag/branch 引用；② `min-snapshots-to-keep` 保留；③ 只清理了快照元数据，数据文件要靠 `remove_orphan_files`。

**Q：能对 tag 写入吗？**
A：不能。tag 只读；branch 可写。

## 自测

1. Snapshot 为什么必须不可变？如果允许修改会破坏什么？
2. `VERSION AS OF` 和 `TIMESTAMP AS OF` 的区别？时间戳如何定位快照？
3. rollback、cherrypick、set_current_snapshot 三者的区别？
4. branch 和 tag 的核心区别？各举一个使用场景。
5. 快照过期会删除哪些东西？为什么 `expire_snapshots` 后还要 `remove_orphan_files`？

## 参考与官方链接

- [Iceberg Time Travel](https://iceberg.apache.org/docs/latest/spark-queries/#time-travel)
- [Iceberg 分支与标签](https://iceberg.apache.org/docs/latest/branching/)
- [Iceberg 表维护](https://iceberg.apache.org/docs/latest/maintenance/)
- [Iceberg 表格式规范（Snapshots / Refs）](https://iceberg.apache.org/spec/#snapshots)
- [Iceberg Spark 过程](https://iceberg.apache.org/docs/latest/spark-procedures/)
