# 11 实战与 FAQ

## 一句话

把前面 10 章的能力串成一个真实项目：「**审批驱动的费用管理机器人**」—— 员工在飞书提报销 → 走飞书审批 → 通过后自动写多维表格台账 + 生成文档凭证 + 通知到群。再附上调试技巧、错误码速查、频控应对和上线 Checklist。

## 实战：审批驱动的费用管理机器人

### 业务目标

- 员工在飞书「报销」审批模板提单
- 审批通过后，自动：① 写入多维表格台账 ② 生成报销凭证文档 ③ 通知报销人和财务群
- 财务在多维表格里就能看全量报销数据、做统计

### 架构与链路

```
┌──────────┐   提交审批    ┌──────────────┐
│  员工飞书  │ ──────────▶ │  飞书审批引擎  │
└──────────┘              └──────┬───────┘
                                │ 审批通过事件
                                ▼
                    ┌───────────────────────┐
                    │  你的后端（事件消费）    │
                    │  ① 收 approval_instance│
                    │  ② 查审批实例详情       │
                    │  ③ 写多维表格台账       │
                    │  ④ 生成 docx 凭证       │
                    │  ⑤ 发消息卡片通知       │
                    └───────────┬───────────┘
                                │
            ┌───────────────────┼───────────────────┐
            ▼                   ▼                   ▼
     ┌────────────┐      ┌────────────┐      ┌────────────┐
     │ 多维表格台账 │      │ 报销凭证文档 │      │ 消息卡片通知 │
     │ (Bitable)  │      │  (docx)    │      │ (员工+财务群)│
     └────────────┘      └────────────┘      └────────────┘
```

### 关键实现步骤

**Step 1：配置审批与事件**
- 飞书管理后台创建「报销」审批模板，记下 `approval_code`
- 开发者后台给应用勾选审批 scope，订阅事件 `approval_instance`
- 用 WebSocket 方式接收事件（本地开发免内网穿透）

**Step 2：事件消费（Python SDK 示例）**

```python
import lark_oapi as lark
from lark_oapi.api.im.v1 import *
from lark_oapi.api.bitable.v1 import *

client = lark.Client.builder().app_id("cli_xxx").app_secret("xxx").build()

# 注册审批事件处理器
def handle_approval_event(data):
    event = data.event
    if event.type == "approval_instance" and event.approval_code == "你的模板code":
        if event.status == "APPROVED":
            # 1. 查审批实例详情拿表单数据
            # 2. 写多维表格台账
            # 3. 生成凭证文档
            # 4. 发消息卡片
            ...

# 飞书 SDK 的事件处理（WSS 模式）
event_handler = lark.EventDispatcherHandler.builder("", "") \
    .register_p2_im_message_receive_v1(handle_msg) \
    .build()
ws_client = lark.ws.Client("cli_xxx", "xxx", event_handler=event_handler)
ws_client.start()
```

**Step 3：写多维表格台账**（调用第 05 章的 batch_create）

**Step 4：生成 docx 凭证**（调用第 06 章的 documents + blocks children）

**Step 5：发卡片通知**（调用第 04 章，卡片带文档链接 + 「查看台账」按钮）

### 收益

- 员工：只在飞书提单，不用切换系统
- 财务：台账自动沉淀到多维表格，可实时筛选/统计/看板
- 凭证：自动生成文档，可归档可追溯

## 调试技巧

### 1. 事件订阅收不到？

| 排查项 | 做法 |
| --- | --- |
| HTTP 回调模式 | ① curl 测回调 URL 公网可访问 ② 后台「事件与回调」点「重试」看报错 ③ 检查是否返回了 challenge ④ 检查签名/加密配置是否匹配 |
| WebSocket 模式 | ① 看 SDK 日志是否连上 WSS ② 确认应用有订阅该事件 ③ 确认事件有实际触发（如真的发了消息） |
| 通用 | 后台「事件与回调 → 事件跟踪」能看到事件投递记录和失败原因 |

### 2. 本地联调推荐 WebSocket

飞书的 WebSocket 长连接事件订阅是**开发利器**：本地代码直接连飞书，无需公网 IP / 内网穿透，改完代码重启即生效。强烈建议开发阶段用 WSS，上线再按需切 HTTP 回调。

### 3. API 调试台

开发者后台每个 API 文档页都有「**调试台**」：填参数、选 token 就能直接发请求看响应。排查「是参数错了还是逻辑错了」时先用调试台验证接口本身能通。

### 4. 开全量日志

SDK 可配置日志级别，把请求 URL、请求体、响应体打出来，对照错误码排查：

```python
client = lark.Client.builder() \
    .app_id("...").app_secret("...") \
    .log_level(lark.LogLevel.DEBUG) \
    .build()
```

## 常见错误码速查

> 飞书错误码以 `code` 字段返回，`code == 0` 为成功。具体数值以[官方错误码文档](https://open.feishu.cn/document/server-docs/api-call-guide/server-error-code)为准，下表为高频场景排查方向。

| code | 含义 | 排查方向 |
| --- | --- | --- |
| `0` | success | 成功 |
| `99991663` / `99991664` | token 无效 / 失效 | token 过期没刷新、App Secret 被重置、用错 token 类型（该用 tenant 用了 user） |
| `99991668` | app_ticket 失效 | 商店应用场景，app_ticket 没正确接收/缓存 |
| `230002` | 无权限发送消息 | 接收者不在应用可见范围 / 没勾选 im 消息权限 / 权限没重新发布生效 |
| `230001` | 消息内容错误 | `msg_type` 与 `content` 不匹配、content 没转成字符串、卡片 JSON 格式错 |
| `230020` / `230021` | 卡片内容错 / 机器人不在群 | 卡片 JSON 校验失败；发群消息但机器人没进群 |
| `1061001` | 参数错误 | 必填参数缺失、类型不对、ID 格式错（如 open_id 写成 user_id） |
| `1061002` / `1061003` | 权限不足 | 没勾对应 scope / 勾了但没重新发版 / 敏感权限需管理员授权 |
| `1254001` 系列 | 多维表格相关 | app_token/table_id 不存在、字段名/字段类型不匹配、记录超量 |

**排查通用套路**：拿到 `code` → 查错误码文档看含义 → 对照 `msg` 字段 → 用调试台复现 → 定位是参数、权限还是配置问题。

## 频控与配额

飞书按接口维度设有限频，超限会返回特定错误码：

| 限制类型 | 说明 | 应对 |
| --- | --- | --- |
| QPS（每秒） | 单接口每秒请求数上限 | 客户端加令牌桶限流 |
| 分钟/天级 | 部分接口有更慢周期的量限制 | 批量接口、错峰、缓存 |
| 获取 token 接口 | 不能高频刷 | 必须缓存 token，提前刷新 |
| 消息接收者 | 单用户每天接收应用消息上限 | 合并消息、卡片摘要、错峰 |

**最佳实践**：
- token 必须缓存（Redis），提前 5 分钟刷新
- 写操作优先用批量接口（batch_create / batch_update）
- 对失败重试用指数退避（1s → 2s → 4s），避免雪崩
- 监控调用量，接近上限时告警

## 上线前 Checklist

```
□ 凭证安全：App Secret 存环境变量/密钥管理，不进 Git、不进前端
□ 权限最小化：只勾选实际用到的 scope，敏感权限已获管理员授权
□ 版本发布：线上版已包含所有配置/权限，可见范围正确
□ 事件订阅：回调/WSS 稳定运行，有失败重试与告警
□ Token 缓存：已接入 Redis 缓存 + 过期前刷新 + 分布式锁
□ 错误处理：接口失败有重试/降级，用户侧有友好提示
□ 频控预估：估算调用量，确认在配额内，有限流保护
□ 日志监控：关键链路（发消息、写表、审批回调）有日志和监控
□ 数据备份：多维表格/文档数据有定期导出备份
□ 安全：回调验签开启、Webhook 机器人配置签名校验
□ 灰度：先小范围（IT/本部门）灰度，再全量放开
```

## FAQ

**Q：自建应用和商店应用（ISV）到底怎么选？**
A：只给自己企业用 → 自建应用（简单、免商店审核）。要做成 SaaS 卖给别的企业 → 商店应用（需走多租户授权：企业管理员安装授权 → 你拿 app_access_token + 企业授权码管理每个租户）。

**Q：为什么我调 API 总是返回「权限不足」，明明后台勾了 scope？**
A：勾选 scope 后必须**创建新版本并发布**，线上版才会生效。开发版和线上版权限是隔离的。另外敏感权限（手机/邮箱/考勤）需要企业管理员在后台单独点「授权」。

**Q：发消息提示「接收者不在应用可用范围」？**
A：应用发布时配置了「可用范围」，目标用户不在范围内就发不了。去后台「应用发布 → 可用范围」把目标用户/部门加进去。

**Q：HTTP 回调和 WebSocket 能同时用吗？**
A：可以同时配置，但同一个事件会被推两次，容易重复处理。建议生产选一种。开发用 WSS，生产量大且需要独立公网服务时可用 HTTP 回调。

**Q：多维表格能当核心数据库吗？**
A：不建议。多维表格适合协作层和轻量业务，单表数据量、并发写入、复杂查询都有限。核心交易数据建议存传统数据库，多维表格做展示/协作层并双向同步。

**Q：token 泄露了怎么办？**
A：立即去开发者后台「凭证与基础信息」重置 App Secret，旧 token 立刻全部失效。再排查泄露原因（是否进了 Git、是否在前端代码）。

## 自测

1. 本地开发调试事件订阅，推荐用 HTTP 回调还是 WebSocket？为什么？
2. 调 API 返回「权限不足」，但后台已经勾了 scope，最可能的原因是什么？
3. 发消息失败提示接收者不在可用范围，怎么解决？
4. 上线前你认为最重要的 3 项 Checklist 是什么？为什么？
5. App Secret 泄露后的应急处置步骤是什么？

## 参考与官方文档

- [飞书开放平台首页](https://open.feishu.cn/)
- [服务端错误码大全](https://open.feishu.cn/document/server-docs/api-call-guide/server-error-code)
- [频控说明](https://open.feishu.cn/document/server-docs/api-call-guide/rate-limit-overview)
- [API 调试台使用](https://open.feishu.cn/document/server-docs/api-call-guide/api-debugger)
- [事件订阅最佳实践](https://open.feishu.cn/document/server-docs/event-subscription-guide/best-practice)
- [商店应用（ISV）开发](https://open.feishu.cn/document/home/introduction-to-capability-platform/isv-app-creation-process)
