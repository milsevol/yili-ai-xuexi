# 02 HDFS 架构与原理

## 一句话

**HDFS**：一个「中心节点管元数据、数据节点存块、每个块放多份」的分布式文件系统，为「超大文件、一次写多次读、机器经常坏、要吞吐不要低延迟」的批处理场景设计。

## 设计假设决定架构

看懂 HDFS 的关键，是先接受它的假设。它的很多「奇怪设计」都是这些假设的直接结果。

| 假设 | 设计选择 | 好处 | 代价 |
| --- | --- | --- | --- |
| 硬件故障是常态 | 多副本 + 校验和 + 自动重建 | 廉价机器也能存住数据 | 3 副本吃掉 3 倍存储 |
| 流式读，批量扫全量 | 大块（默认 128MB）、顺序读 | 高吞吐、少寻址 | 随机小读很慢 |
| 文件很大 | 切块存储，块独立分布 | 单文件可大于单盘 | 小文件浪费元数据 |
| 一次写、多次读，只追加 | 不支持任意位置改写 | 一致性模型简单 | 不能改中间字节 |
| 移动计算比移动数据便宜 | 计算任务尽量调度到数据所在节点 | 省网络、省时间 | 跨机架读取成为瓶颈 |

## 角色分工

```
Clients ──①元数据RPC──► NameNode（目录树/块映射，不存真实数据）
   │                      │ EditLog（HA 时写 JournalNode 集群，2F+1）
   └──②数据流──► DataNode 1/2/3 ...（本地盘：block + checksum）
```

| 角色 | 职责 | 关键点 |
| --- | --- | --- |
| **NameNode** | 目录树、文件到块的映射、副本位置、权限/配额 | 内存是瓶颈；HA 下 Active/Standby |
| **DataNode** | 存 block、执行读写、上报块、校验和 | 坏盘/坏节点由它先暴露 |
| **JournalNode** | HA 时共享 EditLog，让 Standby 追上 Active | 至少 3 台，过半写成功才算提交 |
| **ZKFC** | 监控 NN 健康、触发切换、fencing | 每台 NN 配一个，依赖 ZooKeeper |
| **Client** | 发起读写，自己直连 DataNode 传数据 | 元数据走 NN，数据不经过 NN |
| **Router** | Federation 下统一挂载多个命名空间 | 3.x 的 RBF，客户端只连 Router |

## 块与副本

**块：默认 128MB**

- `dfs.blocksize` 默认 **134217728 字节（128MB）**；Hadoop 1.x 时代默认 64MB。
- 130MB 的文件切成 2 块：128MB + 2MB。小于块大小的文件只占 1 个块，磁盘上是实际字节数，但 NN 仍记 1 条块信息。
- 块大的好处：NN 管理的块更少、寻址切换开销小、顺序扫描吞吐高；代价：单文件可并行的 map 少，小文件更吃亏。

**副本：默认 3，且机架感知**

- `dfs.replication` 默认 **3**；可按文件改：`hdfs dfs -setrep -w 2 /data/file`。
- 同一块在 3 台 DataNode 上各一份，**能容忍 2 份副本损坏**，不是「坏 3 台也没事」。

```
机架 A：DN1(客户端所在)   DN2        机架 B：DN3   DN4
副本1 → DN1（本机）   副本2 → DN3（另一机架）   副本3 → DN4（与副本2同机架的另一台）
```

- 客户端不在集群内时，第一份放客户端所在机架的随机节点；第二份放**另一机架**；第三份放**与第二份同机架的另一台**。这样只跨两个机架，减少跨机架写流量。
- 只有 1 个机架时退化为「分散到不同节点」，没有机架级容错。
- 3 副本放在 2 个机架时，坏一个机架可能只剩 1 份：还能读，但没有冗余。想有 rack 级容错，至少 3 个机架并保证副本分布。

## 元数据：NameNode 内存里有什么

NameNode 保存的是**命名空间**，不是数据本身：

| 内容 | 说明 | 是否持久化 |
| --- | --- | --- |
| INode（文件/目录） | 路径、类型、权限、owner/group、mtime、配额 | 是（FsImage） |
| 文件 → 块列表 | 每个文件由哪些 block 组成、块大小、偏移 | 是（FsImage） |
| 块 → 副本位置 | 哪些 DataNode 上有这个块 | **否**，由块报告重建 |
| Lease（租约） | 哪个客户端正在写哪个文件 | 内存中，重启后恢复 |
| 快照、加密区、EC 策略 | 目录级元数据 | 是（FsImage） |

- **FsImage** 是命名空间完整快照，**EditLog** 是追加的变更日志；NN 启动时加载 FsImage、重放 EditLog、进安全模式等块报告。
- **块报告**：DataNode 启动时全量上报；运行中周期上报（`dfs.blockreport.intervalMsec` 默认 6 小时），心跳默认 3 秒。
- **stale 判定**：约 10.5 分钟没心跳（`2 × recheck-interval + 10 × heartbeat`）后不再优先分配读。
- **内存估算**：每个文件/目录/块对象约 **150 字节**；1 亿小文件光文件对象就约 15GB，加上块和副本位置通常按 **15–20GB 堆**估。小文件治理本质是给 NN 减负。

## 写流程

```
Client                NameNode              DN1 ──► DN2 ──► DN3
 create ─────────────► 建 INode + 租约
 addBlock ───────────► 选副本位置 ──► LocatedBlock(块ID+位置+代际号)
 packet ───────────────────────────────► 逐级转发（64KB/包，512B/chunk 带校验和）
 ◄────────────────────────── ack ─────── 反向逐级回传
 close / complete ───► 确认最小副本数，文件置为 complete
```

1. **create**：客户端 RPC 调 `create()`，NN 检查父目录权限与是否已存在，创建 INode，并发**租约（lease）**防止并发写。
2. **addBlock**：请求第一个块，NN 按机架感知选副本节点，返回块 ID、代际号和位置列表。
3. **建 pipeline**：客户端按「DN1 → DN2 → DN3」建管道，数据只发 DN1，由 DN1 转发 DN2、DN3。
4. **写 packet**：数据切成 **packet（默认 64KB，`dfs.client-write-packet-size`）**，每个 packet 含多个 **512 字节 chunk**，每个 chunk 带校验和。
5. **ack 回传**：DN3 写完发 ack 给 DN2，DN2 给 DN1，DN1 回客户端；只有收到 ack 才算该 packet 成功。
6. **故障恢复**：DN 失败触发 pipeline recovery：剔除坏节点、用新代际号重建管道、从失败 packet 继续；剩余副本不足则写失败。
7. **close / complete**：发完剩余 packet、关闭 pipeline，再调 `complete()`；NN 确认最后一块达到最小副本数后文件才完整。

两个容易混的 API：

| 操作 | 做了什么 | 保证 |
| --- | --- | --- |
| `write()` | 写入客户端缓冲区 | 只保证进了客户端内存 |
| `hflush()` | 推 packet 进 pipeline 并等所有 DN 的 ack | 对读者可见，在 DN 的 OS 缓存里；**断电可能丢** |
| `hsync()` | `hflush` 后再要求每个 DN fsync 到磁盘 | 真正落盘，延迟明显更高 |

注意：**HDFS 只支持追加，不支持在文件中间随机改写**；要改内容就重写整个文件。

## 读流程

1. **open**：客户端调 `open()`，NN 返回该文件所有块的位置（`getBlockLocations`）。
2. **选副本**：位置按网络距离排序——本机 → 同机架 → 同机房 → 跨机房，优先读最近的。
3. **直连 DN**：客户端直接向选中的 DataNode 发读请求，数据不经过 NN。
4. **校验**：每个 chunk 用校验和验证；损坏则向 NN 上报坏块（`reportBadBlocks`），拉黑该副本并换下一个。
5. **顺序读**：读完一块自动取下一块位置；所有副本都坏才抛 `BlockMissingException`。

## SecondaryNameNode 不是热备（重点纠错）

| 对比 | SecondaryNameNode | HA 的 Standby NameNode |
| --- | --- | --- |
| 主要工作 | 定期合并 FsImage + EditLog（checkpoint） | 实时同步 EditLog，随时可切为主 |
| 是否持有最新命名空间 | **否**，只到上次 checkpoint | 是，持续追平 Active |
| NN 挂了能否接管 | **不能** | 能（配合 ZKFC/fencing） |
| 是否对外提供读写 | 不能 | 切换后可以 |

- 它做的事：拉取 FsImage 和 EditLog → 本地合并成新 FsImage → 推回 NN。目的是**防止 EditLog 无限增长、加快 NN 重启**。
- 它不做的事：不接收客户端请求、不保存实时块位置、不参与故障切换。
- 配置：`dfs.namenode.checkpoint.period` 默认 3600 秒，`dfs.namenode.checkpoint.txns` 默认 100 万事务，达到任一条件触发 checkpoint。
- HA 集群里 checkpoint 由 **Standby NN** 做，通常不再部署 SecondaryNameNode。

## HA：QJM + ZKFC

```
Active NN ──写 edits──► [JN1 | JN2 | JN3] ──tail edits──► Standby NN
                          2F+1：3 台容忍 1 台坏，5 台容忍 2 台
```

- **2F+1**：至少 3 台 JournalNode 才能容忍 1 台故障；写 EditLog 只要**过半数**（3 台中 2 台、5 台中 3 台）成功就算提交。
- **Standby 追 edits**：从 JournalNode 读取并应用，保持同步，同时承担 checkpoint。
- **ZKFC**：每台 NN 配一个，监控健康、在 ZooKeeper 抢临时节点；Active 挂了就 **fencing**（sshfence/shell 确保老 Active 停止写），再把 Standby 提升。
- **fencing 为什么必须**：网络分区时老 Active 可能还活着并在写，出现「双主」会写坏元数据；QJM 代际号 + fencing 一起防脑裂。
- 自动切换：`dfs.ha.automatic-failover.enabled=true`，依赖 `ha.zookeeper.quorum`；手工命令 `hdfs haadmin -getServiceState nn1`、`hdfs haadmin -failover --forcefence --forceactive nn1 nn2`。
- 关键配置：`dfs.nameservices`、`dfs.ha.namenodes.<ns>`、`dfs.namenode.shared.edits.dir=qjournal://jn1:8485;jn2:8485;jn3:8485/<ns>`。

## Federation 与 Router

单个 NN 的元数据能力有上限。**Federation** 用多个独立 NN，每个管一个 namespace 和一个 block pool：

- 水平扩展元数据：100 亿文件可以拆到多个 NN；每个 namespace 可各自做 HA。
- 缺点：**跨 namespace 没有原子 rename、没有全局快照**，搬数据要用 `distcp`。
- 访问方式：**ViewFs**（客户端挂载表）或 **Router（RBF，3.x）**（服务端统一入口，Router 无状态、可多实例做 HA）。
- Router 用 `hdfs dfsrouteradmin` 管理挂载点，参数以版本文档为准。

## 安全模式、快照、回收站、透明加密

| 能力 | 作用 | 常用命令/配置 |
| --- | --- | --- |
| **安全模式** | NN 启动时等块报告；手动进入可做维护；写被拒绝 | `hdfs dfsadmin -safemode get/enter/leave/wait` |
| **快照** | 目录级、只读、时间点副本；写时复制 | `hdfs dfs -createSnapshot /data s1`；`hdfs snapshotDiff /data s1 s2` |
| **回收站** | 删除文件先进 `.Trash`，到期清理 | `fs.trash.interval` 默认 0（关闭），生产常设 1440 分钟 |
| **ACL** | 比 755/750 更细的按用户/组授权 | `hdfs dfs -setfacl -m user:alice:rwx /data` |
| **透明加密** | DataNode 落盘加密，客户端无感 | `hadoop key create k1`；`hdfs crypto -createZone -keyName k1 -path /secure` |

- 安全模式退出条件：报告的块比例达到 `dfs.namenode.safemode.threshold-pct`（默认 0.999），再等 `dfs.namenode.safemode.extension`（默认 30 秒）。
- 回收站不是备份：`-rm -skipTrash` 直接删，`-expunge` 立即清空。透明加密依赖 KMS。

## 3.x 纠删码（Erasure Coding）

3 副本的存储开销是 200%。冷数据很少读，再放 3 份不划算，于是有了 **EC**：

- 默认策略 **RS-6-3-1024k**：6 个数据块 + 3 个校验块，共 9 个内部块；存储开销 **1.5 倍**，相比 3 副本**省 50%**，可容忍任意 3 个内部块损坏。
- 一条 stripe 由 6 个 1MB cell 组成，内部块分布在不同 DataNode/机架；RS-6-3 至少需要 **9 台 DataNode**，想要 rack 级容错建议至少 3 个机架。
- EC 是**条带化**写入，写放大和网络开销比副本高，读要多路并行，**适合冷/温数据，不适合频繁写**。
- **限制（重点）**：EC 文件不支持 `append`、`hflush`、`hsync`、`truncate`、`concat`、`setReplication`；副本数对 EC 文件无意义（恒为 1）。
- NN 内存：EC 每个内部块只有 1 份副本位置，副本条目比 3 副本少一半；块组命名也减少额外块开销。但内部块数量是逻辑块的 1.5 倍，别简单理解成「NN 堆减半」。
- 策略是**目录级**的，只影响新文件；已有文件转 EC 只能重写（例如 `distcp` 到新目录）。命令：`hdfs ec -enablePolicy -policy RS-6-3-1024k`、`hdfs ec -setPolicy -path /cold -policy RS-6-3-1024k`、`hdfs ec -getPolicy -path /cold`。

## 易错点清单

1. **把 SecondaryNameNode 当备胎**：它只做 checkpoint，NN 挂了救不了场。
2. **以为 3 副本能坏 3 台**：只能容忍 2 份副本丢失；坏 1 个机架也可能只剩 1 份。
3. **以为 `hflush` 就落盘、EC 能随便写**：`hflush` 只到 DN 的 OS 缓存；EC 不支持 append/hflush，冷数据专用。

## 自测

1. HDFS 为什么把块做到 128MB，而不是 4KB 或 1GB？分别会带来什么问题？
2. 3 副本放在 2 个机架上，坏掉一个机架后还能不能读？还有没有冗余？
3. 客户端调用 `hflush()` 后机器断电，数据一定还在吗？`hsync()` 呢？

## 参考与官方文档

- [HDFS Architecture](https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html)
- [HDFS High Availability Using the Quorum Journal Manager](https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-hdfs/HDFSHighAvailabilityWithQJM.html)
- [HDFS Federation](https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-hdfs/Federation.html)
- [HDFS Erasure Coding](https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-hdfs/HDFSErasureCoding.html)
