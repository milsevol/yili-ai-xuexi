# 10 生态对比与 FAQ

## 一句话

**Hadoop 的价值不在于「一个框架」，而在于它定义的三层接口**——存储层（HDFS）、资源层（YARN）、计算层（MR/Tez/Spark）；理解了这三层，才能判断什么该留、什么该换。

## 三层对比框架

| 层 | Hadoop 原生方案 | 现代替代 | 迁移现状 |
| --- | --- | --- | --- |
| **存储层** | HDFS | 对象存储（S3/OSS）+ 湖仓格式 | 新集群存算分离，存量 HDFS 继续跑 |
| **资源层** | YARN | Kubernetes | 新增负载逐步转向 K8s，YARN 保留存量 |
| **计算层** | MapReduce / Tez | Spark / Flink / Trino | MR 基本退场，Spark 成默认批引擎 |
| **元数据** | Hive Metastore | HMS / Iceberg Catalog / Unity / Glue | 一份元数据多引擎共享 |
| **调度** | Oozie | DolphinScheduler / Airflow | Oozie 退役，新项目不选 |

## HDFS vs 对象存储

| 维度 | HDFS | 对象存储（S3/OSS） |
| --- | --- | --- |
| 访问语义 | 类 POSIX，目录树、原子 rename | 扁平 key，目录是「前缀」；rename 是 copy + delete 或不支持 |
| 一致性 | 强一致 | 多数产品已强一致，但列表/覆盖语义仍有差异 |
| 追加写 | 支持 append、hflush/hsync | 不支持原地追加，只能整对象重写 |
| 延迟 | 毫秒级，本地盘 | 几十毫秒起，受网络与请求次数影响 |
| 小文件 | NN 内存瓶颈（每对象约 150–300 字节元数据） | 不计内存，但按请求计费，海量小文件成本高 |
| 数据本地性 | 有，任务可就近读 | 无，计算与存储分离 |
| 扩展 | 加节点、联邦、EC | 近乎无限，按量付费 |
| 成本 | 硬件 + 运维 + 三副本 | 存储便宜，但请求和流量要算账 |
| 运维 | 重（NN/DN/JN/ZK） | 交给云厂商 |

**湖仓格式怎么替代 HDFS 表**：

| 格式 | 解决的问题 | 特点 |
| --- | --- | --- |
| **Iceberg** | 表语义 + 快照 + 隐藏分区 | 引擎中立，Spark/Flink/Trino 都支持，增长最快 |
| **Hudi** | upsert + 增量拉取 | 适合 CDC 入湖，Mor表/CoW 表可选 |
| **Delta Lake** | ACID + 时间旅行 | 与 Spark 集成最好 |

它们把「目录即表」升级成「元数据文件即表」：ACID 事务、Schema 演进、时间旅行、小文件合并、并发写冲突处理，都靠快照和 manifest 实现，因此**能直接建在对象存储上**。

结论：**热数据、临时数据、需要低延迟的仍可用 HDFS；冷数据、归档、跨引擎共享的表放对象存储 + Iceberg。**

## YARN vs Kubernetes

| 维度 | YARN | Kubernetes |
| --- | --- | --- |
| 定位 | Hadoop 生态的资源管理与批处理调度 | 通用容器编排平台 |
| 调度单位 | Container（内存 + vcore） | Pod（CPU/内存/GPU/临时存储） |
| 调度能力 | 队列、抢占、数据本地性成熟 | 亲和性、污点、拓扑感知，原生不认 HDFS 本地性 |
| 多租户 | Capacity/Fair 队列 | Namespace + RBAC + ResourceQuota |
| 弹性 | 固定节点池，扩容靠加机器 | HPA/Cluster Autoscaler，弹性强 |
| 运行形态 | JVM 进程 + 本地化目录 | 镜像 + 容器，环境一致性好 |
| 运维 | 组件多、JVM 调优重 | 声明式、生态统一，但学习曲线陡 |
| 适用 | 存量 MR/Hive on Tez、传统 Hadoop 集群 | 新平台、Spark/Flink on K8s、混部 |

迁移趋势很明确：**新平台优先 K8s，YARN 保留给存量作业**。但要注意 K8s 不知道「数据在哪」，只能靠 nodeAffinity 近似本地性，跨集群读 HDFS 还会多一层网络开销。

## MapReduce vs Spark vs Flink vs Tez

| 维度 | MapReduce | Tez | Spark | Flink |
| --- | --- | --- | --- | --- |
| 模型 | 两阶段 map/reduce，磁盘落盘 | DAG，合并多个 MR | DAG，内存 + 磁盘 | 原生流，批是流特例 |
| 延迟 | 分钟级 | 秒–分钟 | 秒级（微批） | 毫秒级 |
| 中间结果 | 必落盘 | 尽量内存/选择性落盘 | 内存优先 | 内存 + 状态后端 |
| SQL 能力 | Hive on MR | Hive on Tez | Spark SQL 最强 | Flink SQL 增长快 |
| 状态管理 | 无 | 无 | 有状态算子，能力一般 | 强项（Checkpoint/Savepoint） |
| 生态 | 老作业 | 只服务 Hive | 批/流/ML/图/湖仓 | 实时数仓、CDC、CEP |
| 现状 | 退场 | 存量 Hive | 批处理默认 | 实时默认 |

**选型一句话**：离线批 → Spark；交互式查询 → Trino/Presto 或 Spark SQL；实时 → Flink；老 Hive 作业 → 先留 Tez，再逐步迁 Spark。

## 「Hadoop 已死」辨析

这句话对一半。

| 说法 | 是否成立 | 事实 |
| --- | --- | --- |
| MapReduce 已死 | **基本成立** | 新作业几乎没人写 MR，Spark/Flink 覆盖了绝大多数场景 |
| YARN 已死 | **部分成立** | 新增份额被 K8s 抢走，但政企、传统行业存量仍是主力 |
| HDFS 已死 | **不成立** | 存量数据量巨大（EB 级），对象存储替代的是「新增」，不是「存量」 |
| Hive 已死 | **部分成立** | 作为执行引擎在退，作为 Metastore 和 SQL 兼容层仍不可缺 |
| Hadoop 生态已死 | **不成立** | HDFS/YARN/ZK/HBase 仍在大量生产集群里跑 |

更准确的说法是：**Hadoop 从「一套全家桶」解耦成了「几个可独立替换的基础设施」**。存算分离后，HDFS 只做存储、Spark on K8s 读 HDFS、Hive 只留 Metastore，整栈绑定不再必要，但每一层单独拿出来仍有用。

学习价值也没消失：HDFS 的副本与一致性、YARN 的调度模型、MR 的 shuffle 与 combiner，仍是面试和排障的基本功，也是理解 Spark/Flink 的底层参照。

## 迁移路径

| 迁移 | 步骤 | 主要风险 |
| --- | --- | --- |
| HDFS → 对象存储/湖仓 | 盘点表 → 选 Iceberg → DistCp 搬迁 → 双写/校验 → 切元数据 → 下线旧表 | 小文件、rename 语义、权限映射、一致性校验、请求成本 |
| MR → Spark | 逐作业改写 → 结果比对 → 灰度 → 下线 | 语义差异（combiner、排序、倾斜）、资源模型不同 |
| YARN → K8s | 镜像化 → 提交方式改造 → 队列映射到 namespace → 监控接入 → 灰度 | 数据本地性、资源模型、Kerberos、日志采集 |
| Hive → Spark/Trino | 先共享 HMS → SQL 兼容性验证 → 引擎切换 → 逐步下线 HS2/Tez | UDF、ACID 表、复杂 SQL、权限差异 |

共同原则：**先共享元数据，再切计算；先双跑校验，再下线旧链路；每一步都要有回滚方案。**

## 高频面试题

### Q1：HDFS 的读写流程

**写**：客户端向 NN 请求创建文件 → NN 检查权限与副本数，返回可写的 DN 列表 → 客户端建立 pipeline（DN1→DN2→DN3）→ 按 packet 写入并逐级 ACK → 全部写完 close → NN 记录块信息。
**读**：客户端向 NN 获取块位置 → 按网络距离排序选 DN → 读取并校验 checksum → 失败换下一个副本 → 拼装成文件。
关键点：**数据流不经过 NN**，NN 只发指令；写失败会重建 pipeline，副本不足会异步补齐。

### Q2：NameNode 和 DataNode 的职责

NN 管**元数据**：目录树、文件与块的映射、每个块在哪些 DN 上、权限、配额；它**不存真实数据**。DN 存**块数据**，定期心跳和块汇报，执行读写、复制、删除。NN 是单点，所以要做 HA。

### Q3：SecondaryNameNode 是备份吗

**不是**。它只做 checkpoint：定期把 `fsimage` 和 `edits` 合并成新的 `fsimage`，减轻 NN 启动时的合并压力。NN 挂了它不能接管。HA 架构下这个角色由 Standby NameNode 承担。

### Q4：小文件为什么是问题，怎么处理

每个文件、每个块在 NN 内存里都要占元数据（约 150–300 字节），千万级小文件会把 NN 堆吃满，同时让 MR/Spark 产生海量 task。处理：写入端合并（`CombineFileInputFormat`、`spark.sql.files.maxPartitionBytes`）、HAR 归档、改 ORC/Parquet、用对象存储或 HDFS 联邦分散元数据。

### Q5：HDFS HA 怎么实现的

Active/Standby 两个 NN，共享 EditLog 存在 JournalNode（QJM，奇数台，过半写）；ZooKeeper 负责选举，ZKFC 监控 NN 健康并触发切换；fencing 确保旧 Active 真的停止服务，防止脑裂。客户端通过逻辑名 `mycluster` + `ConfiguredFailoverProxyProvider` 自动重试。

### Q6：副本放置策略

默认 3 副本：第 1 个放在写端所在节点（或同机架随机节点），第 2 个放在**不同机架**的节点，第 3 个放在第 2 个副本同机架的另一节点。这样兼顾可靠性（跨机架）与写入带宽（同机架第二份）。

### Q7：YARN 提交作业的流程

客户端 → RM 提交应用 → RM 分配 AM 容器 → 客户端在 NM 上启动 AM → AM 向 RM 注册并申请资源 → Scheduler 分配容器 → AM 通知 NM 启动 task → task 汇报进度 → 完成后 AM 注销、RM 清理。

### Q8：三种调度器的区别

FIFO 最简单但无隔离；CapacityScheduler 多队列、有 capacity 保证和 max-capacity 上限，适合多租户，是 Hadoop 3.x 默认；FairScheduler 按权重公平分配、支持抢占，适合批流混跑。选型：硬隔离选 Capacity，资源共享选 Fair。

### Q9：数据倾斜怎么发现和处理

现象：少数 task 耗时远超其他、Shuffle Read 分布极不均。处理：① 广播小表消除 join 倾斜；② 热点 key 加盐两阶段聚合；③ 拆分大 key 单独处理；④ 开启 AQE/skew join；⑤ 过滤无效 key。根因永远是 key 分布不均，不是「加大内存」。

### Q10：Combiner 是什么，什么时候不能用

Combiner 是 map 端的本地聚合，减少 shuffle 数据量。它要求聚合满足**结合律和交换律**，且不能改变最终结果：sum/count/max/min 可以；**avg 不行**（要拆成 sum 和 count）；涉及排序、去重、TopN 时要格外小心。

### Q11：Hadoop 常用压缩格式怎么选

| 格式 | 可切分 | 压缩比 | 速度 | 场景 |
| --- | --- | --- | --- | --- |
| gzip | 否 | 高 | 中 | 归档，单文件小于一个块 |
| bzip2 | 是 | 很高 | 慢 | 冷数据归档 |
| LZO | 需建索引 | 中 | 快 | 老方案 |
| Snappy | 否 | 中 | 很快 | 中间数据、Shuffle |
| ZSTD | 否 | 高 | 快 | Hadoop 3.x 新宠 |

原则：**中间结果求快（Snappy/ZSTD），最终归档求省（gzip/bzip2），列式文件（ORC/Parquet）用内置压缩即可。**

### Q12：Hadoop 和 Spark 是什么关系

Hadoop 提供**存储（HDFS）和资源（YARN）**，Spark 提供**计算引擎**，二者是互补不是替代。Spark 可以跑在 YARN 上读 HDFS，也可以跑在 K8s 上读对象存储。说「Spark 取代 Hadoop」不准确，准确说法是「Spark 取代了 MapReduce 这个计算层」。

## 学习路线与下一步

| 阶段 | 内容 | 产出 |
| --- | --- | --- |
| 入门 | HDFS Shell、MR WordCount、YARN UI | 能在伪分布式跑通全链路 |
| 进阶 | Hive SQL、分区/分桶、调度器、HA | 能搭 3 节点集群并跑数仓作业 |
| 精通 | NN/DN/RM 源码、调优、故障排查、容量规划 | 能独立运维一个生产集群 |
| 拓展 | Spark、Flink、HBase、Iceberg/Trino | 能设计存算分离的湖仓架构 |

下一步建议：先把本系列 06–09 的命令在伪分布式上跑一遍；再学 Spark（离线主力）和 Flink（实时）；最后补 Iceberg 与 Trino，完成从「Hadoop 集群」到「湖仓平台」的认知升级。

## 自测

1. 对象存储替代 HDFS 后，哪些能力反而变弱了？湖仓格式补上了哪些？
2. 为什么说「Spark 取代 MR，但不能说 Spark 取代 Hadoop」？
3. 一个团队要把 Hive on Tez 迁到 Spark SQL，你会先做哪三件事来降低风险？
4. YARN 和 K8s 的资源模型有什么本质差异？迁移时最容易踩的坑是哪个？
5. 面试官问「Hadoop 已死」，你怎么用三层框架给出有依据的回答？

## 参考与官方文档

- [Apache Hadoop 官网](https://hadoop.apache.org/)
- [Apache Iceberg](https://iceberg.apache.org/) / [Apache Hudi](https://hudi.apache.org/) / [Delta Lake](https://delta.io/)
- [Apache Spark](https://spark.apache.org/docs/latest/) / [Apache Flink](https://flink.apache.org/)
- [Trino 官方文档](https://trino.io/docs/current/)
- [Kubernetes 概念文档](https://kubernetes.io/docs/concepts/)
- [Apache HBase](https://hbase.apache.org/book.html) / [Apache Hive](https://hive.apache.org/)
