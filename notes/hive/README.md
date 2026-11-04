# Apache Hive

Apache Hive 是大数据仓库的 SQL 层：**把 HDFS（或对象存储）上的文件，通过 Metastore 元数据映射成一张张有名字、有列、有类型的「表」，然后用类 SQL（HiveQL）做数仓建模与离线分析**。

从 Hive 3.x 到 4.x，Hive 完成了一次重大架构转型：**Metastore 从 Hive 内部拆出来，成为被 Spark、Flink、Trino 共享的通用元数据中心**，而 Hive 自身回归「SQL 兼容层」——真正执行 SQL 的是 Tez（4.x 默认）、Spark 或 Flink。湖仓表格式（Iceberg/Hudi/Delta）正在取代 Hive 原生 ORC 表，而 Hive Metastore 继续作为连接枢纽。

本主题用中文笔记梳理「是什么 → 怎么存 → 怎么建模 → 怎么调优 → 怎么事务 → 怎么选型」的完整链路。

> 版本参考：以 **Hive 3.1 / 4.0** 为准，示例以 Beeline CLI、XML 配置、HiveQL DDL/DML 为主。配套**浏览器可视化交互演示**：架构角色点击、内部/外部表 DROP 模拟、ORC vs Parquet 对比、数仓四层数据流图、ACID Compaction 效果、MapJoin 场景选择器等，打开 `demos/index.html` 即玩，无需集群。

## 先决知识

- 知道 HDFS 基本概念（块、副本、目录、分区）
- 知道 YARN 基本概念（ResourceManager、Container、队列）
- 会一点 SQL（SELECT / JOIN / GROUP BY / CTE）
- 用过 Spark SQL / Trino 会帮助理解「Hive 是 SQL 兼容层」这件事

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位.md) | `./start.sh 01` | Hive = 文件变表；Hive vs Spark SQL vs Trino；4.x 现状 |
| 2 | [02-架构与核心组件](./notes/02-架构与核心组件.md) | `./start.sh 02` | Client → HS2 → Compiler → Engine；Metastore 三种模式；执行引擎切换 |
| 3 | [03-数据模型与存储格式](./notes/03-数据模型与存储格式.md) | `./start.sh 03` | 内部表 vs 外部表；分区/分桶；ORC vs Parquet vs TextFile；压缩算法 |
| 4 | [04-SQL与分区管理](./notes/04-SQL与分区管理.md) | `./start.sh 04` | DDL/DML 速查；静态/动态分区；分区裁剪；MSCK REPAIR TABLE |
| 5 | [05-数仓分层设计](./notes/05-数仓分层设计.md) | `./start.sh 05` | ODS→DWD→DWS→ADS 四层；拉链表、增量表、快照表；维度建模星型模型 |
| 6 | [06-执行引擎与TezSpark切换](./notes/06-执行引擎与TezSpark切换.md) | `./start.sh 06` | MR vs Tez vs Spark vs Flink 对比；Tez DAG 优势；SET hive.execution.engine |
| 7 | [07-性能调优](./notes/07-性能调优.md) | `./start.sh 07` | 分区裁剪→谓词下推→MapJoin→倾斜处理→CBO→矢量化 |
| 8 | [08-ACID与事务](./notes/08-ACID与事务.md) | `./start.sh 08` | ORC + Bucket + Compaction；MERGE/UPDATE/DELETE；与 Iceberg/Hudi/Delta 对比 |
| 9 | [09-Hive与周边组件](./notes/09-Hive与周边组件.md) | `./start.sh 09` | Hive Metastore 作为通用元数据中心；Spark/Flink/Trino 对接；湖仓表格式 |
| 10 | [10-生态对比与FAQ](./notes/10-生态对比与FAQ.md) | `./start.sh 10` | Hive vs Spark SQL vs Trino vs ClickHouse；Hive 4.0 新特性；湖仓一体影响 |

建议：01–02 建立心智模型（Metastore 是核心，执行引擎可换）；03–04 是日常主战场（表、分区、SQL）；05 是数仓方法论；06–07 面向执行引擎切换与性能调优；08 是 ACID 事务边界；09 面向多引擎共存；10 面向选型与面试。

## 如何启动演示

```bash
cd notes/hive
./start.sh          # 打开浏览器交互演示页
./start.sh 02       # 直达第 2 章（架构与核心组件）
./start.sh --cli    # 备用：终端文字摘要
./start.sh --cli 02 # 终端查看第 2 章摘要
```

也可从仓库根进入：`python3 main.py hive`。演示为纯 HTML/JS，无需构建、无需集群。

## 本地快速验证（可选）

Hive 支持单机 embedded 模式（Derby 内嵌 Metastore），适合最小体验。需要 Linux/macOS、JDK 8/11、已配置好 Hadoop 伪分布式或本地 HDFS。只想验证 SQL 可用时，也可以直接用 Hive 自带的 `bin/schematool` 初始化 Schema：

```bash
# 示例思路，版本以 4.0+ 为准
tar -xzf apache-hive-4.0.0-bin.tar.gz
export HADOOP_HOME=/path/to/hadoop
export HIVE_HOME=/path/to/apache-hive-4.0.0-bin

# 1) 初始化 Derby Schema（首次运行）
$HIVE_HOME/bin/schematool -initSchema -dbType derby

# 2) 启动 HiveServer2（embedded 模式）
$HIVE_HOME/bin/hiveserver2 &

# 3) Beeline 连接
$HIVE_HOME/bin/beeline -u jdbc:hive2://localhost:10000 -n root -d

# 4) 最小 SQL 验证
CREATE TABLE t_demo (id INT, name STRING)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
STORED AS TEXTFILE;
INSERT INTO TABLE t_demo VALUES (1, 'hello'), (2, 'hive');
SELECT * FROM t_demo;
```

> 注意：Hive 4.x 官方支持 JDK 8/11，更高版本需自行验证。生产环境务必把 Metastore 从内嵌 Derby 切到 MySQL/PostgreSQL 远程模式（端口 9083），让 Spark、Flink、Trino 能直接共享。

## 参考与官方文档

- Hive 4.0 Release Notes：https://cwiki.apache.org/confluence/display/hive/Hive4NewFeatures
- Hive Language Manual：https://cwiki.apache.org/confluence/display/hive/languagemanual
- Hive Metastore 设计：https://cwiki.apache.org/confluence/display/hive/designofhivemetastore
- Hive on Tez：https://cwiki.apache.org/confluence/display/Hive/Hive+on+Tez
- Hive on Spark：https://cwiki.apache.org/confluence/display/Hive/Hive+on+Spark%3A+Getting+Started
- ORC File Format：https://orc.apache.org/docs/
- Apache Tez：https://tez.apache.org/
- 数仓分层经典：《数据仓库工具箱》（Ralph Kimball，维度建模）
- GitHub：https://github.com/apache/hive
- Iceberg 与 Hive Metastore 对接：https://iceberg.apache.org/docs/latest/hive/
