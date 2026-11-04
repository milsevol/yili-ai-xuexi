# Apache Hive

Apache Hive 是建立在 HDFS 之上的数仓 SQL 层：把 SQL 翻译成 MapReduce / Tez / Spark 任务来跑。核心价值是 **统一的 Metastore 元数据中心** 和 **数仓分层建模**（ODS→DWD→DWS→ADS）。本主题用中文笔记 + **浏览器可视化交互演示**，梳理「是什么 → 怎么建表 → 怎么分层 → 怎么调引擎 → 怎么保证 ACID → 怎么和湖仓配合」的完整链路。

> 版本参考：Hive 3.1 / 4.0。演示不连接真实集群；默认打开 `demos/index.html`。

## 先决知识

- HDFS 基本概念（块、副本）
- YARN 基本概念（可选，Hive on MR/Tez 需要）
- 传统关系型数据库 SQL 基础（WHERE、JOIN、GROUP BY）

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位) | `./start.sh 01` | Hive vs Spark SQL vs Trino、大数据链路位置 |
| 2 | [02-架构与核心组件](./notes/02-架构与核心组件) | `./start.sh 02` | HiveServer2/Metastore/Driver、查询链路 |
| 3 | [03-数据模型与存储格式](./notes/03-数据模型与存储格式) | `./start.sh 03` | ORC vs Parquet vs TextFile、SerDe、内部/外部表 |
| 4 | [04-SQL 与分区管理](./notes/04-SQL与分区管理) | `./start.sh 04` | 分区裁剪可视化、静态/动态分区 |
| 5 | [05-数仓分层设计](./notes/05-数仓分层设计) | `./start.sh 05` | ODS→DWD→DWS→ADS 四层流转、维度建模 |
| 6 | [06-执行引擎与 Tez/Spark 切换](./notes/06-执行引擎与TezSpark切换) | `./start.sh 06` | MR vs Tez vs Spark vs Flink DAG 对比 |
| 7 | [07-性能调优](./notes/07-性能调优) | `./start.sh 07` | MapJoin 场景选择器、CBO 开关、倾斜处理 |
| 8 | [08-ACID 与事务](./notes/08-ACID与事务) | `./start.sh 08` | MERGE/UPDATE/DELETE、Compaction 模拟 |
| 9 | [09-Hive 与周边组件](./notes/09-Hive与周边组件) | `./start.sh 09` | Metastore 作为通用元数据中心的连接关系 |
| 10 | [10-生态对比与 FAQ](./notes/10-生态对比与FAQ) | `./start.sh 10` | Hive vs Spark SQL vs Trino vs ClickHouse + 面试 FAQ |

## 如何启动演示

```bash
cd notes/hive
./start.sh          # 浏览器可视化交互
./start.sh 05       # 直达数仓分层流转图
./start.sh --cli    # 备用终端文字版
```

也可：`python3 main.py hive` / `python3 main.py hive 05`。

## 参考与官方文档

- [Hive 3.1 官方文档](https://cwiki.apache.org/confluence/display/Hive/Home)
- [Hive 4.0 官方文档](https://hive.apache.org/)
- [GitHub](https://github.com/apache/hive)
