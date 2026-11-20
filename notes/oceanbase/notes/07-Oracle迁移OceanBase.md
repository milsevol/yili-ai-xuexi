# 07 Oracle 迁移 OceanBase

## 一句话

Oracle 迁移到 OceanBase 的路线是：**先用 OMA/OMS 做兼容性评估 → 建 OceanBase 集群与 Oracle 模式租户 → 用 OMS 做结构迁移、全量迁移、增量同步 → 数据校验 → 割接切换 → 保留反向同步做回滚**。真正的难点不是「数据搬过去」，而是 SQL/PL/SQL 兼容、数据口径一致和回滚预案。

## 迁移全景

```
评估 → POC → 结构迁移 → 全量迁移 → 增量追平 → 数据校验 → 割接切换 → 回滚预案
 │        │        │           │           │           │           │
 │        │        │           │           │           │           └─ OMS 反向增量/双写
 │        │        │           │           │           └─ 行数/汇总/抽样/业务口径
 │        │        │           │           └─ 低延迟同步，等追平
 │        │        │           └─ OMS 全量 + 校验
 │        │        └─ OMS/ODC/手工 DDL，处理不兼容对象
 │        └─ 小范围真实数据验证性能与兼容性
 └─ 对象清单、数据量、语法兼容、改造工作量
```

## 1. 兼容性评估

评估要回答三个问题：

1. **对象能不能迁**：表、分区、索引、约束、视图、序列、同义词、触发器、存储过程、包、DBLink、物化视图等。
2. **SQL 能不能跑**：Oracle 特有语法、函数、Hint、分页、外连接写法。
3. **性能能不能接受**：慢 SQL、大事务、批处理作业、报表查询。

推荐先用 **OMA（OceanBase Migration Assessment）** 扫描源库，输出兼容性报告，再人工复核高风险对象。

### 常见对象支持情况

| Oracle 对象/特性 | OceanBase（Oracle 模式） | 迁移建议 |
| --- | --- | --- |
| 普通表、分区表、约束、索引 | 支持 | 直接迁移，注意分区键与唯一约束 |
| 视图、序列、同义词 | 支持 | 直接迁移 |
| 触发器 | 支持 | 验证触发器内 SQL 与执行顺序 |
| 存储过程/函数 | 大部分支持 | 逐只编译，处理不兼容包与语法 |
| 包（Package） | 大部分支持 | 重点回归包变量、初始化块 |
| DBLink | 支持 | 需配置网络与目标库，跨库性能单独评估 |
| 物化视图 | 支持（刷新机制有差异） | 验证刷新方式与刷新窗口 |
| 索引组织表（IOT） | 不支持 | 改为普通表 + 主键 |
| 外部表 | 受限/不支持 | 改为 OBLoader/ODP 导入或外表方案 |
| 高级队列（AQ） | 不支持 | 改用 Kafka/RocketMQ 等消息中间件 |
| DBMS_SCHEDULER 作业 | 受限 | 迁移到外部调度（DolphinScheduler 等） |
| 自定义对象类型 | 受限 | 拆成普通表/字段或应用层实现 |
| RAC | 不需要 | OB 原生多副本替代 RAC |

> 上表是常见情况，具体以所用版本的官方兼容性说明和实测为准。

### 兼容性重点检查项

| 检查项 | 风险 |
| --- | --- |
| **空串与 NULL** | Oracle 中 `''` 等于 `NULL`，依赖该语义的逻辑要验证 |
| **字符语义** | `VARCHAR2(n)` 默认按字节，中文可能超长 |
| **大小写** | 未加引号的标识符默认大写，加引号则区分大小写 |
| **NUMBER 精度** | 超出精度会报错或截断 |
| **DATE 类型** | Oracle `DATE` 含时分秒；与 `TIMESTAMP` 的转换要统一 |
| **隐式转换** | 字符串与数字、日期的隐式转换结果可能不同 |
| **ROWNUM** | 分页与去重逻辑要逐条验证 |
| **外连接 `(+)`** | 建议改写为 ANSI JOIN，语义更清晰 |
| **Hint** | Oracle Hint 不一定生效，需要重新调优 |
| **长事务/大事务** | OB 对事务大小更敏感，要拆批提交 |

## 2. 环境准备

| 项 | 建议 |
| --- | --- |
| **集群** | 三 Zone 三副本起步；生产按容灾等级规划 |
| **租户** | 创建 **Oracle 模式**租户，字符集建议 `utf8mb4` |
| **用户/权限** | 迁移用户需要建表、建索引、建过程等权限 |
| **网络** | 源库、OMS、目标集群之间网络打通，延迟尽量低 |
| **驱动** | 应用改用 OceanBase Connector/J 或兼容驱动 |
| **连接串** | 通过 OBProxy：`jdbc:oceanbase://host:2883/db`，用户格式 `user@tenant#cluster` |
| **字符集** | Oracle `AL32UTF8` 与 OB `utf8mb4` 对应关系要确认 |
| **时区/NLS** | 统一时区与日期格式，避免数据看起来「差 8 小时」 |

## 3. 结构迁移

方式有三种：

1. **OMS 结构迁移**：自动转换大部分 DDL；
2. **ODC 导入**：适合少量对象与人工调整；
3. **手工 DDL**：复杂对象、分区、存储过程逐个处理。

### DDL 转换示例

```sql
-- Oracle 源表
CREATE TABLE t_order (
  order_id   NUMBER(19)    NOT NULL,
  order_no   VARCHAR2(32)  NOT NULL,
  amount     NUMBER(18,2)  DEFAULT 0 NOT NULL,
  created_at DATE          DEFAULT SYSDATE NOT NULL,
  CONSTRAINT pk_order PRIMARY KEY (order_id)
) PARTITION BY RANGE (created_at) (
  PARTITION p2025 VALUES LESS THAN (DATE '2026-01-01'),
  PARTITION p2026 VALUES LESS THAN (DATE '2027-01-01')
);

-- OceanBase Oracle 模式（基本等价）
CREATE TABLE t_order (
  order_id   NUMBER(19)    NOT NULL,
  order_no   VARCHAR2(32)  NOT NULL,
  amount     NUMBER(18,2)  DEFAULT 0 NOT NULL,
  created_at DATE          DEFAULT SYSDATE NOT NULL,
  CONSTRAINT pk_order PRIMARY KEY (order_id)
) PARTITION BY RANGE (created_at) (
  PARTITION p2025 VALUES LESS THAN (DATE '2026-01-01'),
  PARTITION p2026 VALUES LESS THAN (DATE '2027-01-01')
);
```

大多数简单表可以原样迁移；分区表、全局索引、约束需要逐项确认。

### 结构迁移检查清单

- [ ] 所有表都有主键（无主键表先补主键）
- [ ] 分区键与唯一约束兼容
- [ ] 索引类型与名称符合目标规范
- [ ] 序列缓存与起始值正确
- [ ] 触发器、存储过程、包全部编译通过
- [ ] 同义词、DBLink 指向正确
- [ ] 字符集、时区、日期格式统一
- [ ] 表空间/配额满足容量规划

## 4. 数据迁移（OMS）

OMS 的典型项目流程：

```
新建数据源（Oracle 源 / OB 目标）
  → 新建迁移项目
  → 选择结构迁移 + 全量迁移 + 增量同步
  → 启动预检查
  → 结构迁移
  → 全量迁移
  → 增量同步（LogMiner 解析 Oracle 日志）
  → 数据校验
  → 割接
```

关键配置与注意事项：

| 项 | 说明 |
| --- | --- |
| **并发度** | 根据源库与目标库压力调整，避免打爆生产 |
| **限流** | 全量阶段设置 QPS/带宽上限 |
| **大字段** | LOB 字段迁移更慢，单独评估 |
| **无主键表** | 增量同步困难，必须先补主键 |
| **长事务** | 源库长事务会拖慢增量追平 |
| **断点续传** | 失败后从断点继续，不要盲目重跑全量 |
| **增量延迟** | 持续监控，割接前必须追到接近 0 |

## 5. 数据校验

三段式校验：

| 层级 | 方法 | 说明 |
| --- | --- | --- |
| **行数** | `COUNT(*)` 对比 | 最快，只能发现明显缺失 |
| **汇总** | `SUM`、`MIN`、`MAX`、`COUNT(DISTINCT)` | 发现金额、日期等口径问题 |
| **抽样/全量** | 主键逐行比对、MD5/哈希 | 最可靠，成本最高 |

```sql
-- 源库与目标库分别执行，对比结果
SELECT COUNT(*) AS cnt, SUM(amount) AS amt, MIN(created_at) AS min_t, MAX(created_at) AS max_t
FROM t_order;
```

除了技术校验，还要做**业务口径校验**：核心报表、账务日终、对账文件、接口返回是否一致。技术一致不等于业务一致。

## 6. 割接切换

推荐「短停机窗口 + 增量追平」：

1. 提前完成全量与大部分增量；
2. 选择低峰窗口，暂停源库写入（或应用进入只读）；
3. 等待 OMS 增量延迟归零；
4. 做最后一次校验；
5. 切换应用连接串到 OceanBase；
6. 启动应用，观察错误率、耗时、连接数；
7. 保留 Oracle 只读一段时间，作为回滚兜底。

连接串变化示例：

```properties
# Oracle
jdbc:oracle:thin:@10.0.0.1:1521:ORCL

# OceanBase（经 OBProxy）
jdbc:oceanbase://10.0.0.10:2883/appdb?user=app@ob_orcl#obcluster
```

> 驱动、连接池参数、事务隔离级别、大小写敏感配置都要一起检查，不能只换 URL。

## 7. SQL 与 PL/SQL 改写

| Oracle 写法 | OceanBase 建议 |
| --- | --- |
| `WHERE a.id = b.id(+)` | 改为 `LEFT JOIN` |
| `ROWNUM <= 10` | Oracle 模式通常可用；MySQL 模式用 `LIMIT` |
| `NVL(x, 0)` | Oracle 模式支持；MySQL 模式用 `IFNULL` |
| `DECODE(...)` | Oracle 模式支持；复杂逻辑改 `CASE WHEN` |
| `SELECT ... FROM dual` | Oracle 模式支持 |
| `SYSDATE` | Oracle 模式支持；注意时区 |
| Oracle Hint | 重新评估，OB 优化器不一定识别 |
| `DBMS_*` 高级包 | 逐项确认支持范围，不支持的用应用层替代 |
| Job/调度 | 迁移到外部调度系统 |
| AQ 队列 | 改用 Kafka/RocketMQ |

存储过程迁移建议：

- 先批量编译，收集所有报错；
- 按「被依赖顺序」处理：类型 → 函数 → 过程 → 包 → 触发器；
- 对每个包做单元测试，重点测异常处理与事务边界；
- 避免在过程中依赖 Oracle 特有的隐式行为。

## 8. 性能验证

| 项 | 做法 |
| --- | --- |
| **统计信息** | 迁移后立即收集，避免执行计划走偏 |
| **慢 SQL** | 对比源库 Top SQL，逐条看执行计划 |
| **索引** | 检查索引是否全部迁移、是否被使用 |
| **并行度** | 报表/批处理适当开并行，在线交易慎用 |
| **压测** | 用真实比例数据做读写混合压测 |
| **批处理** | 日终、对账、跑批单独验证窗口是否够 |

## 9. 回滚预案

回滚不是「迁失败了再说」，而是迁移方案的一部分：

| 方案 | 说明 |
| --- | --- |
| **OMS 反向增量** | 割接后把 OceanBase 的变更同步回 Oracle，可快速回切 |
| **双写** | 应用同时写两库，成本高，适合关键系统短期使用 |
| **Oracle 只读保留** | 割接后保留源库一段时间，不做变更 |
| **回滚演练** | 割接前至少演练一次，确认步骤与耗时 |
| **回滚判据** | 明确什么情况必须回滚（错误率、耗时、数据不一致） |

## 10. 常见坑清单

| 坑 | 表现 | 规避 |
| --- | --- | --- |
| 无主键表 | 增量同步无法定位行 | 迁移前补主键 |
| 空串当 NULL | 查询结果与 Oracle 不一致 | 业务逻辑显式处理 NULL |
| 字符长度按字节 | 中文插入报超长 | 用 `CHAR` 语义或扩大长度 |
| 日期时区 | 数据差 8 小时 | 统一时区与 NLS 设置 |
| 大小写 | 表名/字段名找不到 | 统一不加引号或统一加引号 |
| 序列缓存 | 切换后序列跳号/冲突 | 校准起始值与缓存 |
| 大事务 | 迁移或业务报错 | 拆批提交 |
| 统计信息缺失 | 执行计划全表扫描 | 迁移后立即收集 |
| 驱动不兼容 | 连接失败或功能异常 | 使用官方推荐驱动 |
| 未做恢复演练 | 出问题不会恢复 | 备份 + 恢复演练常态化 |

## 迁移检查清单（可打印）

- [ ] 完成对象清单与兼容性评估
- [ ] 完成 POC，核心业务跑通
- [ ] OceanBase 集群、租户、用户、白名单就绪
- [ ] 结构迁移完成，所有对象编译通过
- [ ] 全量迁移完成，行数与汇总校验通过
- [ ] 增量同步延迟稳定，割接前归零
- [ ] 关键表抽样/全量校验通过
- [ ] 业务报表与对账口径一致
- [ ] 应用连接串、驱动、连接池切换完成
- [ ] 性能压测与批处理窗口验证通过
- [ ] 回滚方案与演练完成
- [ ] 监控、告警、备份已配置

## 自测

1. Oracle 迁移 OceanBase 的完整阶段有哪些？
2. 为什么无主键表会成为迁移的硬伤？
3. 数据校验为什么要做行数、汇总、抽样三层？
4. 割接后如何保证可以快速回滚？
5. 列举三个 Oracle 与 OceanBase 容易产生语义差异的点。

## 参考与官方文档

- [OMS 数据迁移服务文档](https://www.oceanbase.com/docs/common-oms-cn-10000000001690000)
- [OMA 迁移评估工具](https://www.oceanbase.com/docs/common-oceanbase-database-cn-10000000001692000)
- [Oracle 兼容性说明](https://www.oceanbase.com/docs/common-oceanbase-database-cn-10000000001692010)
- [OceanBase 迁移最佳实践](https://www.oceanbase.com/docs/common-oceanbase-database-cn-10000000001692020)
- [OceanBase Connector/J](https://www.oceanbase.com/docs/common-oceanbase-connector-j-cn-10000000001690000)
