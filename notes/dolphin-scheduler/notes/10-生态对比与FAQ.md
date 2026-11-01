# 10 生态对比与常见问题（FAQ）

## 和 Airflow 详细对照

| 维度 | DolphinScheduler | Airflow |
| --- | --- | --- |
| DAG 定义 | UI 拖拽为主 + OpenAPI / Python SDK | Python 代码（DAG as Code） |
| 版本管理 | 平台内版本 + 上线/下线 | Git 天然集成，code review 友好 |
| 目标用户 | 数仓 / 数据运营（可视化） | 数据工程 / 平台工程（写代码） |
| 大数据任务 | 内置 Spark/Flink/Hive 插件，页面化 | 靠 Provider Operator，灵活但要写代码 |
| 补数 | UI 选区间，串行/并行一键 | catchup / backfill，强但需懂框架 |
| 多租户权限 | 完善（项目 / 租户 / 资源授权） | RBAC 有但偏粗 |
| 测试 | 相对弱（偏平台操作） | pytest 直接测 DAG，CI 友好 |
| 部署栈 | Java + 注册中心 + RDBMS | Python + RDBMS（+ Celery/K8s） |
| 社区生态 | 国内活跃，中文资料多 | 全球活跃，Provider 生态巨大 |

**实践中的常见组合**：数仓日批与可视化运维用海豚；复杂动态编排、ML 流水线用 Airflow 或自研——不是非此即彼。

## 与其他调度对比速览

| 产品 | 一句话 | 何时考虑 |
| --- | --- | --- |
| XXL-JOB | Java 分布式任务调度 | 服务内定时任务、无复杂 DAG |
| Azkaban | LinkedIn 老牌工作流调度 | 存量系统；新项目一般不选 |
| Oozie | Hadoop 生态老牌 | 维护遗留 Hadoop 作业；新项目不选 |
| Argo Workflows | K8s 原生工作流 | 全面 K8s 化、CI / ML 场景 |
| Airflow | DAG as Code 标杆 | Python 工程团队 |
| 海豚 | 可视化大数据工作流平台 | 数仓团队、国内生态 |

## 选型决策树（简版）

```
任务之间有复杂依赖吗？
├─ 没有，只是分布式定时执行 ──► XXL-JOB / crontab
└─ 有 ──► 团队主要用什么协作？
          ├─ UI 可视化 + 数仓同学为主 ──► DolphinScheduler
          ├─ Python 代码评审 + 工程化 ──► Airflow
          └─ 全 K8s + 容器化任务 ──► Argo Workflows
```

## 常见问题 FAQ

**Q1：改了工作流，为什么还按旧逻辑跑？**
A：定义改了要重新「上线」；运行中的实例用的仍是创建时的快照。

**Q2：工作流上线了，定时就是不跑？**
A：检查调度是否单独「上线」；cron 方言（Quartz 秒开头）；时区。

**Q3：Worker 要直连数据库吗？**
A：2.x 起不需要。Worker 只跟 Master 通信，状态由 Master 落库。

**Q4：Master 是单点吗？**
A：不是。多 Master 去中心化，通过注册中心互知与容错接管。

**Q5：补数会重复写数据吗？**
A：平台只负责按区间生成实例；是否重复写取决于任务是否幂等。分区覆盖写（`INSERT OVERWRITE`）是标准姿势。

**Q6：任务日志在哪里？**
A：Worker 本地执行目录，UI 查看时由 API 实时拉取。Worker 下线或日志清理后 UI 看不到。

**Q7：一个项目多大合适？**
A：按数据域 / 团队划分。单项目几百条工作流没问题，但授权与检索会变钝，宜早拆。

**Q8：能用 API 触发工作流吗？**
A：可以。OpenAPI + Token（安全中心创建），第三方系统可编程触发、传参。

**Q9：海豚适合跑实时流任务吗？**
A：不适合。它是批调度平台；流任务用 Flink 平台 / K8s 部署，海豚只负责启停编排（如定时拉起同步作业）。

**Q10：实例太多页面卡？**
A：实例表膨胀，见第 09 章治理；同时检查元数据库慢查询。

**Q11：和 XXL-JOB 能共存吗？**
A：常见组合：XXL-JOB 管微服务内部定时，海豚管数据工作流，互不冲突。

**Q12：国产化 / 信创环境？**
A：Java 技术栈 + 支持国产数据库元库的实践较多（以社区案例为准），是国内平台常见选型原因之一。

## 学习路径建议（结合本仓库）

1. 读 01–03，并分别打开 `./start.sh 01`～`03`（浏览器交互：对比、点组件、生成实例）
2. 读 04，重点玩 `./start.sh 04`（DAG 单步/播放 + 失败策略）；再读 05～06（`./start.sh 05` + 参数笔记）
3. 读 07–08：本机 Docker 起一套，走完「最小闭环」
4. 读 09–10：运维清单与选型陈述
5. 实战：把真实链路画成 DAG，标业务日期与依赖，落进平台

> 交互页：`demos/index.html`。需要纯文字时加 `--cli`。

## 参考与官方文档

- 官网：https://dolphinscheduler.apache.org/zh-cn/
- GitHub：https://github.com/apache/dolphinscheduler
- 架构设计（中文，仓库内）：`docs/docs/zh/contribute/architecture-design.md`
- 官方 FAQ 与 Release Notes：选型 / 升级前必读

## 自测


1. 什么情况下你会选 Airflow 而不是海豚？各说三个理由。
2. 海豚为什么不适合调度实时流任务？
3. 向一位没接触过调度的同事，用 3 句话介绍海豚调度。
