# OceanBase 数据库

OceanBase（OB）是蚂蚁集团自研的**分布式关系型数据库**：shared-nothing + Paxos 多副本，具备金融级高可用（RPO=0）、在线水平扩展、多租户隔离、MySQL/Oracle 双兼容与 HTAP 能力。本主题用中文笔记 + **浏览器可视化交互演示**，梳理「架构 → 存储 → 多租户 → SQL → 运维调优 → Oracle 迁移 → 选型」的完整链路。

> 版本参考：OceanBase 4.x（4.2 / 4.3 LTS 为常见生产版本）。演示不连接真实集群；默认打开 `demos/index.html`。

## 先决知识

- SQL 基础（JOIN、GROUP BY、事务）
- 了解 MySQL 或 Oracle 中的一种
- 了解主从复制、分区、索引的基本概念更佳
- 了解 Linux 与网络基础

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位) | `./start.sh 01` | OB 是什么、解决什么问题、与 MySQL/Oracle/TiDB 对比 |
| 2 | [02-架构与核心组件](./notes/02-架构与核心组件) | `./start.sh 02` | OBServer / RootService / OBProxy、Zone、分区与 Paxos 选主 |
| 3 | [03-存储引擎与多副本](./notes/03-存储引擎与多副本) | `./start.sh 03` | LSM-Tree、MemTable/SSTable、冻结转储合并、clog |
| 4 | [04-多租户与资源管理](./notes/04-多租户与资源管理) | `./start.sh 04` | Unit Config / Resource Pool / Tenant、隔离与扩缩容 |
| 5 | [05-SQL与兼容模式](./notes/05-SQL与兼容模式) | `./start.sh 05` | MySQL 模式 vs Oracle 模式、数据类型、分区索引 |
| 6 | [06-部署运维与性能调优](./notes/06-部署运维与性能调优) | `./start.sh 06` | 部署、巡检、备份恢复、合并、SQL 调优、故障处理 |
| 7 | [07-Oracle迁移OceanBase](./notes/07-Oracle迁移OceanBase) | `./start.sh 07` | 兼容性评估、OMS 迁移、校验、割接、SQL 改写、回滚 |
| 8 | [08-生态对比与FAQ](./notes/08-生态对比与FAQ) | `./start.sh 08` | OB vs TiDB vs PolarDB-X vs GaussDB、选型与 FAQ |

## 如何启动演示

```bash
cd notes/oceanbase
./start.sh          # 浏览器可视化交互
./start.sh 07       # 直达 Oracle 迁移
./start.sh --cli    # 备用终端文字版
```

也可：`python3 main.py oceanbase` / `python3 main.py oceanbase 07`。

## 参考与官方文档

- [OceanBase 官方文档](https://www.oceanbase.com/docs)
- [OceanBase 社区版 GitHub](https://github.com/oceanbase/oceanbase)
- [OceanBase 快速开始](https://www.oceanbase.com/docs/common-oceanbase-database-cn-10000000001691699)
- [OMS 数据迁移服务](https://www.oceanbase.com/docs/common-oms-cn-10000000001690000)
- [OceanBase 社区问答](https://ask.oceanbase.com/)
