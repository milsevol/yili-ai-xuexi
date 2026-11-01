# 06 YARN 资源管理与调度

## 一句话

**YARN = 把「资源管理」和「作业调度」拆成两层**：ResourceManager 只管全局发资源，ApplicationMaster 只管自己这个作业，NodeManager 只管单机上的一批容器——集群因此能从一个 JobTracker 扩到上千节点。

## 为什么需要 YARN

MRv1 的问题不是「MapReduce 慢」，而是 JobTracker 一个人干了所有活：

| MRv1 痛点 | 具体表现 |
| --- | --- |
| **单点瓶颈** | JobTracker 同时负责调度、资源管理、任务监控，规模上限在数千任务量级 |
| **资源粒度粗** | map slot / reduce slot 固定划分，map 闲着 reduce 不能用 |
| **框架绑定** | 只认 MapReduce，Spark、Tez、Flink 接不进来 |
| **故障影响大** | JobTracker 重启，所有运行中作业全丢 |

YARN 的解法是**解耦**：全局资源交给 RM，每个作业派一个 AM 管自己的任务，单机交给 NM；资源统一抽象成 `Container`，任何计算框架都能用。

## 架构角色

| 角色 | 职责 | 关键点 |
| --- | --- | --- |
| **ResourceManager** | 全局资源仲裁、应用准入、AM 生命周期 | 由 Scheduler + ApplicationsManager 组成 |
| **Scheduler** | 按策略把空闲 Container 分给谁 | **不监控任务**，不管失败重试 |
| **ApplicationsManager** | 接收提交、启动 AM、AM 重试、状态记录 | 与 Scheduler 内部配合 |
| **NodeManager** | 单机代理：启停容器、资源本地化、心跳、健康检查 | 汇报内存/vcore/磁盘 |
| **ApplicationMaster** | 每应用一个，向 RM 申请资源、决定任务怎么跑 | MR 的是 `MRAppMaster` |
| **Container** | 资源抽象：若干 MB 内存 + 若干 vcore | **不是 Docker**，是 NM 上的进程 + cgroup 约束 |
| **ResourceRequest** | AM 的申请单：资源量、优先级、本地性、可否放宽 | 可写成 host → rack → ANY 三级 |
| **Allocation** | RM 每次心跳返回的分配结果 | AM 据此去 NM 起容器 |

**心跳与状态**：NM 默认每 1 秒向 RM 汇报资源与容器状态；超过 `yarn.nm.liveness-monitor.expiry-interval-ms`（默认 10 分钟）没心跳，RM 判其 LOST。NM 状态机为 `NEW → RUNNING → UNHEALTHY / DECOMMISSIONING → DECOMMISSIONED → SHUTDOWN`；UNHEALTHY 时不再接新容器，已运行的容器可以继续。

## 一次作业的完整链路

以 `hadoop jar hadoop-mapreduce-examples.jar wordcount /in /out` 为例：

1. **提交**：客户端向 RM 的 ClientRMService 提交 ApplicationSubmissionContext（jar、命令、队列、资源）。
2. **准入**：RM 校验队列、ACL、资源，生成 `application_xxx`，向 Scheduler 申请一个 AM 容器。
3. **拿容器**：Scheduler 在某个 NM 上分配容器，RM 在响应里返回容器信息。
4. **起 AM**：客户端直接连该 NM 发 ContainerLaunchContext；NM 本地化 jar 与配置，启动 AM。
5. **注册**：AM 向 RM 注册并心跳；RM 的 ApplicationsManager 开始跟踪该应用。
6. **申请资源**：AM 按分片数生成 ResourceRequest（N 个 map、M 个 reduce）发给 RM。
7. **分配**：Scheduler 按队列策略分配，AM 在心跳响应里拿到 Allocation。
8. **起任务**：AM 通知 NM；NM 在 `local-dirs` 隔离目录下启动 `YarnChild` JVM。
9. **执行汇报**：map → spill → shuffle → reduce → 写 HDFS；进度、计数器经 AM 回传 RM。
10. **清理**：AM 注销，RM 标记 FINISHED，NM 清理目录，日志聚合归档。

## 调度器对比

| | FIFO | CapacityScheduler | FairScheduler |
| --- | --- | --- | --- |
| 分配方式 | 单队列先来先得 | 多队列，**capacity 保证 + max-capacity 上限** | 按 **weight** 公平分配 |
| 隔离性 | 无 | 强，适合多租户 | 较强 |
| 弹性 | 无 | 空闲时可借用，上限到 max-capacity | 空闲资源自动分给需要者 |
| 抢占 | 无 | 可开关 | 默认开启 |
| 默认 | 否 | **Hadoop 3.x 默认** | 否 |
| 适用 | 小集群、测试 | 多部门共享、SLA 明确 | 批任务 + 交互式混跑 |

```xml
<property><name>yarn.resourcemanager.scheduler.class</name>
  <value>org.apache.hadoop.yarn.server.resourcemanager.scheduler.capacity.CapacityScheduler</value></property>
```

CapacityScheduler 的队列是**树形**的，同级 capacity 之和必须为 100：

```xml
<property><name>yarn.scheduler.capacity.root.queues</name><value>prod,dev</value></property>
<property><name>yarn.scheduler.capacity.root.prod.capacity</name><value>70</value></property><property><name>yarn.scheduler.capacity.root.prod.maximum-capacity</name><value>100</value></property>
<property><name>yarn.scheduler.capacity.root.dev.capacity</name><value>30</value></property><property><name>yarn.scheduler.capacity.root.dev.maximum-capacity</name><value>60</value></property>
<property><name>yarn.scheduler.capacity.root.dev.maximum-am-resource-percent</name><value>0.2</value></property>
```

- `capacity` 是**保证份额**，`maximum-capacity` 是**借用上限**，默认 100。
- `yarn.scheduler.capacity.maximum-am-resource-percent` 默认 **0.1**：队列最多 10% 资源跑 AM，作业排队但 AM 起不来先看它。
- 单用户默认受 `user-limit-factor=1.0` 约束，防一个人吃满队列。
- 抢占开关：`yarn.scheduler.capacity.<queue>.disable_preemption`，默认 false。
- 资源计算器默认 `DefaultResourceCalculator`（**只看内存**）；要按 vcore 调度必须换 `DominantResourceCalculator`。

**口诀：多租户硬隔离选 Capacity，批流混跑、资源共享选 Fair。**

## 资源配置与计算

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `yarn.nodemanager.resource.memory-mb` | **8192** | 节点可分配给容器的总内存 |
| `yarn.nodemanager.resource.cpu-vcores` | **8** | 节点可分配 vcore 数 |
| `yarn.scheduler.minimum-allocation-mb` | **1024** | 单容器最小内存，小于按 1024 算 |
| `yarn.scheduler.maximum-allocation-mb` | **8192** | 单容器最大内存 |
| `yarn.scheduler.minimum-allocation-vcores` | 1 | 单容器最小 vcore |
| `yarn.scheduler.maximum-allocation-vcores` | 4 | 单容器最大 vcore |

**64GB / 16 核节点预算示例**：

| 项目 | 大小 | 说明 |
| --- | --- | --- |
| 物理内存 | 65536 MB | 64GB |
| OS + 系统服务 | 8192 MB | page cache、sshd、监控 agent、预留 |
| DataNode 堆 | 4096 MB | 块扫描与传输 |
| NodeManager 自身 | 2048 MB | JVM + 本地化开销 |
| **可分配 `memory-mb`** | **51200 MB** | 65536 − 8192 − 4096 − 2048 |
| **可分配 `cpu-vcores`** | **16** | 1 物理核 ≈ 1 vcore |

容器编排：4GB/1vcore × 12 = 48GB/12vcore，留 3.2GB 余量；或 8GB/2vcore × 6 = 48GB/12vcore。AM 预算 = 51200 × 0.1 = 5120MB，按 1–2GB 一个 AM，同时只能跑 2–5 个应用的 AM。

```xml
<property><name>yarn.nodemanager.resource.memory-mb</name><value>51200</value></property><property><name>yarn.nodemanager.resource.cpu-vcores</name><value>16</value></property>
<property><name>yarn.scheduler.minimum-allocation-mb</name><value>1024</value></property><property><name>yarn.scheduler.maximum-allocation-mb</name><value>8192</value></property>
<property><name>yarn.scheduler.capacity.maximum-am-resource-percent</name><value>0.1</value></property><property><name>yarn.nodemanager.local-dirs</name><value>/data/yarn/local</value></property>
```

## 超配与隔离：容器为什么会死

| 死法 | 日志特征 | 根因 |
| --- | --- | --- |
| 物理内存超限 | `Container [pid] is running beyond physical memory limits` | RSS 超过 `memory-mb`，`pmem-check-enabled=true`（默认）触发 |
| 虚拟内存超限 | `beyond virtual memory limits` | 堆外 + 线程栈 + mmap 让 VIRT 远超堆，默认 `vmem-pmem-ratio=2.1` |
| 被调度器杀 | `Container killed on request. Exit code is 143` | 作业被 kill、抢占、节点退役、AM 释放 |
| JVM 自己 OOM | `Exit code is 137` / `Java heap space` | 容器内存给少了，或代码泄漏 |

- **不要关 pmem-check 来解决 OOM**，那只是把问题推给 OS；应按实际用量调容器内存。
- 硬隔离靠 cgroup：`yarn.nodemanager.linux-container-executor.cgroups.hierarchy`、`...resource.memory.enabled`、`...resource.cpu.enabled`；不开 cgroup 只能事后杀。
- 内存超配会让多个容器同时涨内存，最后被 OS OOM killer 带走，节点直接失联。

## Node Labels 与队列映射

**Node Labels** 解决异构机器问题：GPU、大内存机器单独打标签，队列只能落在指定标签的节点上。

```bash
# yarn-site.xml: yarn.node-labels.enabled=true
#                yarn.node-labels.fs-store.root-dir=/share/hadoop/yarn/node-labels
yarn rmadmin -addToClusterNodeLabels "gpu(exclusive=false)"
yarn rmadmin -replaceNodeLabels -labels gpu node05
yarn node -list -label gpu
```

```xml
<property><name>yarn.scheduler.capacity.root.ml.accessible-node-labels</name><value>gpu</value></property><property><name>yarn.scheduler.capacity.root.ml.accessible-node-labels.gpu.capacity</name><value>100</value></property>
<property><name>yarn.scheduler.capacity.root.ml.default-node-label-expression</name><value>gpu</value></property>
```

**队列映射**让用户提交时自动落到对应队列：

```xml
<property><name>yarn.scheduler.capacity.queue-mappings</name><value>u:alice:dev,g:data:prod,g:%primary_group:default</value></property>
<property><name>yarn.scheduler.capacity.queue-mappings-override.enable</name><value>false</value></property>
```

格式为 `u:用户:队列` / `g:组:队列`，支持 `%primary_group`；`override.enable=false` 表示用户显式 `--queue` 优先。

## 日志聚合与历史服务

| 组件 | 作用 | 关键配置 | 端口 |
| --- | --- | --- | --- |
| **日志聚合** | 容器结束后把 userlogs 传到 HDFS，不用逐台机器找日志 | `yarn.log-aggregation-enable=true`、`yarn.nodemanager.remote-app-log-dir=/tmp/logs` | — |
| **JobHistoryServer** | 存 MR 作业历史：配置、计数器、task 记录 | `mapreduce.jobhistory.address=host:10020`、`mapreduce.jobhistory.webapp.address=host:19888` | 10020 / 19888 |
| **Timeline Server v2** | 存应用/容器/任务的通用时序事件 | `yarn.timeline-service.version=2.0`、`yarn.timeline-service.enabled=true` | 8188 |

```bash
yarn logs -applicationId application_1690000000000_0001
mapred --daemon start historyserver
```

## 常见故障速查

| 现象 | 可能原因 | 处理 |
| --- | --- | --- |
| 应用一直 ACCEPTED | 队列资源不足 / AM 百分比到顶 / 队列停用 | 看 RM UI Queue 页，调 capacity 或 `maximum-am-resource-percent` |
| AM 连续失败至 FAILED | AM 命令错、jar 丢失、AM 内存不足、节点坏 | `yarn appattempts` 看 diagnostics，再 `yarn logs` |
| `Container killed on request. Exit code is 143` | 作业被 kill、抢占、节点退役 | 确认是谁发的 kill，是否 preemption |
| `beyond physical memory limits` | 容器内存小于实际用量 | 提高容器内存或降并发，别直接关检查 |
| 内存够但容器起不来 | vcore 耗尽 / 资源计算器只看内存 | 换 `DominantResourceCalculator`，vcores 按物理核数设 |
| NM 状态 UNHEALTHY | local-dirs 不可写、磁盘满、健康检查失败 | `yarn node -list -states UNHEALTHY`，看 NM 日志 `DiskChecker` |

## 自测

1. 64GB / 16 核节点，OS 与系统服务占 8GB、DN 堆 4GB、NM 2GB，`memory-mb` 设多少？单容器 8GB 时最多几个？
2. RM 的 Scheduler 和 AM 各负责什么？为什么「Scheduler 不做监控」是设计优点？
3. 应用卡在 ACCEPTED，按什么顺序排查？至少说出三个可能原因。
4. `capacity` 与 `maximum-capacity` 有什么区别？什么场景会触发抢占？

## 参考与官方文档

- [YARN 官方总览](https://hadoop.apache.org/docs/stable/hadoop-yarn/hadoop-yarn-site/YARN.html)
- [CapacityScheduler 配置](https://hadoop.apache.org/docs/stable/hadoop-yarn/hadoop-yarn-site/CapacityScheduler.html)
- [FairScheduler 配置](https://hadoop.apache.org/docs/stable/hadoop-yarn/hadoop-yarn-site/FairScheduler.html)
- [Node Labels 使用](https://hadoop.apache.org/docs/stable/hadoop-yarn/hadoop-yarn-site/NodeLabel.html)
- [Timeline Service v2](https://hadoop.apache.org/docs/stable/hadoop-yarn/hadoop-yarn-site/TimelineServiceV2.html)
- [yarn-default.xml 默认值全表](https://hadoop.apache.org/docs/stable/hadoop-yarn/hadoop-yarn-common/yarn-default.xml)
