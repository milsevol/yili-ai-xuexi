# Apache Spark

Apache Spark 是目前事实标准的大数据分布式计算引擎：一套代码同时覆盖离线批处理、交互式 SQL、流处理与机器学习。本主题用中文笔记梳理「是什么 → 怎么跑 → 怎么写 → 怎么调优」的完整链路。

> 版本参考：以 **Spark 3.x**（3.5 为主）为准，示例统一使用 **PySpark**。配套**浏览器可视化交互演示**：只演示难懂的概念——MR vs Spark 迭代赛跑、提交全链路动画、Shuffle 搬家、UDF 过境动画、倾斜甘特图、资源装箱、Watermark 模拟等，打开 `demos/index.html` 即玩，无需集群。演示的设计规范见 `demos/演示提示词.md`（可复用于其他主题）。

## 先决知识

- 会基本 Python（能读懂函数、列表推导即可）
- 了解 Linux 命令行与「集群 / 分布式」的基本概念
- 知道 Hadoop / HDFS / Hive 是什么更佳，非必须（第 1 章会补定位）

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位.md) | `./start.sh 01` | MR vs Spark 迭代赛跑（真实比例+快进，磁盘 IO 计数）+ 生态一张图 |
| 2 | [02-架构与运行原理](./notes/02-架构与运行原理.md) | `./start.sh 02` | 提交→DAG→切 Stage→Task 上核全链路动画 + Job/Stage/Task 计算器 |
| 3 | [03-RDD核心抽象](./notes/03-RDD核心抽象.md) | `./start.sh 03` | 惰性求值流水线动画 + 宽窄依赖 Stage 边界 + cache 计时对比 |
| 4 | [04-DataFrame与Dataset](./notes/04-DataFrame与Dataset.md) | `./start.sh 04` | 操作链搭建器（生成代码+实时结果）+ UDF 三种实现过境动画 |
| 5 | [05-SparkSQL与Catalyst](./notes/05-SparkSQL与Catalyst.md) | `./start.sh 05` | Catalyst 计划树演变（谓词下推/列裁剪可见）+ IO 对比开关 |
| 6 | [06-Shuffle与执行计划](./notes/06-Shuffle与执行计划.md) | `./start.sh 06` | Shuffle 搬家动画 + Join 策略数据流动画（广播 vs SMJ）+ 分区健康检查 |
| 7 | [07-部署与资源配置](./notes/07-部署与资源配置.md) | `./start.sh 07` | 资源装箱可视化（Worker 装 Executor，碎片/排队可见）+ 内存条 + submit 模板 |
| 8 | [08-性能调优实战](./notes/08-性能调优实战.md) | `./start.sh 08` | 倾斜甘特图（加盐两阶段重放对比总耗时）+ 小文件生成器 |
| 9 | [09-StructuredStreaming](./notes/09-StructuredStreaming.md) | `./start.sh 09` | Watermark 模拟器（自动播放，迟到数据两种命运）+ 输出模式矩阵 |
| 10 | [10-生态对比与FAQ](./notes/10-生态对比与FAQ.md) | `./start.sh 10` | Spark/Flink 决策树 |

建议：01–03 建立心智模型（核心中的核心）；04–06 是日常开发主战场；07–08 面向生产；09–10 按需深入。

## 如何启动演示

```bash
cd notes/spark
./start.sh          # 打开浏览器交互演示页
./start.sh 06       # 直达第 6 章（Shuffle 动画）
./start.sh --cli    # 备用：终端文字摘要
```

也可从仓库根进入：`python3 main.py spark`。演示为纯 HTML/JS，无需构建、无需集群。

## 本地快速验证（可选）

PySpark 支持完全本地运行，无需集群：

```bash
python3 -m pip install pyspark==3.5.1   # 需要本机有 JDK（8/11/17 均可）

python3 - <<'EOF'
from pyspark.sql import SparkSession
spark = SparkSession.builder.master("local[*]").appName("hello").getOrCreate()
print(spark.range(10).groupBy().sum("id").collect())
spark.stop()
EOF
```

> 注意：PySpark 3.5 官方支持 Python 3.8–3.11 与 JDK 8/11/17。若本机默认 JDK 过高导致启动报错，可 `export JAVA_HOME=$(/usr/libexec/java_home -v 17)` 再试。

## 参考与官方文档

- 官网文档（Quick Start / SQL / Tuning）：https://spark.apache.org/docs/latest/
- PySpark API 参考：https://spark.apache.org/docs/latest/api/python/
- GitHub：https://github.com/apache/spark
- 经典书籍：《Learning Spark, 2nd Edition》（O'Reilly，免费版见 Databricks 官网）、《Spark 快速大数据分析》（第 1 版中译）
