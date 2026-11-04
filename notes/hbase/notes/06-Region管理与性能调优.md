# 06 Region管理与性能调优

## 一句话

HBase 的性能调优围绕三个核心：**Region 不热点、Compaction 不爆 IO、写路径不阻塞**——具体手段是 Region 分裂策略、Compaction 策略选择、WAL 配置、热点打散与 JVM/内核调优。

## Region 分裂策略

Region 大小超过阈值时自动 Split。错误的分裂策略会导致热点、Compaction 风暴、Region 抖动。

| 策略 | 默认 | 说明 | 适用 |
| --- | --- | --- | --- |
| **ConstantSizeRegionSplitPolicy** | 是（2.5+） | Region 固定大小阈值（默认 10GB）时 Split | 大多数场景，简单稳定 |
| **IncreasingToUpperBoundRegionSplitPolicy** | 否（2.4 前默认） | 阈值随 Region 数量动态增大 | 旧表兼容 |
| **KeyPrefixRegionSplitPolicy** | 否 | 按 RowKey 前缀拆分，保证同一前缀在同一 Region | 有业务前缀分区的场景 |
| **DisabledRegionSplitPolicy** | 否 | 关闭自动 Split，完全手动 | 对 Region 数量极其敏感的场景 |

### 关键配置

| 配置 | 默认 | 说明 |
| --- | --- | --- |
| `hbase.hregion.max.filesize` | 10737418240 (10GB) | Region 大小阈值 |
| `hbase.hregion.memstore.flush.size` | 128MB | CF 级 Flush 阈值 |
| `hbase.regionserver.global.memstore.size` | 0.40（堆） | RS 级总 MemStore 上限 |
| `hbase.regionserver.global.memstore.lowerLimit` | 0.38（堆） | 低于此值停止阻塞写入 |
| `hbase.hregion.memstore.block.multiplier` | 4 | 超过 `flush.size × multiplier` 时阻塞写入 |

### 预分裂（建表时指定）

```bash
# Shell 方式（手动指定 Split 点）
create 'user', 'info', 'addr', SPLITS => ['row1000', 'row2000', 'row3000', 'row4000']

# Java 方式
byte[][] splits = new byte[][]{
  Bytes.toBytes("row1000"), Bytes.toBytes("row2000"), Bytes.toBytes("row3000")
};
admin.createTable(
  TableDescriptorBuilder.newBuilder(TableName.valueOf("user"))
    .setColumnFamily(ColumnFamilyDescriptorBuilder.of("info"))
    .build(),
  splits
);

# 按 RowKey 哈希均匀分裂（更通用）
admin.createTable(..., RegionSplitter.HashStringSplit, 256);
admin.createTable(..., RegionSplitter.UniformSplit, 512);
```

### Split 风暴

当集群快速写入、Region 大量 Split 时，每个新 Region 要在 HMaster 调度下迁移到其他 RS，容易产生：

- 短时间内大量 Region 迁移 → HMaster 忙不过来
- 新 Region 立刻开始接收新写入 → 快速再次 Flush → 新 HFile → 触发 Compaction
- 连锁反应 → RS 间 IO 打满、延迟飙升

**应对**：预分裂、调大 Split 阈值、错开大表的初始建表时间、控制写入速率。

## Compaction 策略与调优

Compaction 是影响 HBase 读写延迟的最大因素之一。策略选错要么读路径太长（Compaction 太少），要么 IO 打满（Compaction 太多）。

### 策略对比

| 策略 | 适合场景 | 核心逻辑 |
| --- | --- | --- |
| **ExploringCompactionPolicy**（默认 2.5+） | 大多数生产场景 | 分层合并：小文件优先合并，合并产物逐级向上 |
| **RatioBasedCompactionPolicy** | 兼容旧版本 | 按大小比选文件，最老或最小优先 |
| **FIFOCompactionPolicy** | 时序数据、纯追加 | 按时间淘汰，老文件直接跳过不合并 |
| **DateTieredCompactionPolicy** | 时序数据冷热分层 | 按时间分 Tier，同 Tier 合并 |

### 阈值调优

| 配置 | 默认 | 建议范围 | 说明 |
| --- | --- | --- | --- |
| `hbase.hstore.compactionThreshold` | 3 | 3–5 | 至少几个 HFile 才触发 Minor |
| `hbase.hstore.compaction.max` | 10 | 5–20 | 一次 Minor 最多合并几个 |
| `hbase.hstore.compaction.min.size` | 128MB | 64–256MB | 小于此大小优先选中（小文件先合并） |
| `hbase.hstore.compaction.max.size` | LONG.MAX_VALUE | 1–4GB | 大于此大小不参与合并（保护大文件） |
| `hbase.hregion.majorcompaction` | 7 天 | 7–30 天（或 0 关闭自动） | Major 周期，生产常用手动 Major |
| `hbase.compaction.ratio` | 1.2 | 1.0–2.0 | 新文件大小比老文件，越大越宽松 |

### Compaction 队列与限流

```bash
# 查看 Compaction 队列
hbase shell
> compaction_queue 'user'

# RS UI /tables.jsp 看每个 Region 的 compaction 状态

# 并行 Compaction 线程数（默认等于 CPU 核数）
hbase.hstore.compaction.threads  # 默认 10
hbase.hstore.flush.threads       # 默认 10
```

- Compaction 重的表（大 Region、多 HFile）可以设 `COMPACTION_PRIORITY => HIGH`。
- **离线 Compaction（2.5+）**：RS 资源不够时把 Compaction 任务丢到独立的 Compaction Service 执行，不阻塞 RegionServer 主线程。

## WAL 配置

WAL 是写路径的第一步，但它也是性能关键点：

| 配置 | 默认 | 建议 | 说明 |
| --- | --- | --- | --- |
| `hbase.regionserver.wal.impl` | AsyncFSWAL | AsyncFSWAL | 异步写 WAL（性能好）；SyncFSWAL 是老同步实现 |
| `hbase.regionserver.wal.blocksize` | HDFS 块大小 | HDFS 块大小 | WAL 的 HDFS block 大小 |
| `hbase.regionserver.wal.logrollperiod` | 60 分钟 | 60–240 分钟 | WAL 滚动周期 |
| `hbase.regionserver.wal.maxentries` | 32768 | 32768 | 单个 WAL 文件最大 entries |
| `hbase.wal.groupedflush` | true | true | 多 Region 的 WAL Flush 合并，减少 HDFS RPC |
| `hbase.regionserver.wal.skipWALOnRecovery` | false | false | 不要跳过 WAL 恢复，会丢数据 |

### WAL fsync 调优

HDFS 默认 `dfs.client.datanode.drop-behind-cache.buffer-size` 可能影响 WAL fsync 延迟。高写入场景考虑：

```xml
<!-- hdfs-site.xml -->
<property>
  <name>dfs.client.datanode.drop-behind.cache</name>
  <value>true</value>
</property>
<property>
  <name>dfs.client.datanode.drop-behind-cache.buffer-size</name>
  <value>65536</value>
</property>
```

### Per-Region WAL（2.5+）

默认 RS 上所有 Region 共用一个 WAL 文件。2.5 起支持 Per-Region WAL：每个 Region 独立 WAL 文件。好处：

- Region 迁移时只需要迁移它自己的 WAL
- WAL 恢复时不需要遍历其他 Region 的日志
- 坏处：文件打开句柄更多、HDFS 文件数量更多

```xml
<!-- hbase-site.xml -->
<property>
  <name>hbase.wal.provider</name>
  <value>filesystem</value>  <!-- filesystem = 共享WAL；也可以 perregion 独立WAL -->
</property>
```

## 写吞吐量调优

写性能的瓶颈通常在这几个地方，按顺序排查：

### 1. RowKey 热点

```bash
# Shell：看哪些 Region 写得最多
hbase shell
> status 'detailed'

# 或看 RegionServer Web UI：/rs-status.jsp
# 找写请求特别集中的 Region → 查它的 RowKey 范围 → 看是不是 RowKey 设计有问题

# 客户端：RegionLocator 看 Region 分布
java -cp hbase-client.jar:... org.apache.hadoop.hbase.util.RegionSplitter
```

### 2. MemStore 阻塞

当 `global.memstore.size` 超限时，新 Put 请求会被**阻塞**等待 Flush：

```java
// 客户端调 put 一直超时
// → 查 RegionServer 日志：
grep -i "blocking" hbase-*.log
grep -i "memstore" hbase-*.log

// 指标：MemStore size、flush time、blocked requests
```

**解决**：增加 RS 内存（加大堆）、调大 `global.memstore.size`、或增加 Region 数量（每个 Region 的 MemStore 上限独立）。

### 3. Flush 风暴

MemStore 同时到达阈值，批量 Flush → HDFS IO 打满：

- 错开 Flush 触发（2.5 多段 Flush 天然缓解）
- 控制 Region 数量（Region 太多会让同时 Flush 的概率升高）
- 增加 HDFS DataNode 的磁盘和网络

### 4. HDFS 写延迟

WAL 和 HFile 都写 HDFS，HDFS 慢 → 整个写路径慢：

- DataNode 磁盘 await 高 → 换 SSD 或更多磁盘
- 网络丢包/高延迟 → 排查网络
- 客户端 packet size 太小 → 调大 `dfs.client-write-packet-size`

### 5. BulkLoad（绕过 WAL + Flush）

批量导入数据时，走正常 Put 会触发 WAL + Flush + Compaction，极慢。BulkLoad 直接在客户端生成 HFile 并 move 到 HDFS：

```java
// 1. MR/Spark 并行生成 HFile
// 2. Load 到 HBase
TableName tn = TableName.valueOf("user");
String hfilePath = "/tmp/bulkload/user";

Configuration conf = new Configuration();
conf.set(HTableDescriptor.CONFIGURATION_PRESET, "HTableDescriptor.MOBILE_COMPRESSION");
LoadIncrementalHFiles loader = new LoadIncrementalHFiles(conf);
loader.doBulkLoad(new Path(hfilePath), admin, table, regionLocator);
```

> BulkLoad 是数据导入的**首选方式**，但它绕过了 WAL——如果 BulkLoad 还没完成 RegionServer 就挂了，可能产生数据不一致（HFile 在 HDFS 但 Region 元数据没更新）。

## 热点 Region 定位与打散

### 定位

```bash
# 方法 1：RegionServer Web UI → Region 列表 → 看 Read Request Count / Write Request Count
http://regionserver-host:16030/rs-status.jsp

# 方法 2：HBase Shell status 命令
hbase shell
> status 'detailed'

# 方法 3：metrics 系统（Prometheus/Grafana）
hbase_region_server_regions_requests_write  # 写入请求数
hbase_region_server_regions_requests_read   # 读取请求数

# 方法 4：hbase hfile 工具看 HFile 大小（间接判断 Region 负载）
hbase hfile -m -f /hbase/data/default/user/xxx/info/*.hfile
```

### 打散方法

| 方法 | 适用 | 做法 | 注意 |
| --- | --- | --- | --- |
| **手动 Split** | 热点 Region 还没到 Split 阈值但明显热点 | `hbase shell` → `split 'user', 'row3000'` | Split 后新 Region 还可能热点，要根因 |
| **修改 RegionKeyPolicy** | 热点来自 RowKey 前缀分布不均 | 改成 `KeyPrefixRegionSplitPolicy` | 需要重新建表或重启 |
| **手动 Move Region** | 某台 RS 上 Region 太多 | `hbase shell` → `move 'ENCODED_REGION_NAME', 'RS_HOST:16020'` | 治标不治本，热点 RowKey 还是会让新 Region 也热点 |
| **重设计 RowKey** | 热点来自 RowKey 设计（根因） | 加盐/哈希/反转，**重建表 + BulkLoad** | 最彻底，但要有数据迁移方案 |
| **按热点前缀拆分** | 热点集中在某段 RowKey | Split 后再 Move 到不同 RS | 配合 RowKey 前缀分区策略 |

### 手动 Split 示例

```bash
hbase shell
# 列出 user 表所有 Region
> describe 'user'
# 或
> list_regions 'user'

# 手动 Split 某个 Region
> split 'user', 'row10000'

# 手动 Move Region 到指定 RS
> move 'abcdef123456', 'rs-node-05:16020'
```

## JVM 调优

RegionServer 的堆是性能调优的核心：

| 参数 | 推荐 | 说明 |
| --- | --- | --- |
| `-Xms` / `-Xmx` | 堆的 70–80% 用于 MemStore+BlockCache | RS 一般 8–24GB 堆 |
| `-XX:+UseG1GC` | G1 默认；2.6 支持 ZGC | CMS 已废弃 |
| `-XX:MaxGCPauseMillis=100` | 控制 G1 最大暂停时间 | 影响 RS 心跳稳定性 |
| `-XX:+ParallelRefProcEnabled` | Parallel GC 的引用处理 | G1 也可开 |
| `-XX:ConcGCThreads=N` | 并发 GC 线程数，建议等于 CPU 核数 | |
| `-XX:+AlwaysPreTouch` | 启动时预触页 | 减少运行时缺页 |

### BlockCache vs MemStore 的分配

RS 堆分成三块：

```
总堆空间
├── 10% 预留给 JVM 自己（metaspace、code cache、direct buffers）
├── N%  BlockCache（读缓存，默认 40%）
└── M%  MemStore（写缓冲，默认 40%）
```

- **读多写少** → BlockCache 占比大（如 50–60%）
- **写多读少** → MemStore 占比大（如 50–60%）
- `hfile.block.cache.size` 和 `hbase.regionserver.global.memstore.size` 之和必须 < 0.80（预留 20%）

### GC 问题排查

```bash
# 看 GC 日志
-XX:+PrintGCDetails -XX:+PrintGCDateStamps -Xloggc:/var/log/hbase/rs-gc.log

# 监控：Full GC 次数、GC 暂停时间
jstat -gcutil <pid> 1000

# Prometheus 指标
hbase_jvm_garbagecollector_seconds
hbase_jvm_memory_usage_bytes{area="heap"}
```

- **Full GC 频繁** → 堆不够？对象泄漏？BlockCache/MemStore 分配多了？
- **GC 暂停 > 10s** → RegionServer 心跳超时 → HMaster 以为它挂了 → 触发 Region 重分配 → 更糟

## Linux 内核调优

| 参数 | 推荐值 | 说明 |
| --- | --- | --- |
| `net.ipv4.tcp_tw_reuse` | 1 | 高并发下减少 TIME_WAIT |
| `net.ipv4.tcp_fin_timeout` | 30 | 缩短 FIN_WAIT2 |
| `net.core.somaxconn` | 32768 | 增大 backlog 队列 |
| `net.core.netdev_max_backlog` | 32768 | 增大网卡队列 |
| `vm.swappiness` | 0（禁用 swap） | 避免内存被 swap 导致 GC 超时 |
| `vm.overcommit_memory` | 1 | 允许 overcommit，配合 JVM |
| `fs.file-max` | 65536 | 增大文件句柄上限 |
| `ulimit -n` | 65536 | 进程级文件句柄 |

### 禁用 Swap（关键！）

```bash
# 立即生效
swapoff -a

# 永久：注释 /etc/fstab 里的 swap 行
# 或配置 vm.swappiness=0
sysctl -w vm.swappiness=0
echo "vm.swappiness=0" >> /etc/sysctl.conf
```

> **Swap 是 HBase 的杀手**：RegionServer 进程任何一页被 swap 出去，回来的延迟可能到秒级，直接导致心跳超时、Region 被重分配。**生产集群必须禁用 swap**。

## 易错点清单

1. **手动 Split 后不解决根因**：RowKey 还是热，Split 出来的新 Region 很快再热点 → 循环
2. **Region 太多会让 MemStore 总占用变大**：每个 Region 的 MemStore 独立，但 RS 有全局上限
3. **Major Compaction 没开 → 墓碑和过期版本堆积**：读路径查旧数据，浪费时间；磁盘上也堆积
4. **BlockCache 开但命中率低**：检查 HFile 数量（Compaction 太松）、RowKey 设计（随机查）、RS 内存够不够
5. **没禁用 swap → 偶发性心跳超时**：最难排查的问题之一，机器偶发抖一下就触发

## 自测

1. 某业务每秒 10 万写入，RowKey 是 `timestamp_ms`，Region 10GB 阈值，会发生什么？怎么改？
2. Compaction 队列长时间排满、写请求超时，你会先查哪些指标？
3. BulkLoad 和正常 Put 有什么区别？什么场景必须用 BulkLoad？
4. 生产集群的某台 RegionServer 心跳超时被 HMaster 判死，但你登录机器发现它还在跑——最可能的原因是什么？怎么预防？

## 参考与官方文档

- [HBase 性能调优指南](https://hbase.apache.org/2.5/book.html#perf)
- [Compaction 深度解析](https://hbase.apache.org/2.5/book.html#compaction)
- [Regions 与 MemStore 调优](https://hbase.apache.org/2.5/book.html#regions.arch)
