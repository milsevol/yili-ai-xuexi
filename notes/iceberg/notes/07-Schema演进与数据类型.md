# 07 Schema 演进与数据类型

## 一句话

Iceberg 的 Schema 演进之所以安全，是因为**每一列都有一个永不变的列 ID（column-id）**，数据文件里记录的是 ID 而不是列名；于是「加列、删列、改列名、调整类型、嵌套结构变更」都只改元数据，历史数据不用重写，也不会读错列。

## 为什么列名不可靠

Hive 表的列按「位置 + 名字」对应，Parquet 文件里存列名，读取时按名字或位置匹配：

| 操作 | Hive 表后果 |
| --- | --- |
| 改列名 | 旧文件仍是旧名，读出来是 null 或报错 |
| 删列 | 旧文件该列还在，元数据没了 → 数据错位风险 |
| 中间插入一列 | 按位置读取会全部错位（严重事故） |
| 改类型 | 旧文件类型不匹配，可能转换失败 |

Iceberg 的解法：

```
表 Schema:
  field id=1 name=order_id type=long
  field id=2 name=user_id  type=long
  field id=3 name=amount   type=decimal(12,2)

Data File 内：列 1 / 列 2 / 列 3

改名 amount → total_amount：
  表 Schema: field id=3 name=total_amount
  Data File 里仍是「列 3」→ 自动映射 ✅
```

**列 ID 是稳定标识，列名只是给人看的标签。**

## 支持的演进操作

### 加列（ADD COLUMN）

```sql
ALTER TABLE db.orders ADD COLUMN coupon_amount DECIMAL(12,2) AFTER amount;
ALTER TABLE db.orders ADD COLUMNS (channel STRING COMMENT '渠道', device STRING);
```

- 历史数据该列为 `null`，新数据正常填充，不重写文件

### 删列（DROP COLUMN）

```sql
ALTER TABLE db.orders DROP COLUMN coupon_amount;
```

- 只从 Schema 移除，数据文件里还在（空间等 compaction 回收）
- **列 ID 不会被复用**（避免旧数据被误读）

### 重命名列（RENAME COLUMN）

```sql
ALTER TABLE db.orders RENAME COLUMN amount TO total_amount;
```

- 只改名字，列 ID 不变，历史数据自动对应新名

### 改类型（ALTER COLUMN TYPE）

```sql
ALTER TABLE db.orders ALTER COLUMN amount TYPE DECIMAL(18,2);
ALTER TABLE db.orders ALTER COLUMN user_id TYPE BIGINT;   -- int → bigint
```

Iceberg 允许的「安全类型提升」：

| 从 | 到 |
| --- | --- |
| `int` | `long` |
| `float` | `double` |
| `decimal(p,s)` | `decimal(p+n,s)`（精度提升） |
| `date` | `timestamp`（部分引擎限制） |

**不允许**缩窄（`long → int`），因为旧数据可能溢出。

### 调整列顺序 / 注释

```sql
ALTER TABLE db.orders ALTER COLUMN amount AFTER user_id;
ALTER TABLE db.orders ALTER COLUMN amount COMMENT '订单金额（含税）';
```

列顺序只影响 `SELECT *` 的显示顺序，不影响存储。

## 嵌套结构演进

Iceberg 支持完整的嵌套类型：`struct`、`list`、`map`，演进规则同样基于 ID。

```sql
-- 原 Schema：address struct<city: string, street: string>
ALTER TABLE db.orders ADD COLUMN address.zip STRING;
-- 历史数据 address.zip 为 null；city/street 不受影响

-- list / map 元素类型不兼容时，推荐新增列而不是改原列
ALTER TABLE db.orders ADD COLUMN tag_details ARRAY<STRUCT<name:STRING, score:INT>>;
```

嵌套演进的核心规则：**同层 ID 唯一、父字段 ID 不变、子字段单独分配 ID**。因此「在 struct 中间插字段」是安全的。

## 分区字段变更 vs Schema 变更

| | Schema 变更 | 分区 spec 变更 |
| --- | --- | --- |
| 改什么 | 表的列定义 | 数据在文件系统上的组织方式 |
| 语法 | `ALTER COLUMN` | `ADD/DROP/REPLACE PARTITION FIELD` |
| 是否重写数据 | ❌ | ❌（历史 spec 保留） |
| 影响查询 | 列映射自动适配 | 每个 manifest 按自己的 spec 裁剪 |
| 是否互斥 | 独立 | 独立（分区源列被删时需先处理 spec） |

组合场景：

```sql
ALTER TABLE db.orders ADD COLUMN province STRING;                      -- Schema 演进
ALTER TABLE db.orders ADD PARTITION FIELD truncate(4, province);       -- 分区演进
-- 历史数据不重写，新数据按 province 分区
```

## 为什么 Iceberg 能安全演进

三条设计保证：

1. **列 ID 稳定**：分配后永不复用，删列也不会把 ID 给别人
2. **Schema 有版本**：`metadata.json` 里 `schemas` 是列表，`current-schema-id` 指向当前；旧快照读旧 schema
3. **文件自描述**：Manifest 记录每个文件的 schema id 与字段 ID 映射，读取时按文件自己的 schema 解释

读取过程：

```
查询 → 当前 schema（列 ID → 名字/类型）
     → Manifest 里每个文件的 schema_id
     → 按列 ID 对齐 → 缺的列补 null → 多出的列忽略
```

这就是「加列读旧文件返回 null、删列不报错、改名不影响」的根本原因。

## 实际演进示例

```sql
CREATE TABLE db.orders (
  order_id BIGINT, user_id BIGINT, amount DECIMAL(12,2), ts TIMESTAMP
) USING iceberg PARTITIONED BY (days(ts));

ALTER TABLE db.orders ADD COLUMN channel STRING;                 -- 加列
ALTER TABLE db.orders ALTER COLUMN amount TYPE DECIMAL(18,2);    -- 精度提升
ALTER TABLE db.orders RENAME COLUMN channel TO source_channel;   -- 重命名
ALTER TABLE db.orders ADD COLUMN ext STRUCT<aa:STRING, bb:INT>;  -- 嵌套
ALTER TABLE db.orders ADD COLUMN ext.cc DOUBLE;                  -- 嵌套加字段

DESCRIBE TABLE db.orders;
SELECT * FROM db.orders.schema;   -- 元数据表
```

每一步都只写一个新的 `metadata.json`，**零数据重写**。

## 与 Hive / Delta / Hudi 的对比

| 操作 | Iceberg | Hive | Delta Lake | Hudi |
| --- | --- | --- | --- | --- |
| 加列 | ✅ | ✅（末尾） | ✅ | ✅ |
| 删列 | ✅ | ❌（只能重建） | ✅（需 rewrite） | ✅ |
| 重命名 | ✅ | ⚠️（旧文件可能读不到） | ✅（需 column mapping） | ✅ |
| 改类型 | ✅ 安全提升 | ⚠️ 有限 | ✅ | ✅ |
| 嵌套演进 | ✅ | ❌ | ✅ | ✅ |
| 基于列 ID | ✅ | ❌（名字/位置） | ✅（column mapping 后） | ✅ |

## 关键配置

```properties
# ============ Schema 演进 ============
# 默认无需额外配置，DDL 直接生效

# 控制元数据保留（保证旧快照能读旧 schema）
write.metadata.previous-versions-max=100
write.metadata.delete-after-commit.enabled=true

# ============ 兼容性 ============
# Iceberg 本身不允许缩窄类型，无需配置
```

## 常见问题

**Q：删列后数据文件里的数据真的删了吗？**
A：没有。列数据仍在 Parquet 文件里，只是 Schema 不再引用。空间要等 `rewrite_data_files` 重写文件时才释放。

**Q：加列后旧数据查询会报错吗？**
A：不会，返回 `null`。新写入的数据正常填充。

**Q：重命名列会影响正在运行的查询吗？**
A：已开始的查询用旧 schema（快照隔离），不受影响；新查询用新 schema。

**Q：为什么不能把 `long` 改成 `int`？**
A：历史数据可能有超出 int 范围的值，缩窄会溢出。需要缩窄只能新建列 + 转换写入。

**Q：改列类型后，旧 Parquet 文件能直接读吗？**
A：能。Iceberg 读取时做类型提升（如 int → long），Parquet 本身也支持部分兼容读取。

**Q：分区字段被删了怎么办？**
A：先用 `DROP PARTITION FIELD` 把 spec 里的字段替换成 `void`，再 `DROP COLUMN`。否则会报「分区源列不存在」。

## 自测

1. 为什么 Iceberg 可以用列 ID 而不是列名？数据文件里存的是 ID 吗？
2. 加列、删列、重命名、改类型，哪些会触发数据重写？为什么？
3. Iceberg 允许哪些安全的类型提升？举 3 个例子。
4. Schema 变更和分区 spec 变更的本质区别是什么？
5. 删列后空间什么时候真正释放？怎么做？

## 参考与官方链接

- [Iceberg Schema 演进](https://iceberg.apache.org/docs/latest/evolution/#schema-evolution)
- [Iceberg 表格式规范（Schemas / Column IDs）](https://iceberg.apache.org/spec/#schemas)
- [Iceberg 数据类型](https://iceberg.apache.org/spec/#primitive-types)
- [Spark SQL ALTER TABLE 语法](https://spark.apache.org/docs/latest/sql-ref-syntax-ddl-alter-table.html)
- [Delta Lake Schema 演进](https://docs.delta.io/latest/delta-batch.html#update-table-schema)
