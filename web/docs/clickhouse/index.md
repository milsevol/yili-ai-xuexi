# ClickHouse

ClickHouse 是列式 OLAP 数据库：**向量化执行 + 列存压缩 + MergeTree 引擎家族**，实时聚合查询比 Hive/Spark 快 10-100 倍。不适合 OLTP 场景，但实时看板、用户行为分析、日志分析是它的主场。本主题用中文笔记 + **浏览器可视化交互演示**，梳理「是什么 → 怎么存 → 怎么加速 → 怎么分布式 → 怎么物化 → 怎么调优」的完整链路。

> 版本参考：ClickHouse 24.x / 25.x。演示不连接真实集群；默认打开 `demos/index.html`。

## 先决知识

- SQL 基础（WHERE、JOIN、GROUP BY、聚合函数）
- Hive 或 Spark SQL 经验更佳（理解列式 vs 行存、分区概念）
- 理解 SIMD / 向量化执行是什么更佳

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位) | `./start.sh 01` | ClickHouse vs Hive vs Spark SQL vs Doris |
| 2 | [02-架构与核心组件](./notes/02-架构与核心组件) | `./start.sh 02` | Part/Marks 存储结构、写入→Merge 流程 |
| 3 | [03-MergeTree 引擎家族](./notes/03-MergeTree引擎家族) | `./start.sh 03` | 六种 MergeTree 引擎选择器 |
| 4 | [04-数据类型与 SQL](./notes/04-数据类型与SQL) | `./start.sh 04` | 数据类型选择器、Nullable 坑警告 |
| 5 | [05-分区排序与索引](./notes/05-分区排序与索引) | `./start.sh 05` | 分区策略 + 跳数索引效果可视化 |
| 6 | [06-向量化执行与查询原理](./notes/06-向量化执行与查询原理) | `./start.sh 06` | 列式 vs 行式执行对比 + SIMD 加速 |
| 7 | [07-分布式与集群](./notes/07-分布式与集群) | `./start.sh 07` | Distributed 引擎路由 + Replica 同步 |
| 8 | [08-物化视图与 CDC](./notes/08-物化视图与CDC) | `./start.sh 08` | 实时聚合加速模拟 + TTL 过期 |
| 9 | [09-性能调优与实践](./notes/09-性能调优与实践) | `./start.sh 09` | 写入/查询/Merge/TTL 排障决策树 |
| 10 | [10-生态对比与 FAQ](./notes/10-生态对比与FAQ) | `./start.sh 10` | ClickHouse vs Doris vs StarRocks + 面试 FAQ |

## 如何启动演示

```bash
cd notes/clickhouse
./start.sh          # 浏览器可视化交互
./start.sh 03       # 直达 MergeTree 引擎选择器
./start.sh --cli    # 备用终端文字版
```

也可：`python3 main.py clickhouse` / `python3 main.py clickhouse 03`。

## 参考与官方文档

- [ClickHouse 官方文档](https://clickhouse.com/docs/)
- [ClickHouse 架构概览](https://clickhouse.com/docs/en/guides/sre/architecture)
- [MergeTree 引擎](https://clickhouse.com/docs/en/engines/table-engines/mergetree-family/)
- [GitHub](https://github.com/ClickHouse/ClickHouse)
