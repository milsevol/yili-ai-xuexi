# Apache Kafka

Apache Kafka 是大数据实时链路的入口与中枢：Producer 往里写、Consumer 从里面拉，Broker 集群按 Topic→Partition 存消息并做多副本容错。不只是消息队列，更是分布式提交日志。本主题用中文笔记 + **浏览器可视化交互演示**，梳理「是什么 → 怎么存 → 怎么收发 → 怎么运维 → 怎么和生态配合」的完整链路。

> 版本参考：Kafka 3.6 / 3.7 / 3.8（KRaft 模式）。演示不连接真实集群；默认打开 `demos/index.html`。

## 先决知识

- 消息队列 / 发布订阅 / 解耦的基本概念
- 会一点 Java 或 Python 更佳，非必须
- 理解 TCP、磁盘顺序写、分布式副本等底层概念更佳

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位) | `./start.sh 01` | 三大流派、Kafka vs RocketMQ vs RabbitMQ |
| 2 | [02-架构与核心概念](./notes/02-架构与核心概念) | `./start.sh 02` | Broker/Topic/Partition/ISR、KRaft vs ZK |
| 3 | [03-Producer 生产者原理](./notes/03-Producer生产者原理) | `./start.sh 03` | 发送流程步进、acks/重试/幂等/事务 |
| 4 | [04-Consumer 消费者原理](./notes/04-Consumer消费者原理) | `./start.sh 04` | 消费流程、Rebalance 模拟、提交策略 |
| 5 | [05-存储与分区原理](./notes/05-存储与分区原理) | `./start.sh 05` | 零拷贝原理、分区并行度、ISR 同步 |
| 6 | [06-高级特性](./notes/06-高级特性) | `./start.sh 06` | Streams、Connect、Exactly-Once、压缩 |
| 7 | [07-部署与集群规划](./notes/07-部署与集群规划) | `./start.sh 07` | Broker→分区预算、KRaft 部署、JVM 调优 |
| 8 | [08-运维监控与故障排查](./notes/08-运维监控与故障排查) | `./start.sh 08` | 排障决策树 + 核心指标表 |
| 9 | [09-Kafka 与周边生态](./notes/09-Kafka与周边生态) | `./start.sh 09` | 大数据链路位置图、Flink vs Spark Streaming |
| 10 | [10-生态对比与 FAQ](./notes/10-生态对比与FAQ) | `./start.sh 10` | Kafka vs Pulsar vs RocketMQ + 面试 FAQ |

## 如何启动演示

```bash
cd notes/kafka
./start.sh          # 浏览器可视化交互
./start.sh 02       # 直达架构与核心概念
./start.sh --cli    # 备用终端文字版
```

也可：`python3 main.py kafka` / `python3 main.py kafka 02`。

## 参考与官方文档

- [Kafka 3.8 官方文档](https://kafka.apache.org/38/documentation.html)
- [KRaft 介绍](https://kafka.apache.org/38/documentation.html#kraft)
- [Producer 配置](https://kafka.apache.org/documentation/#producerconfigs)
- [Consumer 配置](https://kafka.apache.org/documentation/#consumerconfigs)
- [GitHub](https://github.com/apache/kafka)
