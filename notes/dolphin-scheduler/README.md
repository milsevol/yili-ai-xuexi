# 海豚调度（Apache DolphinScheduler）

Apache DolphinScheduler 是一个分布式、可视化的 DAG 工作流调度平台，常用于大数据离线任务编排（数仓 ETL、报表、机器学习流水线等）。本主题用中文笔记 + **浏览器可视化交互演示**，帮你建立「是什么 → 怎么跑 → 怎么用 → 怎么运维」的完整图景。

> 版本参考：以社区 3.x 架构为主（Master / Worker / API / Alert + 注册中心）。演示不依赖真实集群；默认打开 `demos/index.html` 交互页。

## 先决知识

- 了解基本的「定时任务 / 批处理」概念（cron、依赖、失败重试）
- 知道 DAG（有向无环图）是什么
- 有一点大数据或数仓背景更佳（Hive / Spark / Flink 任务出现时能对上号），非必须

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位.md) | `./start.sh 01` | crontab vs DAG、选型、学习主线 |
| 2 | [02-架构与组件](./notes/02-架构与组件.md) | `./start.sh 02` | 点选组件看职责与调度链路 |
| 3 | [03-核心概念](./notes/03-核心概念.md) | `./start.sh 03` | 定义 vs 实例（可点生成实例） |
| 4 | [04-DAG与调度](./notes/04-DAG与调度.md) | `./start.sh 04` | DAG 实验室：单步/播放、失败策略 |
| 5 | [05-任务类型详解](./notes/05-任务类型详解.md) | `./start.sh 05` | 点选任务类型看用途 |
| 6 | [06-参数传递与时间变量](./notes/06-参数传递与时间变量.md) | — | 时间变量、参数层级、任务间传参 |
| 7 | [07-资源数据源与环境](./notes/07-资源数据源与环境.md) | — | 资源中心、数据源、Worker 组、环境 |
| 8 | [08-部署与快速上手](./notes/08-部署与快速上手.md) | — | Docker / 伪集群、最小闭环 |
| 9 | [09-运维实践与故障排查](./notes/09-运维实践与故障排查.md) | — | 容错、排障、监控、升级 |
| 10 | [10-生态对比与FAQ](./notes/10-生态对比与FAQ.md) | — | 选型对比与 FAQ |

建议：01–05 **边读笔记边打开对应交互章**；06–07 补实战细节；08 起真实环境；09–10 运维与选型。

## 如何启动演示

默认是**浏览器可视化交互**：分章节点选、架构可点、DAG 可单步/播放。

```bash
cd notes/dolphin-scheduler
./start.sh          # 打开交互演示页
./start.sh 04       # 打开并跳到第 4 章（DAG 实验室）
./start.sh --help
```

备用终端版（纯文字）：

```bash
./start.sh --cli
./start.sh --cli 04
# 或 python3 demos/main.py --cli
```

本主题无第三方依赖；`demos/index.html` 为交互页，无需构建。演示不连接真实 DolphinScheduler 集群。演示对应 01–05 章；06–10 以实战操作为主，无本地模拟演示。

## 参考与官方文档

- 官网文档（介绍）：https://dolphinscheduler.apache.org/zh-cn/docs/latest/user_doc/about/introduction.html
- 快速开始：https://dolphinscheduler.apache.org/zh-cn/docs/latest/user_doc/guide/start/quick-start.html
- GitHub：https://github.com/apache/dolphinscheduler
- 架构设计（仓库内中文）：`docs/docs/zh/contribute/architecture-design.md`
