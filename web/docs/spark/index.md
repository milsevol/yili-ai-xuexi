# Apache Spark

Apache Spark 是目前事实标准的大数据分布式计算引擎：一套代码同时覆盖离线批处理、交互式 SQL、流处理与机器学习。本主题用中文笔记 + **浏览器可视化交互演示**，梳理「是什么 → 怎么跑 → 怎么写 → 怎么调优」的完整链路。

> 版本参考：Spark 3.5，示例统一使用 **PySpark**。演示不连接真实集群；默认打开 `demos/index.html`。

## 先决知识

- 会基本 Python（能读懂函数、列表推导即可）
- 了解 Linux 命令行与「集群 / 分布式」的基本概念
- 知道 Hadoop / HDFS / Hive 是什么更佳，非必须（第 1 章会补定位）

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位) | `./start.sh 01` | vs MapReduce、生态全貌、选型法则 |
| 2 | [02-架构与运行原理](./notes/02-架构与运行原理) | `./start.sh 02` | Driver/Executor、生命周期、Job/Stage/Task |
| 3 | [03-RDD核心抽象](./notes/03-RDD核心抽象) | `./start.sh 03` | 惰性求值、宽窄依赖、cache/checkpoint |
| 4 | [04-DataFrame与Dataset](./notes/04-DataFrame与Dataset) | `./start.sh 04` | Schema、聚合/Join/窗口、UDF 陷阱 |
| 5 | [05-SparkSQL与Catalyst](./notes/05-SparkSQL与Catalyst) | `./start.sh 05` | Catalyst 四阶段、谓词下推、DataSource |
| 6 | [06-Shuffle与执行计划](./notes/06-Shuffle与执行计划) | `./start.sh 06` | Shuffle 过程、Join 策略、AQE、explain |
| 7 | [07-部署与资源配置](./notes/07-部署与资源配置) | `./start.sh 07` | 四种运行模式、资源计算、动态分配 |
| 8 | [08-性能调优实战](./notes/08-性能调优实战) | `./start.sh 08` | 数据倾斜、小文件、GC、反模式 |
| 9 | [09-StructuredStreaming](./notes/09-StructuredStreaming) | `./start.sh 09` | 无界表、Watermark、Exactly-Once |
| 10 | [10-生态对比与FAQ](./notes/10-生态对比与FAQ) | `./start.sh 10` | vs Flink、湖仓格式、MLlib、面试题 |

建议：01–03 建立心智模型（核心中的核心）；04–06 是日常开发主战场；07–08 面向生产；09–10 按需深入。

## 如何启动演示

```bash
cd notes/spark
./start.sh          # 浏览器可视化交互
./start.sh 06       # 直达 Shuffle 动画
./start.sh --cli    # 备用终端文字版
```

也可：`python3 main.py spark` / `python3 main.py spark 06`。

## 参考与官方文档

- [Spark 官方文档](https://spark.apache.org/docs/latest/)
- [PySpark API 参考](https://spark.apache.org/docs/latest/api/python/)
- [SQL Performance Tuning](https://spark.apache.org/docs/latest/sql-performance-tuning.html)
- [Structured Streaming 指南](https://spark.apache.org/docs/latest/structured-streaming-programming-guide.html)
- [GitHub](https://github.com/apache/spark)
