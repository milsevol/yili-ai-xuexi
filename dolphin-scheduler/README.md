# 海豚调度（Apache DolphinScheduler）

Apache DolphinScheduler 是一个分布式、可视化的 DAG 工作流调度平台，常用于大数据离线任务编排（数仓 ETL、报表、机器学习流水线等）。本主题用中文笔记 + Python 概念演示，帮你建立「是什么 → 怎么跑 → 怎么用」的完整图景。

> 版本参考：以社区 3.x 架构为主（Master / Worker / API / Alert + 注册中心）。演示不依赖真实集群，本地即可跑通概念。

## 先决知识

- 了解基本的「定时任务 / 批处理」概念（cron、依赖、失败重试）
- 知道 DAG（有向无环图）是什么
- 有一点大数据或数仓背景更佳（Hive / Spark / Flink 任务出现时能对上号），非必须

## 学习路径

| 顺序 | 笔记 | 演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位.md) | `01` | 解决什么问题、和 Airflow/Oozie 怎么选 |
| 2 | [02-架构与组件](./notes/02-架构与组件.md) | `02` | Master / Worker / API / Alert / 注册中心 |
| 3 | [03-核心概念](./notes/03-核心概念.md) | `03` | 项目、工作流、任务、实例、租户 |
| 4 | [04-DAG与调度](./notes/04-DAG与调度.md) | `04` | 依赖、cron、补数、失败策略、优先级 |
| 5 | [05-任务类型与资源](./notes/05-任务类型与资源.md) | `05` | Shell/SQL/Spark 等、资源中心、数据源 |
| 6 | [06-运维实践与对比](./notes/06-运维实践与对比.md) | — | 部署形态、容错、和 Airflow 对照、上手建议 |

建议顺序：先通读 01–04，跑对应演示；再按需看 05–06。真正上手时再对照官方文档起 Docker / 伪集群。

## 如何启动演示

```bash
cd dolphin-scheduler
python3 -m venv .venv
source .venv/bin/activate
# 本主题无第三方依赖，可直接跑
python3 demos/main.py          # 菜单选择
python3 demos/main.py 04       # 直达第 4 章演示
```

演示均为本地模拟：用 Python 表达 DAG 拓扑执行、Master/Worker 分工、补数与失败策略等，不连接真实 DolphinScheduler。

## 官方资料

- 官网文档：https://dolphinscheduler.apache.org/zh-cn/docs/latest/user_doc/about/introduction.html
- GitHub：https://github.com/apache/dolphinscheduler
- 架构设计（中文）：仓库内 `docs/docs/zh/contribute/architecture-design.md`
