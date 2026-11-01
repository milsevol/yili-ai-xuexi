# Apache Hadoop

Apache Hadoop 是大数据的地基：**HDFS 负责把海量数据可靠地存下来，YARN 负责把集群资源统一调度，MapReduce 提供第一代分布式批处理模型**。即使你日常写 Spark/Flink，底层的数据本地性、Shuffle、资源队列、小文件问题，根都在这里。本主题用中文笔记梳理「是什么 → 怎么存 → 怎么算 → 怎么管 → 怎么运维」的完整链路。

> 版本参考：以 **Hadoop 3.3 / 3.4** 为准，示例以 HDFS 命令、Java 8 API 与 XML 配置为主。配套**浏览器可视化交互演示**：三件套定位、HDFS 读写流程、副本放置、小文件计算器、MapReduce 流水线、倾斜模拟、YARN 资源计算器、集群配置生成器、故障排查决策等，打开 `demos/index.html` 即玩，无需集群。

## 先决知识

- 会 Linux 命令行（目录、权限、进程、SSH）
- 知道「集群 / 分布式 / 副本」的基本概念
- 会一点 Java 或 Python 更佳（读代码示例用），非必须
- 有 Spark/Hive 使用经验更佳，第 1 章会先补定位

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位.md) | `./start.sh 01` | 三件套职责、1.x→YARN 架构手术、生态与选型 |
| 2 | [02-HDFS架构与原理](./notes/02-HDFS架构与原理.md) | `./start.sh 02` | 读写流程步进 + 机架感知副本放置 |
| 3 | [03-HDFS实践与运维](./notes/03-HDFS实践与运维.md) | `./start.sh 03` | 命令速查 + 小文件元数据计算器 |
| 4 | [04-MapReduce原理与执行](./notes/04-MapReduce原理与执行.md) | `./start.sh 04` | WordCount 流水线动画 + Spill 次数计算 |
| 5 | [05-MapReduce进阶与优化](./notes/05-MapReduce进阶与优化.md) | `./start.sh 05` | 倾斜模拟（加盐前后）+ Join 策略选择器 |
| 6 | [06-YARN资源管理与调度](./notes/06-YARN资源管理与调度.md) | `./start.sh 06` | 集群资源计算器 + 调度器对比 |
| 7 | [07-Hadoop生态组件](./notes/07-Hadoop生态组件.md) | `./start.sh 07` | 需求 → 组件推荐器 |
| 8 | [08-部署与集群规划](./notes/08-部署与集群规划.md) | `./start.sh 08` | 集群规模 → 参数建议 + 配置片段 |
| 9 | [09-运维监控与故障排查](./notes/09-运维监控与故障排查.md) | `./start.sh 09` | 症状 → 原因 → 处理 的排障决策 |
| 10 | [10-生态对比与FAQ](./notes/10-生态对比与FAQ.md) | `./start.sh 10` | HDFS vs 对象存储、YARN vs K8s、面试 FAQ |

建议：01–02 建立心智模型（存储与元数据是核心）；03–05 是 HDFS/MapReduce 的日常主战场；06 是资源与多租户；07–08 面向生态与落地；09–10 面向生产运维与选型。

## 如何启动演示

```bash
cd notes/hadoop
./start.sh          # 打开浏览器交互演示页
./start.sh 02       # 直达第 2 章（HDFS 读写流程）
./start.sh --cli    # 备用：终端文字摘要
```

也可从仓库根进入：`python3 main.py hadoop`。演示为纯 HTML/JS，无需构建、无需集群。

## 本地快速验证（可选）

Hadoop 支持单机伪分布式运行，但需要 Linux/macOS、JDK 8/11、`ssh localhost` 免密，并按官方文档配置四个 XML。只想验证 HDFS 客户端可用时，也可以先用 Docker 起一个伪分布式环境（注意镜像版本与 JDK）：

```bash
# 示例思路，镜像与端口以实际发行版文档为准
docker run -d --name hadoop -p 9870:9870 -p 8088:8088 apache/hadoop:3
docker exec -it hadoop hdfs dfs -mkdir -p /tmp/demo
docker exec -it hadoop bash -lc "printf 'hello hadoop\n' > /tmp/hello.txt && hdfs dfs -put /tmp/hello.txt /tmp/demo/"
docker exec -it hadoop hdfs dfs -cat /tmp/demo/hello.txt
```

> 注意：本机若默认 JDK 过高，先 `export JAVA_HOME=$(/usr/libexec/java_home -v 11)`（Hadoop 3.3/3.4 官方支持 JDK 8/11，更高版本需自行验证生态组件兼容性）。`hdfs namenode -format` 对同一目录只做一次。

## 参考与官方文档

- 官网文档（HDFS / YARN / MapReduce）：https://hadoop.apache.org/docs/stable/
- HDFS 架构：https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html
- YARN 介绍：https://hadoop.apache.org/docs/stable/hadoop-yarn/hadoop-yarn-site/YARN.html
- MapReduce 教程：https://hadoop.apache.org/docs/stable/hadoop-mapreduce-client/hadoop-mapreduce-client-core/MapReduceTutorial.html
- GitHub：https://github.com/apache/hadoop
- 经典书籍：《Hadoop 权威指南》（第 4 版，Tom White）
