# 03 身份认证与 Token

## 一句话

飞书所有 API 调用都要带 `Authorization: Bearer <token>`。token 分三种：**tenant_access_token**（企业自建应用主力）、**app_access_token**（应用身份）、**user_access_token**（用户身份，OAuth 换取）。搞懂这三种 token 的区别和获取方式，是调通一切 API 的前提。

## 三种 Token 对比

| Token | 代表谁 | 用在哪 | 怎么获取 | 有效期 |
| --- | --- | --- | --- | --- |
| **tenant_access_token** | 企业 + 应用 | 绝大多数服务端 API（发消息、读写文档、通讯录…） | App ID + App Secret → `/open-apis/auth/v3/tenant_access_token/internal` | ~2 小时 |
| **app_access_token** | 应用本身（无企业上下文） | 商店应用拿企业授权、发送应用通知等 | App ID + App Secret → `/open-apis/auth/v3/app_access_token/internal` | ~2 小时 |
| **user_access_token** | 具体某个用户 | 以用户身份操作（如代用户发消息、读用户日历） | OAuth2 授权码流程 → `/open-apis/authen/v1/access_token` | ~2 小时，可用 refresh_token 续 |

> 企业自建应用 99% 的场景用 **tenant_access_token**。user_access_token 只在「需要以用户身份操作」时才用。

## 获取 tenant_access_token

这是最常用的 token，代表「你的应用在这个企业里的身份」。

### 请求

```http
POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal
Content-Type: application/json

{
  "app_id": "cli_a1b2c3d4e5f6g7h8",
  "app_secret": "xxxxxxxxxxxxxxxxxxxxxxxx"
}
```

### 响应

```json
{
  "code": 0,
  "msg": "ok",
  "tenant_access_token": "t-g1043d...",
  "expire": 7200
}
```

- `code: 0` 表示成功
- `expire` 单位是秒（7200 = 2 小时）
- token 形如 `t-xxxxxxxx`，调用时放 Header：`Authorization: Bearer t-g1043d...`

### Python 示例（官方 SDK）

```python
import lark_oapi as lark

# 创建客户端（内部应用）
client = lark.Client.builder() \
    .app_id("cli_a1b2c3d4e5f6g7h8") \
    .app_secret("xxxxxxxxxxxxxxxxxxxxxxxx") \
    .build()

# SDK 内部会自动获取并缓存 tenant_access_token，无需手动管理
```

> `lark-oapi` 是飞书官方 Python SDK，自动处理 token 获取、缓存、刷新、重试。强烈建议用 SDK，不要自己裸写 HTTP（除非在学原理）。

## Token 缓存与刷新策略

token 有效期 2 小时，但**不能等到过期才刷新**（高并发下会瞬间大量请求触发频控）。最佳实践：

```
┌──────────────────────────────────────────────────┐
│  Token 缓存策略（推荐 Redis 集中缓存）             │
├──────────────────────────────────────────────────┤
│  1. 本地内存缓存 token + 过期时间                  │
│  2. 多实例部署 → 用 Redis 共享缓存                │
│  3. 过期前 5 分钟主动刷新（留余量）                │
│  4. 刷新加分布式锁（SETNX），避免多实例同时刷新    │
│  5. 接口返回 token 失效错误码时，强制刷新后重试一次│
└──────────────────────────────────────────────────┘
```

**为什么不能每次请求都换 token？** 飞书对获取 token 接口有频控限制，频繁调用会被限流。正确做法是缓存复用。

## user_access_token 与 OAuth2 授权登录

当你需要**以用户身份**操作（比如让用户授权后读取他的日历、代他发消息），就要走 OAuth2 授权码流程拿 user_access_token。

### 授权码模式流程

```
① 用户点击「登录」→ 跳到飞书授权页
   https://open.feishu.cn/open-apis/authen/v1/authorize
     ?app_id=cli_xxx
     &redirect_uri=https://your.com/callback
     &scope=contact:user.base:readonly
     &state=xyz

② 用户确认授权 → 飞书 302 回 redirect_uri?code=xxx&state=xyz

③ 后端用 code 换 user_access_token
   POST /open-apis/authen/v1/access_token
   { "grant_type":"authorization_code", "code":"xxx" }
   → 返回 user_access_token + refresh_token + 用户信息

④ 用 user_access_token 调用「以用户身份」的 API
```

### 换取 user_access_token

```http
POST https://open.feishu.cn/open-apis/authen/v1/access_token
Authorization: Bearer <app_access_token>   ← 注意这里用 app_access_token
Content-Type: application/json

{
  "grant_type": "authorization_code",
  "code": "xMSkq..."
}
```

响应：

```json
{
  "code": 0,
  "data": {
    "access_token": "u-5Td...",
    "refresh_token": "ur-6aB...",
    "expires_in": 7200,
    "refresh_expires_in": 2592000,
    "name": "张三",
    "open_id": "ou_1234...",
    "user_id": "zhangsan"
  }
}
```

### 用 refresh_token 续期

user_access_token 2 小时过期，但 refresh_token 有效期 30 天，可用来刷新：

```http
POST https://open.feishu.cn/open-apis/authen/v1/refresh_access_token
Authorization: Bearer <app_access_token>
{ "grant_type":"refresh_token", "refresh_token":"ur-6aB..." }
```

## JSAPI 鉴权（H5 网页应用）

在飞书客户端内打开 H5 页面时，要调用飞书原生能力（扫码、选人、上传等），需要先做 **JSAPI 鉴权**（类似企业微信的 wx.config）。

```
┌─────────────────────────────────────────────┐
│  H5 JSAPI 鉴权流程                           │
├─────────────────────────────────────────────┤
│  ① 前端把当前页面 URL 发给自己后端            │
│  ② 后端用 tenant_access_token 调             │
│     /open-apis/jssdk/ticket/get 拿 ticket    │
│  ③ 后端算签名：                              │
│     signature = sha1(jsapi_ticket=xxx        │
│       &noncestr=xxx&timestamp=xxx&url=xxx)   │
│  ④ 前端 window.tt.config({...}) 注入鉴权     │
│  ⑤ tt.ready 后调 window.tt.scanQRCode 等     │
└─────────────────────────────────────────────┘
```

> 飞书 H5 JSAPI 命名空间是 `window.tt`（不是 wx）。小程序里也是 `tt` 命名空间。

## 三种用户 ID 的选择

调用 API 时经常要传「用户标识」，飞书有三种，别搞混：

| ID | 唯一性范围 | 说明 | 典型场景 |
| --- | --- | --- | --- |
| **open_id** | 应用内唯一 | 同一个用户在不同应用下 open_id 不同 | 绝大多数 API 默认用它（发消息、通讯录） |
| **user_id** | 企业内唯一 | 同一个用户在整个企业里 user_id 固定 | 企业内部系统对接、和 HR 系统映射 |
| **union_id** | 同开发商多应用唯一 | 同一开发商的多个应用间共享 | ISV 多应用打通用户身份 |

**获取方式**：
- OAuth 登录返回三种 ID
- 通讯录 API 查询成员返回（需对应权限）
- 发消息时 `receive_id_type` 参数指定用哪种 ID 解析

## 自测

1. tenant_access_token、app_access_token、user_access_token 分别代表谁？企业自建应用最常用哪个？
2. 为什么不能每次 API 调用都重新获取 token？正确的缓存策略是什么？
3. OAuth2 授权码流程中，第③步用 code 换 token 时，Authorization 头应该带哪种 token？
4. open_id 和 user_id 有什么区别？你的内部 CRM 系统应该存哪个来和飞书用户做映射？
5. H5 页面要调飞书扫码能力，鉴权流程是怎样的？

## 参考与官方文档

- [获取 tenant_access_token（内部应用）](https://open.feishu.cn/document/server-docs/authentication-management/access-token/tenant_access_token_internal)
- [获取 user_access_token（OAuth 授权码）](https://open.feishu.cn/document/server-docs/authentication-management/access-token/get-user_access_token)
- [刷新 user_access_token](https://open.feishu.cn/document/server-docs/authentication-management/access-token/update-user_access_token)
- [JSAPI 鉴权（H5）](https://open.feishu.cn/document/common-capabilities/jsapi-authentication/overview)
- [用户身份标识说明](https://open.feishu.cn/document/home/user-identity-introduction/introduction)
- [Python SDK lark-oapi](https://github.com/larksuite/oapi-sdk-python)
