# 05 API与CRUD实战

## 一句话

HBase 的 API 很简单：**Put 写、Get 单点查、Delete 删、Scan 范围扫、Increment 原子计数**——但要真正用好，需要懂**批量操作、Scan 优化、BufferedMutator、异步 API**，以及 Python happybase 怎么用。

## 先装依赖

```bash
# Java Maven 依赖（HBase 2.5）
<dependency>
  <groupId>org.apache.hbase</groupId>
  <artifactId>hbase-client</artifactId>
  <version>2.5.8</version>
</dependency>

# Python happybase（pip 装）
pip install happybase

# Shell（自带，无需安装）
hbase shell
```

## HBase Shell 速查

最方便的快速验证工具：

```bash
hbase shell

# 建表：至少指定一个 ColumnFamily
create 'user', {NAME => 'info', VERSIONS => 3}, {NAME => 'addr'}

# 插入
put 'user', 'user001', 'info:name', 'Alice'
put 'user', 'user001', 'info:age', 28
put 'user', 'user002', 'info:name', 'Bob'

# 查询
get 'user', 'user001'                        # 取所有 CF 的最新版本
get 'user', 'user001', 'info:name'           # 取指定列
get 'user', 'user001', {VERSIONS => 3}       # 取多个历史版本

# 扫描
scan 'user'                                  # 全表扫（小表可以）
scan 'user', {STARTROW => 'user001', STOPROW => 'user010'}  # 范围扫
scan 'user', {FILTER => "ColumnPrefixFilter('info')"}       # 过滤

# 删除
delete 'user', 'user001', 'info:age'         # 删一个 Cell
deleteall 'user', 'user001'                  # 删整行

# 计数/统计
count 'user', INTERVAL => 1000               # 每 1000 行打一次进度
disable 'user'                               # 先 disable 才能改表
alter 'user', 'maxversion=5'                 # 改表属性
enable 'user'

# Admin
list                                         # 列出所有表
describe 'user'                              # 表结构
drop 'user'                                  # 删表（先 disable）
flush 'user'                                 # 手动 Flush
compact 'user'                               # 手动 Minor Compaction
major_compact 'user'                         # 手动 Major Compaction
```

## Java API —— Connection 初始化

```java
import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.hbase.*;
import org.apache.hadoop.hbase.client.*;

// 创建 Configuration（最简单是读 hbase-site.xml，或代码指定 ZK）
Configuration conf = HBaseConfiguration.create();
conf.set("hbase.zookeeper.quorum", "zk1,zk2,zk3");
conf.set("hbase.zookeeper.property.clientPort", "2181");

// Connection 是重量级对象，全局共享一个
Connection connection = ConnectionFactory.createConnection(conf);

// Table、Admin 是轻量的，用完 close
Table table = connection.getTable(TableName.valueOf("user"));
Admin admin = connection.getAdmin();
```

> **关键**：`Connection` 很贵，**一个进程建一个就行**；`Table` 和 `Admin` 每次用完 close（`try-with-resources`）。

## Put —— 写入

```java
// 单条 Put
Put put = new Put(Bytes.toBytes("user001"));
put.addColumn(Bytes.toBytes("info"), Bytes.toBytes("name"), Bytes.toBytes("Alice"));
put.addColumn(Bytes.toBytes("info"), Bytes.toBytes("age"), 28L);
put.addColumn(Bytes.toBytes("addr"), Bytes.toBytes("city"), Bytes.toBytes("Beijing"));
table.put(put);

// 指定时间戳（默认自动用当前毫秒）
put.addColumn(Bytes.toBytes("info"), Bytes.toBytes("name"), 1700000000L, Bytes.toBytes("Alice"));

// 关闭 WAL（日志类可重放数据，风险高）
put.setDurability(Durability.SKIP_WAL);

// 批量 Put（同步）
List<Put> puts = new ArrayList<>();
for (int i = 0; i < 1000; i++) {
    puts.add(new Put(Bytes.toBytes("user" + i))
        .addColumn(Bytes.toBytes("info"), Bytes.toBytes("name"), Bytes.toBytes("user_" + i)));
}
table.put(puts);  // 内部会切成 RPC 批次

// BufferedMutator（异步缓冲，性能更好）
BufferedMutatorParams params = new BufferedMutatorParams(TableName.valueOf("user"))
    .writeBufferSize(8 * 1024 * 1024)  // 缓冲区大小 8MB
    .maxKeyValueSize(1024 * 1024);
try (BufferedMutator mutator = connection.getBufferedMutator(params)) {
    for (int i = 0; i < 100000; i++) {
        mutator.mutate(new Put(Bytes.toBytes("user" + i))
            .addColumn(Bytes.toBytes("info"), Bytes.toBytes("name"), Bytes.toBytes("user_" + i)));
    }
    mutator.flush();  // 手动 Flush 剩余数据
}
```

## Get —— 单点查

```java
// 单条 Get
Get get = new Get(Bytes.toBytes("user001"));
get.addFamily(Bytes.toBytes("info"));           // 只查 info CF
get.addColumn(Bytes.toBytes("info"), Bytes.toBytes("name"));  // 只查某列
get.setMaxVersions(5);                          // 取 5 个历史版本
get.setTimeRange(1699990000L, 1700010000L);    // 时间范围

Result result = table.get(get);

if (result.isEmpty()) {
    System.out.println("not found");
} else {
    // 遍历所有 Cell
    for (Cell cell : result.rawCells()) {
        String row = Bytes.toString(cell.getRowArray(), cell.getRowOffset(), cell.getRowLength());
        String cf = Bytes.toString(cell.getFamilyArray(), cell.getFamilyOffset(), cell.getFamilyLength());
        String qual = Bytes.toString(cell.getQualifierArray(), cell.getQualifierOffset(), cell.getQualifierLength());
        long ts = cell.getTimestamp();
        byte[] value = CellUtil.cloneValue(cell);
        System.out.printf("row=%s, cf=%s:%s, ts=%d, val=%s%n", row, cf, qual, ts, new String(value));
    }

    // 取特定列（最新版本）
    byte[] nameValue = result.value();  // 等价于 getFamilyMap().get("info").get("name").get(0).getValue()
    String name = Bytes.toString(result.getValue(Bytes.toBytes("info"), Bytes.toBytes("name")));
    Long age = Bytes.toLong(result.getValue(Bytes.toBytes("info"), Bytes.toBytes("age")));
}

// 批量 Get（同步）
List<Get> gets = new ArrayList<>();
for (int i = 0; i < 100; i++) {
    gets.add(new Get(Bytes.toBytes("user" + i)).addFamily(Bytes.toBytes("info")));
}
Result[] results = table.get(gets);
```

## Delete —— 删除

```java
// 删一个 Cell（特定列）
Delete del = new Delete(Bytes.toBytes("user001"));
del.addColumn(Bytes.toBytes("info"), Bytes.toBytes("age"));       // 只删 age 这列的最新版本
del.addColumn(Bytes.toBytes("info"), Bytes.toBytes("age"), 1700000000L);  // 删特定时间戳的版本

// 删整行（所有列所有版本）
Delete delAll = new Delete(Bytes.toBytes("user001"));
// 不加任何 addColumn 就是删整行

// 删一个 CF（该 CF 的所有列所有版本）
Delete delCF = new Delete(Bytes.toBytes("user001"));
delCF.addFamily(Bytes.toBytes("addr"));

table.delete(del);
```

> **Delete 的真相**：不是立即物理删除，而是写一个**墓碑标记（Tombstone）**。Compaction 时才真正清理。所以删了之后，**Get/Scan 在 Major Compaction 之前仍可能"看到"墓碑标记**，但不会返回对应 Cell。

## Scan —— 范围扫描

```java
// 基础 Scan
Scan scan = new Scan();
scan.withStartRow(Bytes.toBytes("user001"));   // 包含
scan.withStopRow(Bytes.toBytes("user500"));    // 不包含
scan.addFamily(Bytes.toBytes("info"));
scan.setMaxResultsPerColumnFamily(1);          // 每个 CF 每列只取 1 个版本
scan.setCaching(100);                          // 每次 RPC 预取 100 条（默认 1，网络开销大）
scan.setBatch(10);                             // 每个 Row 最多返回 10 个 Cell

try (ResultScanner scanner = table.getScanner(scan)) {
    for (Result result : scanner) {
        String row = Bytes.toString(result.getRow());
        String name = Bytes.toString(result.getValue(Bytes.toBytes("info"), Bytes.toBytes("name")));
        System.out.println(row + " → " + name);
    }
}
```

### Scan 性能优化清单

| 配置 | 默认 | 建议 | 说明 |
| --- | --- | --- | --- |
| `setCaching(int)` | 1 | 100–500 | 一次 RPC 预取多少行，减少网络往返 |
| `setBatch(int)` | Integer.MAX_VALUE | 按需 | 每行返回多少个 Cell，宽表时避免一行巨多列 |
| `addColumn()` / `addFamily()` | 全部列 | 必要的列 | 不要扫描不需要的 CF，列式存储的关键优势 |
| `setFilter()` | 无 | 必要 | RegionServer 端过滤，减少网络传输 |
| `withStartRow/withStopRow` | 无边界 | 必须有 | 避免全表扫描 |
| `setReversed(true)` | false | 倒序时 | 反向扫描，配合反向时间戳 RowKey |
| `setAsyncPrefetch(true)` | false | true | 异步预取下一批，流水线效应 |

### 常用 Filter

```java
// 1. 行前缀过滤
Filter prefixFilter = new PrefixFilter(Bytes.toBytes("user00"));

// 2. 列值精确匹配
Filter valueFilter = new SingleColumnValueFilter(
    Bytes.toBytes("info"),          // CF
    Bytes.toBytes("city"),          // Qualifier
    CompareOperator.EQUAL,
    Bytes.toBytes("Beijing")        // 精确值
);
valueFilter.setFilterIfMissing(true);  // 如果该行没有这个列，跳过

// 3. 正则匹配
Filter regexFilter = new RowFilter(CompareOperator.EQUAL,
    new RegexStringComparator("user0[0-9]{3}"));

// 4. 单列范围
Filter rangeFilter = new ColumnRangeFilter(
    Bytes.toBytes("col_a"), true,   // 起始 qualifier（包含）
    Bytes.toBytes("col_m"), false); // 结束 qualifier（不包含）

// 5. 多种 Filter 组合
FilterList filters = new FilterList(FilterList.Operator.MUST_PASS_ALL);
filters.addFilter(prefixFilter);
filters.addFilter(valueFilter);
scan.setFilter(filters);
```

## Increment —— 原子计数

```java
// 自增（每次调用 +1；也可指定增量）
Increment inc = new Increment(Bytes.toBytes("counter_row"));
inc.addColumn(Bytes.toBytes("stats"), Bytes.toBytes("click"), 1L);  // 每次 +1
inc.addColumn(Bytes.toBytes("stats"), Bytes.toBytes("view"), 5L);   // 每次 +5

Result result = table.increment(inc);  // 原子操作，不会丢计数

// 初始值 0；如果 row 不存在也能正常 Increment
```

Increment 是原子的，因为它在 RegionServer 上执行（不是客户端计算再 Write），不会丢。

## CheckAndPut —— CAS 写入

```java
// 类似数据库的 UPDATE ... WHERE 条件
// 只有当条件满足时才 Put
Put put = new Put(Bytes.toBytes("user001"))
    .addColumn(Bytes.toBytes("info"), Bytes.toBytes("status"), Bytes.toBytes("active"));

boolean success = table.checkAndPut(
    Bytes.toBytes("user001"),
    Bytes.toBytes("info"),
    Bytes.toBytes("old_status"),
    CompareOperator.EQUAL,
    Bytes.toBytes("pending"),   // 只有当 old_status == "pending" 时才 Put
    put
);
```

## Python happybase 实战

```python
import happybase

# 连接
connection = happybase.Connection('zk1,zk2,zk3', port=2181)

# 建表（需要 admin 权限）
connection.create_table('user', {
    'info': dict(max_versions=3),
    'addr': {},
})

table = connection.table('user')

# Put
table.put(b'user001', {
    b'info:name': b'Alice',
    b'info:age': b'28',
    b'addr:city': b'Beijing',
})

# Get
row = table.row(b'user001', columns=[b'info:name', b'info:age'])
print(row[b'info:name'])   # b'Alice'

# Scan（范围）
for key, data in table.scan(row_start=b'user001', row_stop=b'user010', columns=[b'info']):
    print(key, data)

# 批量（更好的性能）
with table.batch() as batch:
    for i in range(1000):
        batch.put(f'user{i:05d}'.encode(), {b'info:name': f'user_{i}'.encode()})

# Delete
table.delete(b'user001', columns=[b'info:age'])  # 删一列
table.delete(b'user002')                          # 删整行

# Increment（happybase 支持 increment_column）
table.increment(b'counter_row', b'stats:click', 1)

connection.close()
```

## 异步 API（2.x 新特性）

```java
// AsyncConnection + AsyncTable，完全非阻塞
AsyncConnection asyncConn = ConnectionFactory.createAsyncConnection(conf).get();
AsyncTable<AdvancedScanResultConsumer> asyncTable = asyncConn.getTable(TableName.valueOf("user"));

// 异步 Put
CompletableFuture<Void> putFuture = asyncTable.put(
    new Put(Bytes.toBytes("user001")).addColumn(...)
);
putFuture.thenRun(() -> System.out.println("Put done!"));

// 异步 Get
CompletableFuture<Result> getFuture = asyncTable.get(new Get(Bytes.toBytes("user001")));
getFuture.thenAccept(result -> {
    if (!result.isEmpty()) System.out.println("Found!");
});
```

## 批量操作 vs 单条

| 方式 | 适用 | 注意 |
| --- | --- | --- |
| `table.put(Put)` 单条 | 低频、实时写入 | RPC 开销大，别每秒调几万次 |
| `table.put(List<Put>)` 同步批量 | 中高频 | 内部自动分片到不同 Region |
| `BufferedMutator` | 高频/海量写入 | 缓冲满了自动刷，需要手动 flush |
| `table.batch(List<? extends Row>)` | 混合操作 | 可以 Put/Get/Delete 一起；部分失败会抛异常 |
| Mapper/Reducer/Spark 并行 | 超大规模批量 | 用 `HBaseWriter` / Spark `newAPIHadoopRDD` |

## 易错点清单

1. **Connection 要全局共享**：每建一个 Connection 就多一组线程和 ZK 会话，别频繁创建。
2. **Scan 默认 setCaching=1**：每次只拉 1 行，10000 行就是 10000 次 RPC，扫描性能会很差。
3. **Delete 不立即物理删除**：Compaction 前墓碑还在；Major Compaction 才会清理。
4. **happybase increment 返回 int**：Python happybase 的 increment 返回的是新值（int），和 Java API 略有不同。
5. **版本号用小整数时注意类型**：Java 中 `Put.addColumn(cf, qual, 123L, value)` 的 timestamp 参数是 `long`，别传错类型。

## 自测

1. 用 Java API 写一段代码：从 `user` 表扫描 `user001` 到 `user1000` 的用户，取出 `info:name` 和 `info:age`，打印出来。注意 Scan 的 Caching 设置。
2. 某业务每秒 5000 次写入，单条 Put、同步批量、BufferedMutator 三种方式，你会选哪个？为什么？
3. Delete 一个 Cell 后立刻 Get，理论上还能读到吗？为什么？
4. CheckAndPut 怎么实现的？如果我想做"只有当 old_status 是 pending 时才改成 active"，但并发多个请求怎么办？

## 参考与官方文档

- [HBase Java API 参考](https://hbase.apache.org/2.5/apidocs/index.html)
- [HBase Client 配置](https://hbase.apache.org/2.5/book.html#client)
- [happybase 文档](https://happybase.readthedocs.io/)
- [异步客户端](https://hbase.apache.org/2.5/book.html#async.client)
