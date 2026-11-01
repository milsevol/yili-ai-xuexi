# Apache Hadoop

Apache Hadoop 是大数据的地基：HDFS 负责海量数据的可靠存储，YARN 负责集群资源调度，MapReduce 提供第一代分布式批处理模型。本主题用中文笔记 + **浏览器可视化交互演示**，梳理「是什么 → 怎么存 → 怎么算 → 怎么管 → 怎么运维」的完整链路。

> 版本参考：Hadoop 3.3 / 3.4。演示不连接真实集群；默认打开 `demos/index.html`。

## 先决知识

- Linux 命令行、`ssh`、进程与权限
- 分布式 / 副本 / 集群的基本概念
- 会一点 Java 或 Python 更佳，非必须
- 有 Spark / Hive 经验更佳（第 1 章会先补定位）

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位) | `./start.sh 01` | 三件套职责、YARN 架构手术、生态与选型 |
| 2 | [02-HDFS架构与原理](./notes/02-HDFS架构与原理) | `./start.sh 02` | 读写流程步进 + 机架感知副本放置 |
| 3 | [03-HDFS实践与运维](./notes/03-HDFS实践与运维) | `./start.sh 03` | 命令速查 + 小文件元数据计算器 |
| 4 | [04-MapReduce原理与执行](./notes/04-MapReduce原理与执行) | `./start.sh 04` | WordCount 流水线 + Spill 次数计算 |
| 5 | [05-MapReduce进阶与优化](./notes/05-MapReduce进阶与优化) | `./start.sh 05` | 倾斜模拟 + Join 策略选择器 |
| 6 | [06-YARN资源管理与调度](./notes/06-YARN资源管理与调度) | `./start.sh 06` | 资源计算器 + 调度器对比 |
| 7 | [07-Hadoop生态组件](./notes/07-Hadoop生态组件) | `./start.sh 07` | 需求 → 组件推荐器 |
| 8 | [08-部署与集群规划](./notes/08-部署与集群规划) | `./start.sh 08` | 集群规模 → 参数建议 + 配置片段 |
| 9 | [09-运维监控与故障排查](./notes/09-运维监控与故障排查) | `./start.sh 09` | 症状 → 原因 → 处理 |
| 10 | [10-生态对比与FAQ](./notes/10-生态对比与FAQ) | `./start.sh 10` | 对象存储 / K8s 对比 + FAQ |

建议：01–02 建立心智模型；03–05 是日常主战场；06 面向资源与多租户；07–08 生态与落地；09–10 生产运维与选型。

## 如何启动演示

```bash
cd notes/hadoop
./start.sh          # 浏览器可视化交互
./start.sh 02       # 直达 HDFS 读写流程
./start.sh --cli    # 备用终端文字版
```

也可：`python3 main.py hadoop` / `python3 main.py hadoop 02`。

## 参考与官方文档

- [Hadoop 官方文档](https://hadoop.apache.org/docs/stable/)
- [HDFS 架构](https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html)
- [YARN 介绍](https://hadoop.apache.org/docs/stable/hadoop-yarn/hadoop-yarn-site/YARN.html)
- [MapReduce 教程](https://hadoop.apache.org/docs/stable/hadoop-mapreduce-client/hadoop-mapreduce-client-core/MapReduceTutorial.html)
- [GitHub](https://github.com/apache/hadoop)
