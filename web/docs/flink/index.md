# Apache Flink

Apache Flink 是真正的流计算引擎：**一切皆流**，批处理是流的特例。核心是 State、Checkpoint、Watermark、Exactly-Once。本主题用中文笔记 + **浏览器可视化交互演示**，梳理「是什么 → 怎么算 → 怎么存状态 → 怎么保证一致性 → 怎么和 SQL/CDC 配合 → 怎么运维」的完整链路。

> 版本参考：Flink 1.18 / 1.19 / 1.20。演示不连接真实集群；默认打开 `demos/index.html`。

## 先决知识

- Spark 或 Storm 的基本概念（有其一即可）
- Kafka 基本概念（第 09 章会配合讲 CDC）
- 会一点 Java 或 Python 更佳，非必须

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位) | `./start.sh 01` | Flink vs Spark vs Storm、大数据链路位置 |
| 2 | [02-架构与运行原理](./notes/02-架构与运行原理) | `./start.sh 02` | JM/TM/Slot、数据流图、Operator Chain |
| 3 | [03-DataStream API 与核心算子](./notes/03-DataStream%20API与核心算子) | `./start.sh 03` | ProcessFunction、KeyedProcessFunction、异步 IO |
| 4 | [04-时间语义与 Watermark](./notes/04-时间语义与Watermark) | `./start.sh 04` | Watermark 推进动画、乱序容忍度 |
| 5 | [05-Window 窗口机制](./notes/05-Window窗口机制) | `./start.sh 05` | 四种窗口类型、迟到数据处理 |
| 6 | [06-State 与 Checkpoint](./notes/06-State与Checkpoint) | `./start.sh 06` | State 类型选择器、Checkpoint Barrier 步进 |
| 7 | [07-Flink SQL 与 Table API](./notes/07-Flink%20SQL与Table%20API) | `./start.sh 07` | Flink SQL vs DataStream、CDC 入湖 |
| 8 | [08-部署与集群规划](./notes/08-部署与集群规划) | `./start.sh 08` | JM/TM 数量、Slot/内存预算计算器 |
| 9 | [09-性能调优与故障排查](./notes/09-性能调优与故障排查) | `./start.sh 09` | 反压/倾斜/Checkpoint 慢 排障决策树 |
| 10 | [10-生态对比与 FAQ](./notes/10-生态对比与FAQ) | `./start.sh 10` | Flink vs Spark vs Trino + 面试 FAQ |

## 如何启动演示

```bash
cd notes/flink
./start.sh          # 浏览器可视化交互
./start.sh 04       # 直达 Watermark 推进动画
./start.sh --cli    # 备用终端文字版
```

也可：`python3 main.py flink` / `python3 main.py flink 04`。

## 参考与官方文档

- [Flink 1.18 官方文档](https://nightlies.apache.org/flink/flink-docs-release-1.18/)
- [Flink 1.19 官方文档](https://nightlies.apache.org/flink/flink-docs-release-1.19/)
- [Flink 架构概览](https://nightlies.apache.org/flink/flink-docs-release-1.18/deployment/)
- [GitHub](https://github.com/apache/flink)
