# 湖仓一体（Apache Iceberg）

Apache Iceberg 是**开放表格式**：不改存储引擎，只在大数据文件（Parquet/ORC）之上加一层元数据，就补上了 Hive 表的三大短板——**没有 ACID、分区难演进、不能时间旅行**。它是「湖仓一体」的事实标准之一，能被 Spark / Flink / Hive / Trino 同时读写。本主题用中文笔记 + **浏览器可视化交互演示**，梳理「为什么需要 → 元数据怎么组织 → 怎么保证一致性 → 怎么演进 → 怎么调优」的完整链路。

> 版本参考：Iceberg 1.4 / 1.5 / 1.6。演示不连接真实集群；默认打开 `demos/index.html`。

## 先决知识

- HDFS 或 S3 对象存储基本概念
- Hive Metastore（Catalog 最常用的实现）
- Spark 或 Flink 其一的读写经验
- Parquet / ORC 列式文件格式

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与湖仓一体](./notes/01-概述与湖仓一体) | `./start.sh 01` | 数据湖/数仓/湖仓三代对比、Hive 四大痛点 |
| 2 | [02-架构与元数据层级](./notes/02-架构与元数据层级) | `./start.sh 02` | Catalog→Metadata→Manifest List→Manifest→Data File |
| 3 | [03-表格式与文件组织](./notes/03-表格式与文件组织) | `./start.sh 03` | Manifest 结构、min/max 统计信息加速 |
| 4 | [04-ACID 与快照隔离](./notes/04-ACID与快照隔离) | `./start.sh 04` | 乐观并发控制、指针原子切换、冲突重试 |
| 5 | [05-分区演进与隐藏分区](./notes/05-分区演进与隐藏分区) | `./start.sh 05` | 隐藏分区、days()/bucket()、演进不重写数据 |
| 6 | [06-Time Travel 与版本管理](./notes/06-TimeTravel与版本管理) | `./start.sh 06` | Snapshot 时间轴、rollback、branch/tag |
| 7 | [07-Schema 演进与数据类型](./notes/07-Schema演进与数据类型) | `./start.sh 07` | 列 ID 机制、加列/删列/改类型 |
| 8 | [08-与 Spark/Flink/Hive 集成](./notes/08-与SparkFlinkHive集成) | `./start.sh 08` | 各引擎读写、Flink 流式 exactly-once |
| 9 | [09-性能优化与实践](./notes/09-性能优化与实践) | `./start.sh 09` | 小文件 compaction、元数据重写、Z-Order |
| 10 | [10-生态对比与 FAQ](./notes/10-生态对比与FAQ) | `./start.sh 10` | Iceberg vs Hudi vs Delta Lake + 面试 FAQ |

## 如何启动演示

```bash
cd notes/iceberg
./start.sh          # 浏览器可视化交互
./start.sh 06       # 直达 Time Travel 时间轴
./start.sh --cli    # 备用终端文字版
```

也可：`python3 main.py iceberg` / `python3 main.py iceberg 06`。

## 参考与官方文档

- [Iceberg 官方文档](https://iceberg.apache.org/docs/latest/)
- [表格式规范 Table Spec](https://iceberg.apache.org/spec/)
- [Spark 集成](https://iceberg.apache.org/docs/latest/spark-getting-started/)
- [Flink 集成](https://iceberg.apache.org/docs/latest/flink-getting-started/)
- [表维护与优化](https://iceberg.apache.org/docs/latest/maintenance/)
- [GitHub](https://github.com/apache/iceberg)
