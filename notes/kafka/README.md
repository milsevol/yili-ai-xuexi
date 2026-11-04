# Apache Kafka

Apache Kafka 是大数据实时链路的**入口与中枢**：**Producer 往里写、Consumer 从里面拉，Broker 集群把消息按 Topic→Partition 存下来并做多副本容错**。它不只是个消息队列，更是一个**分布式提交日志（Distributed Commit Log）**——Streams 把它当状态存储、Connect 把它当数据总线、Flink/Spark Structured Streaming 把它当 Source/Sink。即使你日常写 Flink SQL，Partition 并行度、ISR 同步、Rebalance 这些概念仍然绕不开。本主题用中文笔记梳理「是什么 → 怎么存 → 怎么收发 → 怎么运维 → 怎么和周边生态配合」的完整链路。

> 版本参考：以 **Kafka 3.6 / 3.7 / 3.8** 为准，示例以 KRaft 模式、Java/Python Producer/Consumer API 与服务端配置为主。配套**浏览器可视化交互演示**：三大流派对比、架构角色点击、Producer 发送流程步进、Consumer Rebalance 模拟、零拷贝原理、分区并行度计算器、排障决策树等，打开 `demos/index.html` 即玩，无需集群。

## 先决知识

- 知道「消息队列 / 发布订阅 / 解耦」的基本概念
- 会一点 Java 或 Python（读 Producer/Consumer API 示例用）
- 理解 TCP、磁盘顺序写、分布式副本等底层概念更佳
- 有 Spark/Flink 使用经验更佳，第 09 章会对比它们和 Kafka 的配合

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位.md) | `./start.sh 01` | 为什么需要 Kafka、三大消息队列流派、Kafka vs RocketMQ vs RabbitMQ |
| 2 | [02-架构与核心概念](./notes/02-架构与核心概念.md) | `./start.sh 02` | Broker/Topic/Partition/ISR、KRaft vs ZooKeeper、Controller 角色 |
| 3 | [03-Producer生产者原理](./notes/03-Producer生产者原理.md) | `./start.sh 03` | 发送流程步进、acks/重试/幂等开关、事务 |
| 4 | [04-Consumer消费者原理](./notes/04-Consumer消费者原理.md) | `./start.sh 04` | 消费流程、Rebalance 模拟、提交策略、Exactly-Once 语义 |
| 5 | [05-存储与分区原理](./notes/05-存储与分区原理.md) | `./start.sh 05` | 零拷贝原理、分区并行度计算器、ISR 同步可视化 |
| 6 | [06-高级特性](./notes/06-高级特性.md) | `./start.sh 06` | Streams 拓扑模拟、Connect、Exactly-Once 事务、压缩算法选择 |
| 7 | [07-部署与集群规划](./notes/07-部署与集群规划.md) | `./start.sh 07` | Broker 数量→分区数预算、KRaft 部署、JVM/内核调优 |
| 8 | [08-运维监控与故障排查](./notes/08-运维监控与故障排查.md) | `./start.sh 08` | 症状→原因→处理 的排障决策树、核心指标 |
| 9 | [09-Kafka与周边生态](./notes/09-Kafka与周边生态.md) | `./start.sh 09` | 大数据链路位置图、Flink vs Spark Streaming、Kafka Connect CDC |
| 10 | [10-生态对比与FAQ](./notes/10-生态对比与FAQ.md) | `./start.sh 10` | Kafka vs Pulsar vs RocketMQ、KRaft 替代 ZK、Kafka on K8s、面试 FAQ |

建议：01–02 建立心智模型（Partition 是一切并行与吞吐的根本）；03–05 是 Producer/Consumer/存储的核心日常；06 面向高级特性与事务；07–08 面向部署运维与排障；09–10 面向生态选型与面试。

## 如何启动演示

```bash
cd notes/kafka
./start.sh          # 打开浏览器交互演示页
./start.sh 02       # 直达第 2 章（架构与核心概念）
./start.sh --cli    # 备用：终端文字摘要
```

也可从仓库根进入：`python3 main.py kafka`。演示为纯 HTML/JS，无需构建、无需集群。

## 本地快速验证（可选）

Kafka 支持单机 KRaft 模式快速验证，需要 JDK 17+（3.7+ 推荐）。只想验证 Producer/Consumer 可用时，也可以先用 Docker 起一个 KRaft 环境：

```bash
# Docker Compose 最简示例思路（镜像版本以实际发行版为准）
docker run -d --name kafka ^
  -p 9092:9092 -p 9093:9093 -p 8080:8080 ^
  -e KAFKA_NODE_ID=1 -e KAFKA_PROCESS_ROLES=broker,controller ^
  -e KAFKA_CONTROLLER_QUORUM_VOTERS=1@localhost:9093 ^
  -e KAFKA_LISTENERS=PLAINTEXT://:9092,CONTROLLER://:9093 ^
  -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://localhost:9092 ^
  bitnami/kafka:3.8

# 创建主题 + 生产 + 消费
docker exec -it kafka /opt/bitnami/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --topic demo --partitions 3 --replication-factor 1
docker exec -it kafka /opt/bitnami/kafka/bin/kafka-console-producer.sh --bootstrap-server localhost:9092 --topic demo
docker exec -it kafka /opt/bitnami/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic demo --from-beginning
```

> 注意：ZooKeeper 模式在 3.8 开始 deprecated，新项目务必用 KRaft。3.7 起 KRaft 已标记为生产可用。

## 参考与官方文档

- 官网文档（3.8）：https://kafka.apache.org/38/documentation.html
- KRaft 介绍：https://kafka.apache.org/38/documentation.html#kraft
- Producer 配置：https://kafka.apache.org/documentation/#producerconfigs
- Consumer 配置：https://kafka.apache.org/documentation/#consumerconfigs
- GitHub：https://github.com/apache/kafka
- 经典书籍：《Kafka 权威指南》（第 2 版）
