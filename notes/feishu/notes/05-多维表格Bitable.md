# 05 多维表格 Bitable

## 一句话

多维表格（Bitable）是飞书的「在线数据库 + 电子表格」混血：有表、字段、记录、视图，支持多人实时协作，又能通过 API 当数据库用。它是飞书最具差异化的能力，也是**低成本搭建业务系统**的神器。

## 多维表格是什么

| 类比 | 多维表格里叫什么 | 说明 |
| --- | --- | --- |
| 数据库的「库」 | 多维表格 App | 一个独立的多维表格文件，有 app_token |
| 数据库的「表」 | 数据表 Table | 一个 App 里可建多张表，有 table_id |
| 数据库的「列」 | 字段 Field | 有类型（文本/数字/单选/日期/人员…），有 field_id |
| 数据库的「行」 | 记录 Record | 一行数据，有 record_id |
| 数据库的「视图」 | 视图 View | 同一张表的不同展示方式（表格/看板/甘特/画册） |
| Excel 的公式 | 公式字段 | 基于其他字段计算，支持函数 |

```
多维表格 App (app_token)
 └─ 数据表 Table (table_id)
     ├─ 字段 Field (field_id)  ← 列定义
     ├─ 记录 Record (record_id) ← 行数据
     └─ 视图 View (view_id)     ← 展示方式
```

## 核心 ID 体系

调用 Bitable API 经常要传这几个 ID：

| ID | 在哪看 | 示例 |
| --- | --- | --- |
| **app_token** | 多维表格 URL 里 `/base/` 后面那段 | `https://xxx.feishu.cn/base/`**`bascnXXXX`** |
| **table_id** | API 返回 / URL 参数 `?table=` | `tblXXXX` |
| **field_id** | API 返回 | `fldXXXX` |
| **record_id** | API 返回 / URL 参数 `?record=` | `recXXXX` |
| **view_id** | API 返回 | `vewXXXX` |

> 这些 ID 建议在你的系统里**持久化存下来**，不要每次都靠查。新建表/字段时 API 会返回对应 ID。

## 字段类型

多维表格支持丰富的字段类型，选对类型才能正确读写：

| 字段类型 | type 值 | 写入值格式 | 说明 |
| --- | --- | --- | --- |
| 多行文本 | `text` | `"hello"` 或 `[{type:text,text:...}]` | 默认 |
| 数字 | `number` | `100` | 可设小数位、千分位 |
| 单选 | `select` | `"选项名"` | 选项需预先存在 |
| 多选 | `multi_select` | `["选项A","选项B"]` | |
| 日期 | `date` | `1700000000000`（毫秒时间戳） | |
| 复选框 | `checkbox` | `true` / `false` | |
| 人员 | `user` | `[{id:"ou_xxx"}]` | 按 open_id |
| 超链接 | `url` | `{link:"https://...", text:"显示"}` | |
| 电话 | `phone` | `"13800138000"` | |
| 邮箱 | `email` | `"a@b.com"` | |
| 附件 | `attachment` | `[{file_token:"xxx"}]` | 先上传文件拿 token |
| 公式 | `formula` | （只读，由公式计算） | 不能写，只能读 |
| 单向关联 | `link` | `["recXXX"]` | 关联另一条记录 |
| 查找引用 | `lookup` | （只读） | 从关联表取数 |

## Bitable 常用 API

所有接口前缀：`/open-apis/bitable/v1`，需带 `Authorization: Bearer <tenant_access_token>` 和对应 scope。

### 1. 列出应用下的数据表

```http
GET /open-apis/bitable/v1/apps/{app_token}/tables
```

### 2. 新增一条记录

```http
POST /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records
{
  "fields": {
    "标题": "客户拜访记录",
    "客户名称": "字节跳动",
    "拜访日期": 1700000000000,
    "跟进人": [{ "id": "ou_xxx" }],
    "状态": "已完成"
  }
}
```

响应返回 `record_id`，存下来后续更新用。

### 3. 批量新增记录（推荐，减少 API 调用）

```http
POST /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create
{
  "records": [
    { "fields": { "标题": "记录1" } },
    { "fields": { "标题": "记录2" } }
  ]
}
```

> 批量接口一次最多 500 条，超限分批。

### 4. 查询记录（带过滤、排序、分页）

```http
GET /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records
  ?page_size=100
  &filter=CurrentValue.[状态]="待跟进"
  &sort=创建时间 DESC
```

返回带 `has_more` + `page_token` 用于翻页。

### 5. 更新记录

```http
PUT /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}
{ "fields": { "状态": "已签约" } }
```

### 6. 新建字段 / 新建数据表

```http
POST /open-apis/bitable/v1/apps/{app_token}/tables   // 新建表
POST /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields  // 新建字段
```

## 自动化流程

多维表格内置「自动化」能力，无需写代码就能触发：

| 触发条件 | 执行动作 |
| --- | --- |
| 新增记录时 | 发飞书消息 / 发邮件 / 调用 webhook |
| 记录满足条件时 | 更新其他记录 / 创建关联记录 |
| 定时触发 | 发送日报卡片 / 同步数据 |
| 按钮点击时 | 自定义动作 |

> 自动化里的「调用 webhook」可以把多维表格的数据推到你自己的后端，实现「表格即数据库，变更即事件」。

## Python 集成实战：用多维表格当 CRM

用官方 SDK 读写多维表格，把它当成轻量 CRM：

```python
import lark_oapi as lark
from lark_oapi.api.bitable.v1 import *

client = lark.Client.builder().app_id("cli_xxx").app_secret("xxx").build()

APP_TOKEN = "bascnXXXX"
TABLE_ID = "tblXXXX"

# 新增一条客户跟进记录
req = CreateAppTableRecordRequest.builder() \
    .app_token(APP_TOKEN) \
    .table_id(TABLE_ID) \
    .request_body(AppTableRecord.builder()
        .fields({
            "客户名称": "某科技公司",
            "跟进状态": "初次接触",
            "跟进人": [{"id": "ou_xxx"}],
        }).build()) \
    .build()

resp = client.bitable.v1.app_table_record.create(req)
if resp.success():
    print("record_id:", resp.data.record.record_id)
else:
    print(resp.code, resp.msg)
```

## 多维表格 vs 传统数据库

| 维度 | 多维表格 Bitable | 传统数据库（MySQL） |
| --- | --- | --- |
| 定位 | 协作型轻量数据层 | 严肃业务存储 |
| 上手成本 | 极低，非技术也能建表 | 需 DBA / 写 DDL |
| 并发写入 | 适合百人级协作 | 适合高并发事务 |
| 数据量 | 单表建议 10 万行内 | 千万级无压力 |
| 关联查询 | 单向/双向关联、lookup | JOIN / 外键 |
| API | RESTful，开箱即用 | 需要自己写服务层 |
| 适合 | 内部工具、运营看板、轻 CRM/工单 | 核心交易、高并发系统 |

> 最佳实践：多维表格做「业务协作层 + 可视化」，核心数据同步到传统数据库做分析与备份。

## 自测

1. 多维表格的 app_token、table_id、record_id 分别怎么获取？为什么要持久化存？
2. 往「日期」字段和「人员」字段写值，格式分别是什么？
3. 为什么推荐用批量接口（batch_create）而不是循环单条新增？
4. 公式字段和查找引用字段为什么不能通过 API 写入？
5. 多维表格适合做核心交易系统的数据库吗？它的定位边界在哪？

## 参考与官方文档

- [多维表格 API 总览](https://open.feishu.cn/document/server-docs/docs/bitable-v1/bitable-overview)
- [多维表格字段类型](https://open.feishu.cn/document/server-docs/docs/bitable-v1/bitable-structure)
- [记录操作 API](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/create)
- [自动化流程](https://www.feishu.cn/hc/zh-CN/articles/360049067836)
- [Python SDK Bitable 示例](https://github.com/larksuite/oapi-sdk-python)
