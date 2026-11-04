# Apache Flink

Apache Flink 是**真正的流计算引擎**：从第一天起就以「数据是连续不断地到来的」为前提设计，把「状态 State、精确一次 Exactly-Once、事件时间 Event-Time、检查点 Checkpoint」这四件事做到开箱即用。Spark Structured Streaming 向它靠拢，Kafka Streams 借鉴了它的 Keyed State，Iceberg/Hudi/Delta 湖仓在流写入上也绕不开 Flink。本主题用中文笔记梳理「是什么 → 架构 → DataStream → 时间语义 → Window → State/Checkpoint → SQL → 部署 → 调优 → 生态」的完整链路。

> 版本参考：以 **Flink 1.18 / 1.19 / 1.20** 为准（1.20 引入 Flink SQL Gateway / Async State 重大改进），示例以 Java 11 + Scala 2.12 / Python API 为主。配套**浏览器可视化交互演示**：Flink vs Spark vs Storm 对比、JM/TM/Slot、数据流图、Watermark 推进、四种窗口、Checkpoint Barrier、CDC 入湖、集群预算、反压排障树、FAQ 手风琴，打开 `demos/index.html` 即玩，无需集群。

## 先决知识

- 知道 Spark Streaming / Structured Streaming 的基本概念（微批、DStream、Dataset）
- 知道 Kafka 的 Topic / Partition / Consumer Group
- 会一点 Java 或 Python（读代码示例用），非必须
- 了解 HDFS / HBase 任一存储组件更佳，第 07/08 章会联动湖仓

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位.md) | `./start.sh 01` | Flink vs Spark vs Storm；真正的流 vs 微批；大数据链路位置 |
| 2 | [02-架构与运行原理](./notes/02-架构与运行原理.md) | `./start.sh 02` | JM/TM/Slot/数据流图；Operator Chain；并发度并行度 |
| 3 | [03-DataStream API与核心算子](./notes/03-DataStream%20API与核心算子.md) | `./start.sh 03` | Source/Transformation/Sink；map/flatmap/process；异步 IO |
| 4 | [04-时间语义与Watermark](./notes/04-时间语义与Watermark.md) | `./start.sh 04` | EventTime vs ProcessingTime；Watermark 原理；乱序容忍度 |
| 5 | [05-Window窗口机制](./notes/05-Window窗口机制.md) | `./start.sh 05` | 滚动/滑动/会话/全局窗口；AggregateFunction；迟到数据 |
| 6 | [06-State与Checkpoint](./notes/06-State与Checkpoint.md) | `./start.sh 06` | KeyedState vs OperatorState；Barrier 对齐；State Backend |
| 7 | [07-Flink SQL与Table API](./notes/07-Flink%20SQL与Table%20API.md) | `./start.sh 07` | CDC 入湖；Temporal Join；Hive Metastore；Batch vs Streaming |
| 8 | [08-部署与集群规划](./notes/08-部署与集群规划.md) | `./start.sh 08` | Standalone/YARN/K8s；JM/TM/Slot 预算；JVM/RocksDB 调优 |
| 9 | [09-性能调优与故障排查](./notes/09-性能调优与故障排查.md) | `./start.sh 09` | 数据倾斜；反压 Backpressure；Checkpoint 慢；GC；排障决策树 |
| 10 | [10-生态对比与FAQ](./notes/10-生态对比与FAQ.md) | `./start.sh 10` | Flink vs Spark vs Trino；CDC vs SeaTunnel；流批一体 vs 湖仓一体 |

建议：01–02 建立心智模型（真正的流、JM/TM/Slot、Operator Chain）；03–06 是 Flink 核心主战场（API、时间、窗口、状态/检查点）；07 是 Flink 成为企业首选的关键（SQL + CDC）；08–09 面向生产部署与调优；10 面向选型与面试。

## 如何启动演示

```bash
cd notes/flink
./start.sh          # 打开浏览器交互演示页
./start.sh 04       # 直达第 4 章（Watermark 推进动画）
./start.sh --cli    # 备用：终端文字摘要
```

也可从仓库根进入：`python3 main.py flink`。演示为纯 HTML/JS，无需构建、无需集群。

## 本地快速验证（可选）

Flink 提供 Standalone 模式单机运行，或直接用 Docker 镜像快速启动。只需 JDK 11+：

```bash
# Docker 起一个 Standalone 集群
docker run -d --name flink -p 8081:8081 flink:1.18
docker exec -it flink /opt/flink/bin/start-cluster.sh
# UI: http://localhost:8081
```

或下载二进制包：

```bash
# 示例
wget https://archive.apache.org/dist/flink/flink-1.19.1/flink-1.19.1-bin-scala_2.12.tgz
tar -xzf flink-1.19.1-bin-scala_2.12.tgz
cd flink-1.19.1
./bin/start-cluster.sh
# UI: http://localhost:8081
```

## 参考与官方文档

- 官网文档：https://nightlies.apache.org/flink/flink-docs-stable/
- DataStream API：https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/overview/
- Flink SQL：https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/table/overview/
- 状态后端：https://nightlies.apache.org/flink/flink-docs-stable/docs/ops/state/state_backends/
- GitHub：https://github.com/apache/flink
- 经典书籍：《Stream Processing with Apache Flink》（Fabian Hüske 等）
