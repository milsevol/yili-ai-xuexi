# 03 数据模型与RowKey设计

## 一句话

HBase 的数据模型是「**有序 RowKey + 若干固定 ColumnFamily + 任意 Qualifier + 多版本 Cell**」的列式稀疏存储——RowKey 是一切的入口，**怎么设计 RowKey 直接决定热点分布、读写路径和 Compaction 成本**。

## 数据模型详解

### 核心实体

| 实体 | 说明 | 是否可变更 |
| --- | --- | --- |
| **Table** | 逻辑表；物理上一个 HDFS 目录 | 可增删 CF，但不能改 RowKey 设计 |
| **Column Family (CF)** | 创建表时定义；同一 CF 的数据一起存、一起压缩、一起 Flush/Compact | **不可新增/删除已有 CF**（2.5 起支持删除 CF，但小心使用） |
| **Qualifier** | CF 里的列名，一行可以有不同的 Qualifier | **随时可以加**，不同行可以有不同列 |
| **RowKey** | 行的唯一主键；**按字典序排序** | 不可变 |
| **Cell** | `RowKey + CF:Qualifier + timestamp` 定位的一个值 | 多版本，默认保留 1 个 |
| **Region** | Table 的一段连续 RowKey 范围；最小存储与负载均衡单位 | Split/Merge 产生新 Region |

### 存储格式示意

```
Table: user_profile
  ColumnFamily: info    →  存在 HDFS 的 /hbase/data/default/user_profile/xxx/info/ 目录下
  ColumnFamily: addr    →  存在 /hbase/data/default/user_profile/xxx/addr/ 目录下

同一 Region 内，info CF 的所有 HFile 长这样（按 RowKey 排序）：

RowKey           CF:Qualifier     timestamp        value
user001          info:name        1700000000       "Alice"
user001          info:age         1700000000       28
user002          info:name        1700000000       "Bob"
user002          info:age         1699999999       30   ← 旧版本，读时取最新
user002          info:age         1700000000       31   ← 新版本

addr CF 的 HFile 存的是同一批 RowKey 的 addr:* 列，和 info 是分开的
```

### 时间戳与版本

每个 Cell 可以保留多个时间戳版本：

| 配置 | 默认 | 说明 |
| --- | --- | --- |
| `VERSIONS`（建表时指定） | 1 | 最多保留的版本数，上限 100 |
| `MIN_VERSIONS` | 0 | Compaction 时最少保留的版本数 |
| `TTL` | FOREVER | 版本保留的最大时间 |
| `COMPRESSION` | NONE | HFile 压缩格式：SNAPPY / GZ / LZ4 / ZSTD |
| `BLOOMFILTER` | ROW | BloomFilter 粒度：ROW / ROWCOL / NONE |

- Get 默认取最新版本；要取历史版本可以指定 `setMaxVersions()` 或 `setTimeRange()`。
- Delete 操作不是立即删除，而是写一个**墓碑标记（Tombstone）**，等 Compaction 时物理清除。

## RowKey 设计：最重要的事

RowKey 是字节数组，**按字典序排序**。一切问题都来自这个「有序」：

- 连续 RowKey 会落到同一个 Region → 写入同一 RS → **热点**
- 设计好 RowKey 可以让范围扫描变得高效
- 设计坏 RowKey 会让一个 RS 打满、其他 RS 闲得慌

### 什么是热点

```
RegionServer 1 (100% 写)   RegionServer 2 (20% 写)   RegionServer 3 (10% 写)
  Region: [1, 1000]         Region: [1001, 2000]       Region: [2001, 3000]

写 RowKey = 自增 ID：user1, user2, user3 ...
  user1001, user1002 ... → 全在 RS1（刚 Split 出来的新 Region）
  RS1 写打满，RS2/3 没事做
```

> **热点的根源**：连续自增的 RowKey 让所有新写入都落到一个 Region（刚 Split 出来的尾 Region）。这是新手最容易踩的坑。

### 设计策略总览

| 策略 | 适用场景 | 做法 | 风险 |
| --- | --- | --- | --- |
| **加盐（Salting）** | 写入热点 | 在 RowKey 前面加固定长度的随机/取模前缀 | 扫描要多并发前缀，范围扫描变难 |
| **哈希（Hashing）** | 点查、精确查询 | 对业务主键做哈希，前缀放哈希值 | 彻底失去有序性，范围扫描不可用 |
| **反转（Reversing）** | 有固定后缀格式（如手机号） | 把后缀反转到前面 | 只有适合反转格式的主键能用 |
| **业务前缀** | 按业务维度分区 | 用租户 ID / 国家码 / 业务域 做前缀 | 热点集中在最大租户的前缀上 |
| **时间戳后缀** | 时序数据、流水 | `device_id + timestamp` 保证按设备聚合、时间有序 | 不能只有时间戳（时间戳递增导致尾 Region 热点） |

### 加盐详解

```python
# 业务主键：uid（自增整数）
# 加盐前缀：hash(uid) % 16 → 固定 1 字节
import hashlib, struct

def rowkey_salt(uid: int) -> bytes:
    salt = hash(str(uid)) % 16
    return struct.pack('>B', salt) + struct.pack('>Q', uid)

# 写 uid=100 → RowKey = 0x05 + b'\x00\x00...\x64'
# 写 uid=101 → RowKey = 0x09 + b'\x00\x00...\x65'
# 不同的 uid 被均匀打散到 16 个前缀 → 落到 16 个不同 Region
```

- **点查**：知道 uid，算加盐 → 精确 RowKey → 直接 Get。
- **范围扫描**：如果只扫 uid 范围，得对每个可能的盐前缀做并发 Scan，然后归并结果。有点麻烦但可行。
- **盐位数**：根据 Region 数量决定。集群 64 台 RS、每台平均 4 个 Region → 总 Region 约 256 → 盐位数至少 `log2(256) = 8` 位（0-255）。

### 哈希详解

```python
import hashlib

def rowkey_hash(email: str) -> bytes:
    # MD5 16 字节，SHA256 32 字节
    digest = hashlib.md5(email.encode()).digest()
    return digest + email.encode()
```

- **点查**：算 MD5 前缀 → 精确定位。
- **范围扫描**：**不可用**。没有有序性。
- 适合：用户画像表、按 email/手机号 点查的场景。

### 反转详解

```python
def rowkey_reverse(phone: str) -> bytes:
    # 手机号 13800138000 → 反转 000838000831
    return phone[::-1].encode()
```

- 适合：有固定后缀格式的主键（手机号、订单号如果是「日期+序号」格式）。
- 反转后，相同前缀的号码（比如都是 13800138***）会被打散，但仍保留**后缀维度的有序性**。
- 问题：只有非常特定的格式能用。

### 时序数据 RowKey 设计（经典案例）

需求：监控系统，每 10 秒采集一个设备指标，按设备聚合、按时间范围查询。

```
# 错误设计：只有时间戳
RowKey = 1700000000001, 1700000000002, 1700000000003 ...
→ 全写到尾 Region → 热点爆炸

# 正确设计：设备ID + 反向时间戳
RowKey = device_001 + (now_ms - timestamp)
# 反向时间戳：新数据的 RowKey 更小 → 每个设备的数据按「新 → 旧」有序
# 查询某设备最近 1 小时数据：Scan(device_001+, device_001+反向时间戳(now-1h))
→ 同一设备的数据在同一个 Region → 点查/范围扫描快
→ 不同设备均匀分布 → 写入不热点
```

## RowKey 长度控制

RowKey 是**每个 Cell 都存一遍**的。RowKey 越长，存储开销越大：

- HFile 的 KV 编码里，key 包含完整的 RowKey。如果 RowKey 平均 100 字节、每行 50 个 Cell，每行额外开销 5KB。
- 建议 RowKey **尽量控制在 20–50 字节**以内。
- CF 名称也别太长（每个 HFile entry 都带 CF 名），用简短名如 `info`、`addr`、`d`。

| 做法 | 推荐 | 避免 |
| --- | --- | --- |
| RowKey 编码 | 二进制（struct.pack / 定长字节） | 长字符串、UUID 文本 |
| CF 名短 | `info` / `addr` | `user_information_family` |
| Qualifier 短 | `n` / `a` | `user_name` / `user_age` |

## 为什么不能只有时间戳

这是 HBase RowKey 设计的**第一大坑**：

```
RowKey = timestamp（毫秒）
  1700000000001 → Region A
  1700000000002 → Region A  ← 新时间戳更大，落在 Region A 末尾
  1700000000003 → Region A
  ...
  1700000360000 → Region A 打满 → Split 出新 Region B
  1700000360001 → Region B  ← 立刻又把 Region B 打满 → Split
  永远在尾 Region 持续写入 → 热点永远消不掉
```

**解法**：时间戳只能做后缀，前缀必须是**散列维度**（设备 ID、用户 ID、盐前缀等）。

## Region 预分裂

建表时可以指定 `SPLITS`，把 Region 提前建好，避免运行时 Split：

```java
byte[][] splits = new byte[][]{
  Bytes.toBytes("row1000"),
  Bytes.toBytes("row2000"),
  Bytes.toBytes("row3000"),
  Bytes.toBytes("row4000"),
};
admin.createTable(TableDescriptorBuilder.newBuilder(TableName.valueOf("user"))
  .setColumnFamily(ColumnFamilyDescriptorBuilder.of("info"))
  .addCoprocessor(...)
  .build(), splits);
```

- RegionServer 数量多时，预分裂的 Region 会被均匀分配到各 RS 上。
- 没有预分裂的表从 1 个 Region 开始，随着写入 Split 增长。

## 常见 RowKey 设计模板

| 业务场景 | RowKey 设计 | 备注 |
| --- | --- | --- |
| 用户画像（点查为主） | `hash(email/phone) + email/phone` | 哈希打散，保留明文方便调试 |
| 设备监控时序 | `device_id + reverse(timestamp_ms)` | 设备聚合、时间有序、反向时间让新数据排前 |
| 订单流水 | `tenant_id + reverse(date) + order_no` | 租户分片、日期倒序方便查最近 |
| 广告点级明细 | `ad_id + reverse(hour) + click_id` | 同一广告聚合，按小时倒序 |
| 日志（可重放） | `salt_prefix + hostname + reverse(timestamp)` | 打散 + 按主机聚合 |

## 易错点清单

1. **RowKey 只有时间戳 → 必然热点**：时间戳递增天然把所有新写到尾 Region。
2. **哈希后还想范围扫描 → 做不到**：哈希打散了有序性。
3. **RowKey 太长 → 浪费存储**：每个 Cell 都存 RowKey，别写成 200 字节。
4. **CF 名太长 → 浪费存储**：每个 HFile entry 都带 CF 名，用短名。

## 自测

1. 一个监控系统，每秒 10 万条设备上报，RowKey 该怎么设计？为什么不能只用时间戳？
2. 一个用户画像表，RowKey 用什么可以兼顾点查（按邮箱）和范围扫描（按注册日期）？
3. 加盐策略下，想扫描「uid 在 [10000, 20000] 的用户」，该怎么做？
4. 某表 RowKey = `user_10001, user_10002, ...`，现在想加租户维度改成 `tenant1_user_10001, tenant2_user_10001`，原来的 Region 怎么办？

## 参考与官方文档

- [HBase 数据模型](https://hbase.apache.org/2.5/book.html#datamodel)
- [HBase RowKey 设计最佳实践](https://hbase.apache.org/2.5/book.html#rowkey.design)
- [HBase 性能调优指南](https://hbase.apache.org/2.5/book.html#perf.rowkey)
