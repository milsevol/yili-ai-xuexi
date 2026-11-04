# 10-生态对比与FAQ

## 一句话

ClickHouse 在 OLAP 赛道上的直接对手是 Apache Doris / StarRocks（兼容 MySQL 协议、有事务）、Trino（交互式查询联邦引擎）、TiDB（HTAP 兼顾 OLTP+OLAP）、HBase（列式 KV）。选型时看：有没有事务需求？有没有复杂 JOIN？团队熟悉度？查询延迟要求？——没有银弹，只有最匹配。

## ClickHouse vs 主要对手

### ClickHouse vs Doris vs StarRocks

这三个是**列式 OLAP 同赛道**，但架构路径不同：

| 维度 | ClickHouse | Apache Doris | StarRocks |
| --- | --- | --- | --- |
| **架构** | 单 Server 对等（无 Master/Worker 区分） | FE（元数据+调度）+ BE（存储+计算） | FE + BE（基于 Doris 分支） |
| **协议** | Native + HTTP + MySQL 协议兼容 | ✅ MySQL 协议原生 | ✅ MySQL 协议原生 |
| **事务** | ❌ 无 ACID（MergeTree 最终一致） | ✅ 支持 2PC 事务 | ✅ 支持 2PC 事务 |
| **复杂 JOIN** | ⚠️ 较弱，大表 JOIN 性能差 | ✅ 强（CBO + 动态分区） | ✅ 强（CBO + 动态分区） |
| **向量化** | ✅ 优秀（SIMD 极致） | ✅ 优秀 | ✅ 优秀 |
| **物化视图** | ✅ 强（实时聚合） | ✅ 强（异步刷新） | ✅ 强（异步刷新） |
| **冷热分离** | 需配合 S3/HDFS 引擎 | ✅ 内置（Native + S3） | ✅ 内置 |
| **湖仓兼容** | ⚠️ 有限（Iceberg/Hudi 引擎） | ✅ 强（Iceberg + Hudi） | ✅ 强 |
| **运维复杂度** | 低（对等架构，无 Master） | 中（FE/BE 双角色） | 中 |
| **适用场景** | 纯实时看板、ADAS 层、指标系统 | 企业级 BI、全链路数仓、复杂 JOIN | 同上 |
| **社区** | Yandex → 全球，国内字节/快手重度用户 | Apache 顶级项目，国内腾讯推广 | 字节开源，国内活跃 |

**选型口诀**：
- ✅ **ClickHouse**：只做 ADS/报表层、团队不想维护 Master、追求极致简单
- ✅ **Doris / StarRocks**：需要事务、需要 MySQL 协议、有复杂多表 JOIN

### ClickHouse vs Trino

| 维度 | ClickHouse | Trino (Presto 分支) |
| --- | --- | --- |
| **定位** | OLAP 数据库（存+算一体） | 查询引擎（联邦查询） |
| **存储** | MergeTree（本地列存） | 外部存储（HDFS/S3/Hive Metastore） |
| **延迟** | 毫秒~秒级 | 亚秒级~秒级 |
| **多数据源** | 有限引擎（MySQL/Kafka/S3） | ✅ 30+ 数据源联邦查询 |
| **写入** | ✅ 原生写入 + Merge | ❌ 只读（查询外部表） |
| **分布式** | MergeTree 天然分布式 | 原生 Coordinator/Worker |

**互补关系**：Trino 可以把 ClickHouse 作为一个数据源查询（`connector=clickhouse`）。很多公司用 Trino 做统一查询入口、ClickHouse 做高性能 ADS 层。

### ClickHouse vs TiDB

| 维度 | ClickHouse | TiDB |
| --- | --- | --- |
| **定位** | 纯 OLAP | HTAP（OLTP + OLAP 兼顾） |
| **事务** | ❌ | ✅ ACID 强事务 |
| **查询模式** | 大规模聚合 | 点查 + 小范围读 + 聚合 |
| **架构** | MergeTree 列存 | TiKV（RocksDB 行存）+ TiFlash（列存） |
| **适用** | 报表、看板 | 在线业务库 + 轻量分析 |

**选型**：如果同一个业务表既要高并发点查（OLTP）又要大规模聚合（OLAP）→ TiDB。如果纯分析 → ClickHouse。

### ClickHouse vs HBase

| 维度 | ClickHouse | HBase |
| --- | --- | --- |
| **存储模型** | 列式 MergeTree | 列式 KV（LSM-Tree） |
| **查询** | SQL 聚合 | 点查 / Scan（无 SQL） |
| **适用** | 聚合分析 | 高并发点查 |
| **依赖** | Keeper（可选） | ZooKeeper（强依赖） |
| **写入** | 批量 append | 单行 / 批量 put |

**选型**：HBase 做在线业务点查，ClickHouse 做离线/近线聚合分析。两者完全互补。

### 全景选型图

```
业务需求:
├─ 需要 OLTP 事务？
│   ├─ Yes → MySQL / TiDB (HTAP)
│   └─ No
│
├─ 需要大规模聚合查询？
│   ├─ Yes
│   │   ├─ 需要高并发写入 + 实时看板 → ClickHouse
│   │   ├─ 需要事务 + 复杂 JOIN → Doris / StarRocks
│   │   ├─ 需要多数据源联邦 → Trino + ClickHouse (后端)
│   │   └─ 需要长链路 ETL + 湖仓 → Spark + Hive Metastore + Iceberg
│   └─ No
│
├─ 需要高频点查（PK 定位）？
│   ├─ Yes → Redis / HBase / TiKV
│   └─ No
│
└─ 需要实时流处理？
    ├─ Yes → Flink + Kafka + ClickHouse Sink
    └─ No → Hive on Spark (离线 ETL)
```

## ClickHouse on K8s

### 为什么需要 K8s 部署

生产环境 ClickHouse 集群规模通常在 3–50 节点。K8s 提供：
- 自动扩缩容（根据 CPU/内存/Pod 数量）
- 滚动升级（零停机）
- 容器化隔离
- 云原生存储集成（云盘 / PV）

### 部署模式

| 模式 | 说明 | 适用 |
| --- | --- | --- |
| **单节点 StatefulSet** | 开发测试 | 学习、测试 |
| **多 Shard StatefulSet** | 1 StatefulSet 对应 1 Shard | 生产（最常见） |
| **ClickHouse Operator** | 官方 Operator 自动化集群管理 | 大规模生产 |

### Operator 示例（简化）

```yaml
# clickhouse-operator CR
apiVersion: clickhouse.altinity.com/v1
kind: ClickHouseInstallation
metadata:
  name: clickhouse-production
spec:
  configuration:
    clusters:
      - name: production
        shardsCount: 3
        replicasCount: 2
  templates:
    podTemplates:
      - name: clickhouse-server
        spec:
          containers:
            - name: clickhouse
              image: clickhouse/clickhouse-server:24.12
              resources:
                requests:
                  cpu: '4'
                  memory: 16Gi
                limits:
                  cpu: '8'
                  memory: 32Gi
          volumeMounts:
            - name: clickhouse-data
              mountPath: /var/lib/clickhouse
    volumeClaimTemplates:
      - name: clickhouse-data
        spec:
          accessModes: ['ReadWriteOnce']
          resources:
            requests:
              storage: 500Gi
```

### K8s 部署注意事项

| 注意点 | 说明 |
| --- | --- |
| **SSD 存储** | ClickHouse 极依赖磁盘 IO，必须用云 SSD（不要用标准 HDD） |
| **网络** | 跨 Pod 网络延迟影响分布式查询，尽量同 AZ 部署 |
| **Keeper 独立** | Keeper 建议独立 StatefulSet + 持久化存储 |
| **自动扩缩容** | ClickHouse Shard 扩容需要数据 Rebalance，复杂！**尽量预规划 Shard 数** |
| **备份恢复** | K8s 里用 S3 备份 ClickHouse 数据 |

## 湖仓兼容：Iceberg / Hudi

ClickHouse 22.x+ 提供 Iceberg / Hudi / Delta Lake 引擎，可以直接查询湖仓表格式：

```sql
-- 查询 Iceberg 表（无需导入到 ClickHouse）
CREATE TABLE iceberg_orders ENGINE = Iceberg('hdfs://hive-warehouse/orders', ...);

-- 查询 Hudi 表
CREATE TABLE hudi_events ENGINE = Hudi('s3://lake/events', ...);

-- 查询 Delta Lake 表
CREATE TABLE delta_products ENGINE = DeltaLake('hdfs://warehouse/products');
```

| 引擎 | 优势 | 劣势 | 推荐场景 |
| --- | --- | --- | --- |
| **Hive Engine** | 直接查询 HDFS/S3 上 Hive Metastore 表 | 无列存压缩、无 SIMD | 临时查 Hive 表、不常访问 |
| **Iceberg Engine** | 查询 Iceberg 表格式，支持快照时间旅行 | 依赖 Hive Metastore | 湖仓表需要高性能查询时 |
| **S3 Engine** | 直接查 S3 上 Parquet/CSV/JSON | 无缓存、性能依赖网络 | 冷数据临时查询 |
| **MySQL Engine** | 直连 MySQL 查小表 | 实时性差、无缓存 | 字典表 JOIN、偶尔查 MySQL |

**生产常见组合**：Spark/Flink 写 Iceberg 表到 S3 → ClickHouse 通过 Iceberg Engine 高性能查询同一份数据。

## 常见面试题

### Q1：ClickHouse 为什么那么快？

**答**：三个层面：
1. **列式存储**：IO 只读需要的列（减少 90%+），同类型数据天然高压缩（10–20x LZ4）
2. **SIMD 向量化执行**：CPU 向量指令一次处理 64–256 行，批量计算比逐行快 5–10x
3. **MergeTree 有序合并**：数据按 ORDER BY 存储，主索引 Mark 稀疏定位，跳数索引跳过无关 Part

### Q2：ClickHouse 的 MergeTree 的 PARTITION BY 和 ORDER BY 有什么区别？

**答**：PARTITION BY 决定磁盘目录划分（一级过滤），ORDER BY 决定分区内数据物理顺序和主索引精度。PARTITION BY 通常用时间字段（方便裁剪 + TTL 过期），ORDER BY 用查询最常过滤的字段（user_id、city 等）。ORDER BY 必填，PARTITION BY 可选（空分区）。

### Q3：ClickHouse 分布式集群的写入流程？为什么推荐业务层直连本地表？

**答**：
- 写入流程：① 业务层根据分片键路由到对应节点 ② 直接 INSERT 本地 MergeTree 表 ③ 后台 Merge 合并 ④ ReplicatedMergeTree 通过 Keeper 同步副本
- 为什么直连本地：Distributed 引擎写入多一跳网络、单点瓶颈、失败影响全局。业务层路由直接写本地，所有节点均衡承载。

### Q4：ClickHouse 的 UPDATE/DELETE 怎么实现？为什么不推荐大量使用？

**答**：ALERT UPDATE/DELETE 底层是**重写所有 Part**（Mutation 机制）。每次 Mutation 需要读取、过滤、重写整个表数据。大量 Mutation 会让 Merge 队列爆、查询变慢。推荐替代方案：ReplacingMergeTree + 写入新行、Partition DROP 代替 DELETE、TTL 自动过期。

### Q5：ClickHouse 和 Hive / Spark SQL 怎么配合？

**答**：典型组合：
- **Hive on Spark**：做 ETL（长链路、多表 JOIN、事务），数据落到 HDFS / Iceberg
- **ClickHouse**：写入清洗后的数据做 ADS 层，供实时看板 / BI 报表查询
- **Flink CDC**：MySQL 实时变更 → Kafka → ClickHouse 物化视图入仓
- **Trino**：统一查询入口，后端接 Hive + ClickHouse 多个数据源

### Q6：ReplacingMergeTree 的去重什么时候生效？FINAL 关键字是什么？

**答**：ReplacingMergeTree 去重只在**后台 Merge 时**生效——相同 ORDER BY 键的多行合并成一行。刚 INSERT 的重复数据可能还在。FINAL 关键字强制查询时触发实时合并去重（极慢！大表不可用）。生产应该依赖后台 Merge 自然去重，不用 FINAL。

### Q7：ClickHouse 的跳数索引有哪几种？分别适合什么查询？

**答**：
- **minmax**：每个 Part 记录列 MIN/MAX → 适合 `amount BETWEEN` 范围查询
- **set(N)**：每个 Part 记录列的 N 个不同值 → 适合 `user_id IN (1, 2, 3)` 等值查询
- **bloom_filter**：每个 Part 生成 BF → 适合字符串/低基数字段 `city = '北京'` 等值查询
- **ngrambf_v1**：N-Gram BF → 适合 LIKE '%xxx%' 模糊查询

### Q8：ClickHouse 怎么处理高并发写入（每秒 10 万+）？

**答**：
1. **AsyncInsert 异步写入**：多个微批次自动合并刷盘，减少 Part 数量
2. **Kafka 引擎 + 物化视图**：Kafka 做缓冲层，ClickHouse 后台批量消费
3. **分布式多节点写入**：业务层按分片键路由到各节点本地表
4. **调大 max_insert_block_size**：单 Part 数据量上限提高
5. **监控 Part 数**：保持单表 Part 数 < 1000，过多加速 Merge

### Q9：ClickHouse 的分布式查询怎么实现的？

**答**：Distributed 引擎是代理层。查询时 ClickHouse 并发把相同 SQL 下发到集群所有分片的本地表 → 每个节点做本地 MergeTree 执行（分区裁剪 + SIMD 聚合）→ 结果返回 Coordinator 节点二次聚合（GROUP BY + 合并结果）→ 返回给用户。

### Q10：ClickHouse 有事务吗？怎么保证数据一致性？

**答**：ClickHouse **没有完整 ACID 事务**。它的一致性靠两个层面：
1. **MergeTree 写入**：append-only + Merge 最终一致，写入不会看到半写数据
2. **ReplicatedMergeTree + Keeper**：副本间异步同步，Keeper 协调 Part 编号避免冲突
3. **写入幂等性**：相同批次（同一 INSERT block）可以重试不重复

需要强事务的场景用 Doris / StarRocks 或 TiDB。

## 参考与官方链接

- [ClickHouse vs Doris（官方博客对比）](https://clickhouse.com/blog/clickhouse-vs-doris)
- [ClickHouse Operator（Altinity）](https://github.com/Altinity/clickhouse-operator)
- [ClickHouse on K8s 部署指南](https://clickhouse.com/docs/en/guides/sre/kubernetes)
- [Iceberg Engine](https://clickhouse.com/docs/en/engines/table-engines/integrations/iceberg)
- [湖仓一体生态对比](https://clickhouse.com/blog/clickhouse-data-lake)
- [ClickHouse 面试题集合（知乎）](https://www.zhihu.com/question/539279673)
