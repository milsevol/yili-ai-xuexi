# 05 SQL 与兼容模式

## 一句话

OceanBase 在**建租户时**选择 MySQL 模式或 Oracle 模式：MySQL 模式兼容 MySQL 协议与语法，Oracle 模式兼容 Oracle 的 SQL、PL/SQL、数据字典与常用对象。两种模式共享同一套分布式内核，但 SQL 方言、数据类型、系统视图不同。

## 两种模式对比

| 维度 | MySQL 模式 | Oracle 模式 |
| --- | --- | --- |
| **协议** | MySQL 协议 | Oracle 兼容协议（OBClient/ODC） |
| **客户端** | mysql / JDBC / MyBatis | OBClient / ODC / Oracle 风格 JDBC |
| **默认 Schema** | Database | Schema/User |
| **分页** | `LIMIT offset, size` | `ROWNUM` / `FETCH FIRST` |
| **自增** | `AUTO_INCREMENT` | `SEQUENCE` + `NEXTVAL` |
| **字符串** | `VARCHAR` | `VARCHAR2` |
| **数字** | `INT` / `DECIMAL` | `NUMBER` |
| **系统视图** | `information_schema` / `SHOW` | `ALL_*` / `USER_*` / `DBA_*` / `V$*` |
| **PL/SQL** | 存储过程、函数、触发器 | 存储过程、函数、包、触发器、同义词 |
| **空串** | 空串是空串 | 空串按 `NULL` 处理（Oracle 语义） |

> 兼容模式创建后不可修改。需要两种模式就建两个租户。

## 数据类型速查

| 场景 | MySQL 模式 | Oracle 模式 |
| --- | --- | --- |
| 整数 | `TINYINT` / `INT` / `BIGINT` | `NUMBER(p,0)` |
| 小数 | `DECIMAL(p,s)` | `NUMBER(p,s)` |
| 字符串 | `VARCHAR(n)` / `TEXT` | `VARCHAR2(n)` / `CLOB` |
| 日期时间 | `DATETIME` / `TIMESTAMP` | `DATE` / `TIMESTAMP` |
| 布尔 | `TINYINT(1)` | `NUMBER(1)` |
| 二进制 | `VARBINARY` / `BLOB` | `RAW` / `BLOB` |
| JSON | `JSON` | `JSON`（按版本支持） |

字符长度语义要注意：Oracle 的 `VARCHAR2(10)` 默认按**字节**计算，`VARCHAR2(10 CHAR)` 才按字符。迁移时如果源库是字节语义，目标库也要保持一致，否则中文可能超长。

## 建表与分区

```sql
-- MySQL 模式：按用户 ID 哈希分区
CREATE TABLE t_order (
  order_id   BIGINT       NOT NULL,
  user_id    BIGINT       NOT NULL,
  amount     DECIMAL(18,2) NOT NULL,
  created_at DATETIME     NOT NULL,
  PRIMARY KEY (order_id)
) PARTITION BY HASH(user_id) PARTITIONS 16;

-- Oracle 模式：按范围分区
CREATE TABLE t_order (
  order_id   NUMBER(19)    NOT NULL,
  user_id    NUMBER(19)    NOT NULL,
  amount     NUMBER(18,2)  NOT NULL,
  created_at DATE          NOT NULL,
  CONSTRAINT pk_order PRIMARY KEY (order_id)
) PARTITION BY RANGE (created_at) (
  PARTITION p2025 VALUES LESS THAN (DATE '2026-01-01'),
  PARTITION p2026 VALUES LESS THAN (DATE '2027-01-01')
);
```

支持的常见分区方式：RANGE、RANGE COLUMNS、LIST、HASH、KEY、复合分区。分区是 OceanBase 水平扩展与裁剪的基础。

## 索引

| 类型 | 说明 |
| --- | --- |
| **主键索引** | 聚簇索引，决定数据物理顺序 |
| **普通索引 / 唯一索引** | 二级索引 |
| **局部索引** | 与分区一一对应，分区维护简单 |
| **全局索引** | 跨分区唯一，查询灵活但维护成本高 |
| **函数索引** | 对表达式建索引，适合固定函数查询 |

```sql
-- 局部索引（默认）
CREATE INDEX idx_order_user ON t_order(user_id) LOCAL;

-- 全局唯一索引
CREATE UNIQUE INDEX uk_order_no ON t_order(order_no) GLOBAL;
```

> 分区表上的唯一约束必须包含分区键，否则需要用全局索引。

## 常用对象

```sql
-- 序列（Oracle 模式）
CREATE SEQUENCE seq_order_id START WITH 1 INCREMENT BY 1 CACHE 100;
SELECT seq_order_id.NEXTVAL FROM dual;

-- 同义词（Oracle 模式）
CREATE SYNONYM t_order FOR app.t_order;

-- 存储过程（Oracle 模式）
CREATE OR REPLACE PROCEDURE p_close_order(p_id IN NUMBER) IS
BEGIN
  UPDATE t_order SET status = 'CLOSED' WHERE order_id = p_id;
  COMMIT;
END;
/

-- 触发器（MySQL 模式）
CREATE TRIGGER trg_order_bi BEFORE INSERT ON t_order
FOR EACH ROW SET NEW.created_at = IFNULL(NEW.created_at, NOW());
```

## 系统视图与诊断

| 用途 | MySQL 模式 | Oracle 模式 |
| --- | --- | --- |
| 当前租户 | `SELECT * FROM oceanbase.DBA_OB_TENANTS` | 同左（OceanBase 自有视图通用） |
| 表信息 | `SHOW TABLES` / `information_schema.tables` | `USER_TABLES` / `ALL_TABLES` |
| 执行计划 | `EXPLAIN` | `EXPLAIN PLAN FOR` |
| 慢 SQL | `GV$OB_SQL_AUDIT` | `GV$OB_SQL_AUDIT` |
| 会话 | `SHOW PROCESSLIST` | `V$SESSION` |
| 参数 | `SHOW PARAMETERS` | `SHOW PARAMETERS` |

```sql
-- 最近 10 条慢 SQL（通用）
SELECT SVR_IP, TENANT_NAME, SQL_ID, ELAPSED_TIME, QUERY_SQL
FROM oceanbase.GV$OB_SQL_AUDIT
ORDER BY ELAPSED_TIME DESC
LIMIT 10;
```

## HTAP：行存与列存

OceanBase 4.3 起支持列存能力，可以为表或副本指定列存，用于实时分析：

```sql
-- 建表时指定列存（具体语法随版本变化）
CREATE TABLE t_trade (
  trade_id BIGINT,
  account_id BIGINT,
  amount DECIMAL(18,2),
  trade_time DATETIME
) WITH COLUMN GROUP (ALL COLUMNS);
```

典型用法：交易主表保持行存承载 OLTP，分析场景使用列存副本或列存表，避免把数据同步到外部 OLAP 系统。

## SQL 使用注意事项

| 注意点 | 说明 |
| --- | --- |
| **大事务** | 单事务过大占用内存与日志，建议拆批提交 |
| **无主键表** | 迁移与复制困难，生产表必须有主键 |
| **隐式转换** | 索引列上做函数或类型转换会导致索引失效 |
| **分页深翻** | `LIMIT 1000000, 20` 扫描量大，用游标或延迟关联 |
| **统计信息** | 数据变化大时及时收集，否则执行计划可能走偏 |
| **绑定变量** | 高频 SQL 用绑定变量，避免计划缓存膨胀 |

## 常见问题

**Q：MySQL 模式能直接跑 MySQL 的存储过程吗？**
A：大部分可以，但 OceanBase 的实现与 MySQL 存在差异，复杂存储过程需要测试。

**Q：Oracle 模式下 `''` 和 `NULL` 一样吗？**
A：一样，遵循 Oracle 语义。迁移时依赖「空串」与 `NULL` 区分的逻辑要重点检查。

**Q：两种模式能互相访问吗？**
A：可以通过 DBLink 等方式跨租户访问，但性能和权限模型要单独评估。

## 自测

1. MySQL 模式和 Oracle 模式的主要差异有哪些？
2. 分区表上的唯一索引有什么限制？
3. 为什么生产表要求必须有主键？
4. 列存适合什么场景？和行存怎么配合？

## 参考与官方文档

- [OceanBase SQL 参考（MySQL 模式）](https://www.oceanbase.com/docs/common-oceanbase-database-cn-10000000001691800)
- [OceanBase SQL 参考（Oracle 模式）](https://www.oceanbase.com/docs/common-oceanbase-database-cn-10000000001691850)
- [分区表](https://www.oceanbase.com/docs/common-oceanbase-database-cn-10000000001691730)
- [索引管理](https://www.oceanbase.com/docs/common-oceanbase-database-cn-10000000001691732)
- [HTAP 与列存](https://www.oceanbase.com/docs/common-oceanbase-database-cn-10000000001691735)
