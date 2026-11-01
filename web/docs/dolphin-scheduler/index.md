# 海豚调度（Apache DolphinScheduler）

Apache DolphinScheduler 是一个分布式、可视化的 DAG 工作流调度平台，常用于大数据离线任务编排。本主题用中文笔记 + **浏览器可视化交互演示**，帮助快速理解概念与调度逻辑。

> 版本参考：社区 3.x。演示不连真实集群；默认打开 `demos/index.html`。

## 先决知识

- 定时任务 / 批处理（cron、依赖、重试）
- DAG（有向无环图）基本概念
- 有数仓背景更佳，非必须

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位) | `./start.sh 01` | crontab vs DAG、选型 |
| 2 | [02-架构与组件](./notes/02-架构与组件) | `./start.sh 02` | 点选组件看职责 |
| 3 | [03-核心概念](./notes/03-核心概念) | `./start.sh 03` | 定义 vs 实例 |
| 4 | [04-DAG与调度](./notes/04-DAG与调度) | `./start.sh 04` | DAG 实验室（单步/失败策略） |
| 5 | [05-任务类型详解](./notes/05-任务类型详解) | `./start.sh 05` | 点选任务类型 |
| 6 | [06-参数传递与时间变量](./notes/06-参数传递与时间变量) | — | 时间变量与传参 |
| 7 | [07-资源数据源与环境](./notes/07-资源数据源与环境) | — | 资源 / 数据源 / Worker 组 |
| 8 | [08-部署与快速上手](./notes/08-部署与快速上手) | — | Docker 与最小闭环 |
| 9 | [09-运维实践与故障排查](./notes/09-运维实践与故障排查) | — | 容错与排障 |
| 10 | [10-生态对比与FAQ](./notes/10-生态对比与FAQ) | — | 选型与 FAQ |

建议：01–05 边读边开对应交互章；08 起真实环境。

## 如何启动演示

```bash
cd notes/dolphin-scheduler
./start.sh          # 浏览器可视化交互
./start.sh 04       # 直达 DAG 实验室
./start.sh --cli    # 备用终端文字版
```

也可：`python3 main.py dolphin-scheduler` / `python3 main.py dolphin-scheduler 04`。

## 参考与官方文档

- [官网文档（介绍）](https://dolphinscheduler.apache.org/zh-cn/docs/latest/user_doc/about/introduction.html)
- [快速开始](https://dolphinscheduler.apache.org/zh-cn/docs/latest/user_doc/guide/start/quick-start.html)
- [GitHub](https://github.com/apache/dolphinscheduler)
- 架构设计：上游仓库 `docs/docs/zh/contribute/architecture-design.md`
