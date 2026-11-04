# ClickHouse

ClickHouse 是一个**列式 OLAP（在线分析处理）数据库**，核心是 **MergeTree 引擎家族**、**向量化执行**、**分布式并行**。它从 Yandex 内部诞生，最初为了支撑超大规模用户行为日志分析，现在被全球电商、广告、金融、物联网公司用来做**实时看板、用户行为分析、日志分析、指标系统**。

ClickHouse 的核心优势是「**快**」——同量级数据、同复杂度查询，通常比 Hive / Spark SQL / Trino 快 5–100 倍。原因很朴素：列式存储压缩率高、SIMD 指令批量运算、无锁异步 IO、MergeTree 引擎天然有序。但它不是银弹——不支持完整事务、不擅长复杂 JOIN、不适合高频点查。它和 Hive / Spark / Flink 是互补关系：**Hive 做离线 ETL，Flink 做实时入仓，ClickHouse 做查询加速层（ADS / 报表层）**。

本主题用中文笔记梳理「是什么 → 怎么存 → 怎么查 → 怎么分布式 → 怎么物化视图 → 怎么调优 → 怎么选型」的完整链路。

> 版本参考：以 **ClickHouse 24.x / 25.x** 为准，示例以 clickhouse-client（HTTP / Native 协议）、MergeTree 引擎、DDL/DML/SQL 为主。配套**浏览器可视化交互演示**：MergeTree 引擎选择器、Part/Marks 存储结构、向量化执行动画、分布式路由图、物化视图加速模拟、性能调优决策树等，打开 `demos/index.html` 即玩，无需集群。

## 先决知识

- 会一点 SQL（SELECT / JOIN / GROUP BY / CTE）
- 知道 Hive 或 Spark SQL 会帮助理解「OLAP 查询」这件事
- 知道列式存储 vs 行式存储的基本区别更佳

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位.md) | `./start.sh 01` | ClickHouse 本质；vs Hive vs Spark SQL vs Trino vs Doris；为什么那么快 |
| 2 | [02-架构与核心组件](./notes/02-架构与核心组件.md) | `./start.sh 02` | Server 节点；Part / Marks 存储结构；写入→Merge 后台流程；Distributed 引擎 |
| 3 | [03-MergeTree引擎家族](./notes/03-MergeTree引擎家族.md) | `./start.sh 03` | MergeTree 基类；Replacing / Summing / Aggregating / Collapsing；物化视图关系 |
| 4 | [04-数据类型与SQL](./notes/04-数据类型与SQL.md) | `./start.sh 04` | 数据类型大全；Nullable 的坑；DDL/DML；函数速查；JSON 支持 |
| 5 | [05-分区排序与索引](./notes/05-分区排序与索引.md) | `./start.sh 05` | PARTITION BY 分区策略；ORDER BY 排序键；Marks 稀疏索引；跳数索引；Projections |
| 6 | [06-向量化执行与查询原理](./notes/06-向量化执行与查询原理.md) | `./start.sh 06` | 列式存储 + SIMD；Pipeline vs 非 Pipeline；EXPLAIN 查询计划；优化器 |
| 7 | [07-分布式与集群](./notes/07-分布式与集群.md) | `./start.sh 07` | Distributed 引擎；ReplicatedMergeTree + Keeper 副本；分片策略；集群配置 |
| 8 | [08-物化视图与CDC](./notes/08-物化视图与CDC.md) | `./start.sh 08` | Materialized View 实时聚合；CREATE MATERIALIZED VIEW TO；TTL 过期；Kafka + CDC |
| 9 | [09-性能调优与实践](./notes/09-性能调优与实践.md) | `./start.sh 09` | 写入优化；查询优化；Merge 阻塞排查；Mutation 慢处理；常见报错速查 |
| 10 | [10-生态对比与FAQ](./notes/10-生态对比与FAQ.md) | `./start.sh 10` | ClickHouse vs Doris vs StarRocks vs TiDB vs Trino；湖仓兼容；面试题 |

建议：01–02 建立心智模型（MergeTree 是核心，向量化 + 列存是快的根因）；03–05 是日常主战场（引擎选型、分区排序、索引）；06 理解查询为什么快；07 面向集群部署；08–09 面向实时加速与调优；10 面向选型与面试。

## 如何启动演示

```bash
cd notes/clickhouse
./start.sh          # 打开浏览器交互演示页
./start.sh 02       # 直达第 2 章（架构与核心组件）
./start.sh --cli    # 备用：终端文字摘要
./start.sh --cli 02 # 终端查看第 2 章摘要
```

也可从仓库根进入：`python3 main.py clickhouse`。演示为纯 HTML/JS，无需构建、无需集群。

## 本地快速验证（可选）

ClickHouse 支持单机 server 模式，开箱即用，适合最小体验：

```bash
# macOS（Homebrew）
brew install clickhouse

# Linux（官方二进制）
curl -O https://builds.clickhouse.com/master/amd64/clickhouse
chmod +x clickhouse
sudo ./clickhouse install

# 1) 启动单机 server
clickhouse server

# 2) 另开一个终端，连 client
clickhouse-client

# 3) 最小 SQL 验证
CREATE TABLE t_demo (
  id UInt32,
  name String,
  created DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY id;

INSERT INTO t_demo VALUES (1, 'hello'), (2, 'clickhouse');

SELECT count() FROM t_demo;
```

> 注意：ClickHouse 默认端口 8123（HTTP）+ 9000（Native）+ 9004（MySQL 协议兼容）。生产环境务必配置 `config.xml` 开启 Keeper（或依赖 ZooKeeper）做副本一致性，单机 MergeTree 没有冗余。

## 参考与官方文档

- ClickHouse 官方文档：https://clickhouse.com/docs
- ClickHouse Releases：https://clickhouse.com/docs/en/changelog
- MergeTree 引擎：https://clickhouse.com/docs/en/engines/table-engines/mergetree-family/mergetree
- Distributed 引擎：https://clickhouse.com/docs/en/engines/table-engines/special/distributed
- Materialized View：https://clickhouse.com/docs/en/guides/materialized-views
- ClickHouse Keeper：https://clickhouse.com/docs/en/guides/sre/keeper
- GitHub：https://github.com/ClickHouse/ClickHouse
- Projections：https://clickhouse.com/docs/en/engines/table-engines/mergetree-family/projections
- 跳数索引：https://clickhouse.com/docs/en/engines/table-engines/mergetree-family/mergetree#table_engine-mergetree-covering-index
