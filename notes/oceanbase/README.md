# OceanBase 数据库

OceanBase（OB）是蚂蚁集团自研的**分布式关系型数据库**：shared-nothing 架构 + Paxos 多副本，具备金融级高可用（RPO=0）、在线水平扩展、多租户隔离、MySQL/Oracle 双兼容与 HTAP 能力。它从支付宝核心交易场景走出来，2020 年开源，目前广泛应用于金融、政务、运营商等行业的核心系统替换与整合。

本主题用中文笔记梳理「是什么 → 架构怎么跑 → 数据怎么存 → 租户怎么隔离 → SQL 怎么写 → 怎么运维调优 → Oracle 怎么迁 → 怎么选型」的完整链路，并配一个**浏览器可视化交互演示**（Paxos 选主、LSM 合并、租户资源、Oracle 迁移流程）。

> 版本参考：以 **OceanBase 4.x（4.2 / 4.3 LTS 为常见生产版本）** 为准。不同小版本功能存在差异，落地前以对应版本文档为准。

## 先决知识

- 会 SQL（SELECT / JOIN / GROUP BY / 事务基础）
- 了解 MySQL 或 Oracle 中的至少一种
- 知道主从复制、分区、索引的基本概念更佳
- 了解 Linux 与网络基础，便于理解部署与运维

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位.md) | `./start.sh 01` | OB 是什么；解决什么问题；产品家族；与 MySQL/Oracle/TiDB 对比；适用场景 |
| 2 | [02-架构与核心组件](./notes/02-架构与核心组件.md) | `./start.sh 02` | OBServer / RootService / OBProxy；Zone/Region；分区与 Paxos；一次写入链路 |
| 3 | [03-存储引擎与多副本](./notes/03-存储引擎与多副本.md) | `./start.sh 03` | LSM-Tree；MemTable/SSTable；冻结/转储/合并；clog；多副本与事务 |
| 4 | [04-多租户与资源管理](./notes/04-多租户与资源管理.md) | `./start.sh 04` | Unit Config / Resource Pool / Tenant；建租户；隔离；扩缩容；主备租户 |
| 5 | [05-SQL与兼容模式](./notes/05-SQL与兼容模式.md) | `./start.sh 05` | MySQL 模式 vs Oracle 模式；数据类型；分区与索引；常用对象；系统视图 |
| 6 | [06-部署运维与性能调优](./notes/06-部署运维与性能调优.md) | `./start.sh 06` | OBD/OCP 部署；巡检；备份恢复；合并；SQL 调优；常用参数；故障处理 |
| 7 | [07-Oracle迁移OceanBase](./notes/07-Oracle迁移OceanBase.md) | `./start.sh 07` | 兼容性评估；结构/全量/增量迁移；OMS；校验；割接；SQL 改写；回滚预案 |
| 8 | [08-生态对比与FAQ](./notes/08-生态对比与FAQ.md) | `./start.sh 08` | OB vs TiDB vs PolarDB-X vs GaussDB；与 OLAP 分工；选型；FAQ |

建议顺序：01–02 建立整体架构心智；03–04 理解存储与资源隔离；05 是日常 SQL 主战场；06 面向运维；07 是 Oracle 迁移实战；08 用于选型与面试。

## 如何启动演示

```bash
cd notes/oceanbase
./start.sh          # 打开浏览器交互演示页
./start.sh 07       # 直达第 7 章（Oracle 迁移）
./start.sh --cli    # 备用：终端文字摘要
./start.sh --cli 03 # 终端查看第 3 章摘要
```

也可从仓库根进入：`python3 main.py oceanbase`。演示为纯 HTML/JS，无需集群、无需构建。

演示包含：

- **Paxos 选主**：三 Zone 三副本，点击「杀掉 Leader」观察重新选主；
- **LSM 合并**：模拟写入 → 冻结 → 转储 → 合并；
- **租户资源**：调整 Unit 规格，检查资源是否足够；
- **Oracle 迁移**：按步骤推进迁移流程，查看阶段要点；
- **兼容性清单**：查看常见 Oracle 对象的支持情况。

## 本地快速体验（可选）

单机容器适合学习，不具备高可用：

```bash
docker run -d --name ob \
  -p 2881:2881 -p 2883:2883 \
  -e MODE=mini \
  oceanbase/oceanbase-ce:latest

docker logs -f ob   # 等待初始化完成

docker exec -it ob obclient -h127.0.0.1 -P2881 -uroot@sys -p -Doceanbase
```

最小 SQL 验证：

```sql
CREATE TENANT IF NOT EXISTS ob_mysql
  RESOURCE_POOL_LIST = ('pool_mysql')
  SET ob_compatibility_mode = 'mysql';

SELECT * FROM oceanbase.DBA_OB_TENANTS;
```

> 具体镜像标签、默认密码与租户创建方式随版本变化，以官方快速开始为准。

## 参考与官方文档

- [OceanBase 官方文档](https://www.oceanbase.com/docs)
- [OceanBase 社区版 GitHub](https://github.com/oceanbase/oceanbase)
- [OceanBase 快速开始](https://www.oceanbase.com/docs/common-oceanbase-database-cn-10000000001691699)
- [OMS 数据迁移服务](https://www.oceanbase.com/docs/common-oms-cn-10000000001690000)
- [OceanBase 社区问答](https://ask.oceanbase.com/)
