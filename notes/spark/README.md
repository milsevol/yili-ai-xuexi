# Apache Spark

Apache Spark 是目前事实标准的大数据分布式计算引擎：一套代码同时覆盖离线批处理、交互式 SQL、流处理与机器学习。本主题用中文笔记梳理「是什么 → 怎么跑 → 怎么写 → 怎么调优」的完整链路。

> 版本参考：以 **Spark 3.x**（3.5 为主）为准，示例统一使用 **PySpark**。配套**浏览器可视化交互演示**：RDD 惰性求值、Shuffle 动画、倾斜模拟器、资源计算器、Watermark 模拟等，打开 `demos/index.html` 即玩，无需集群。

## 先决知识

- 会基本 Python（能读懂函数、列表推导即可）
- 了解 Linux 命令行与「集群 / 分布式」的基本概念
- 知道 Hadoop / HDFS / Hive 是什么更佳，非必须（第 1 章会补定位）

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位.md) | `./start.sh 01` | vs MR 对比卡、生态组件、学习主线 |
| 2 | [02-架构与运行原理](./notes/02-架构与运行原理.md) | `./start.sh 02` | 点选角色 + 生命周期步进 + Job/Stage/Task 计算器 |
| 3 | [03-RDD核心抽象](./notes/03-RDD核心抽象.md) | `./start.sh 03` | 惰性求值日志、宽窄依赖 SVG 切换、cache 分支复用 |
| 4 | [04-DataFrame与Dataset](./notes/04-DataFrame与Dataset.md) | `./start.sh 04` | 操作链搭建器（生成代码+实时结果）+ UDF 性能对比 |
| 5 | [05-SparkSQL与Catalyst](./notes/05-SparkSQL与Catalyst.md) | `./start.sh 05` | Catalyst 四阶段步进 + 谓词下推开关 |
| 6 | [06-Shuffle与执行计划](./notes/06-Shuffle与执行计划.md) | `./start.sh 06` | Shuffle 搬家动画 + Join 策略选择器 + 分区健康检查 |
| 7 | [07-部署与资源配置](./notes/07-部署与资源配置.md) | `./start.sh 07` | 资源计算器（联动 submit 模板）+ Executor 内存条 |
| 8 | [08-性能调优实战](./notes/08-性能调优实战.md) | `./start.sh 08` | 倾斜模拟器（加盐前后）+ 小文件生成器 + 反模式翻卡 |
| 9 | [09-StructuredStreaming](./notes/09-StructuredStreaming.md) | `./start.sh 09` | Watermark 模拟器 + 输出模式矩阵 |
| 10 | [10-生态对比与FAQ](./notes/10-生态对比与FAQ.md) | `./start.sh 10` | Spark/Flink 决策树 + 湖仓对比 + FAQ 手风琴 |

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
