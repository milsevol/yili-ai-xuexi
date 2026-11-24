# 10 开发技巧与 FAQ

## 一句话

把开发企微应用过程中最容易踩的坑、调试技巧、频率限制、沙箱环境、企微 vs 微信开放平台的区别一次性梳理清楚。

## 调试技巧

### 1. 内网穿透是标配

本地开发没有公网 IP，回调 URL 无法被企微访问。推荐工具：

| 工具 | 特点 | 推荐场景 |
| --- | --- | --- |
| **cpolar** | 国内速度快，免费有 5G 流量 | 国内开发者首选 |
| **ngrok** | 国际大牌，免费有 5 次/分钟限制 | 海外开发 |
| **localtunnel** | 纯 Node，无需安装 | 临时用 |
| **花生壳** | 老工具，免费版不稳定 | 不推荐 |

```bash
# cpolar 最简用法
cpolar http 8080
# → https://abc123.r1.cpolar.top → 映射到 localhost:8080

# ngrok
ngrok http 8080
```

### 2. 明文模式跳过加解密

开发阶段先用明文模式，跳过 AES 加解密的坑。跑通主流程后再切安全模式。

### 3. 回调 URL 验证临时 hack

企微首次配置回调 URL 时，会发 GET 验证请求。最简单的后端处理：

```python
# Flask 快速通过验证
@app.route('/api/wecom/callback', methods=['GET', 'POST'])
def callback():
    if request.method == 'GET':
        # 明文模式直接返回 echostr
        return request.args.get('echostr', '')
    else:
        # POST 处理消息
        body = request.data
        # ...
        return 'success'
```

### 4. access_token 缓存可视化

调试时可以把 token 缓存状态打出来：

```python
class WeComTokenManager:
    def __init__(self, ...):
        self._cache = {}  # key: secret → token info

    def debug_status(self):
        for secret, info in self._cache.items():
            remaining = info['expire_at'] - time.time()
            print(f"  {secret[:8]}... 剩余 {remaining:.0f}s 有效")
```

### 5. 用 Postman 直接调 API

access_token 获取、应用消息发送这些 GET/POST 接口都可以直接用 Postman 测试：

```
GET https://qyapi.weixin.qq.com/cgi-bin/gettoken
    ?corpid=你的CorpID
    &corpsecret=你的Secret
```

## 沙箱环境

### 企微沙箱 vs 正式环境

| 对比项 | 沙箱（测试号） | 正式环境 |
| --- | --- | --- |
| **CorpID** | 自动分配 | 企业自己的 |
| **可见范围** | 自动包含创建者 | 需要手动配置 |
| **客户联系** | 不可用 | 可用 |
| **审批模板** | 有限 | 全功能 |
| **API 频率** | 和正式一样 | 每天 2000 次 token |

### 如何申请沙箱

管理员账号登录企微后台 → 「应用管理」→ 「自建应用」→ 底部「获取测试企业信息」。

### 沙箱常见问题

| 问题 | 原因 |
| --- | --- |
| 员工看不到应用 | 沙箱默认只包含创建者，正式环境同样要检查可见范围 |
| 客户联系不可用 | 沙箱不开放客户联系 |
| JS-SDK 签名一直失败 | 沙箱的 corpId 和 jsapi_ticket 和正式环境不同，别混用 |

## 频率限制一览

### 全局频率控制

| 限制项 | 上限 | 说明 |
| --- | --- | --- |
| access_token 获取 | 2000 次/天 | **非常容易踩！** 一定要缓存 |
| 应用消息主动推送 | 200 次/人/天 | 超过后需要用户主动触发 |
| 接口总调用 | 约 100 次/分钟/应用 | 具体各接口不同 |
| 多媒体素材上传 | 200 KB/图片、2 MB/其他 | 上传到 media_id 再发送 |

### 为什么 access_token 有 2000 次/天的限制

企微服务器怕你把它当缓存服务了。正确姿势：**缓存 7100 秒，每天最多调用 12 次**。

```python
# 正确的 token 刷新策略
class TokenManager:
    def __init__(self, secret):
        self.secret = secret
        self._token = None
        self._expire_at = 0

    def get_token(self):
        now = time.time()
        # 提前 100 秒刷新，避免刚好到期
        if not self._token or now >= self._expire_at - 100:
            self._refresh()
        return self._token

    def _refresh(self):
        # 获取一次，7200 秒有效
        # 一个应用一天只需要刷新 ~12 次
        resp = requests.get('https://qyapi.weixin.qq.com/cgi-bin/gettoken',
            params={'corpid': CORP_ID, 'corpsecret': self.secret}).json()
        self._token = resp['access_token']
        self._expire_at = time.time() + resp['expires_in']
```

## 常见坑排查

| 症状 | 可能原因 | 排查方法 |
| --- | --- | --- |
| 员工看不到应用 | 可见范围没配 | 应用详情 → 可见范围，必须包含该员工 |
| 回调 URL 验证失败 | URL 不是 HTTPS / Token 不一致 / 签名算错 | 先明文模式排除加解密，再看签名算法 |
| 消息推送到人但对方收不到 | 24 小时超限 / UserID 写错 / 应用不可见 | 查 errcode：45009=频率限制 |
| JS-SDK 一直 wx.config 失败 | signature 算法错 / URL 含 # 被传进去 | 前端打印当前 URL（不含 #），后端按同样的算 |
| OAuth2 授权后拿不到 UserID | scope 不对 / code 已过期（5 分钟） | snsapi_base 足够拿 UserID，别多请求敏感 scope |
| 审批回调没收到 | 审批模板没开回调 / 事件类型不是 approval | 后台审批模板详情 → 状态变更回调 |
| 客户联系 API 调不通 | 用错 Secret（自建应用的 Secret vs 客户联系的 Secret） | 客户联系有自己的 Secret |
| access_token 获取 42007 | Secret 被重置了 / CorpID 写错 | 去后台重新查看应用 Secret |

### 错误码速查

| errcode | 含义 | 解决 |
| --- | --- | --- |
| 0 | 成功 | — |
| 40001 | access_token 无效 | 刷新 token |
| 40014 | access_token 过期 | 刷新 token |
| 42007 | access_token 超过每日上限 | 明天再来或检查缓存 |
| 45009 | 接口调用频率超限 | 减少调用量，加缓存 |
| 40013 | UserID 无效 | 检查 UserID 是否属于该企业 |
| 40070 | 不合法的 url | OAuth redirect_uri 必须在白名单 |
| 41030 | 不合法的 CorpID | 检查 CorpID 拼写 |
| 41033 | secret 无效 | 检查 Secret 拼写 |

## 企微 vs 微信开放平台

| 维度 | 企业微信开放平台 | 微信开放平台 |
| --- | --- | --- |
| **服务对象** | 企业内部员工 | C 端用户 |
| **身份** | CorpID + UserID | AppID + OpenID |
| **应用类型** | 自建应用 / 微应用 | 公众号 / 小程序 |
| **API 权限** | 通讯录、审批、打卡、客户联系 | 用户信息、模板消息、支付 |
| **用户获取** | OAuth2 → UserID | OAuth2 → OpenID |
| **推送限制** | 200 条/人/天 | 模板消息次数限制 |
| **加密方式** | AES（43 位 Key） | AES（43 位 Key） |

## 开发 Checklist

上线前过一遍：

- [ ] CorpID / AgentID / Secret 都正确，Secret 不提交到 Git
- [ ] 回调 URL（HTTPS）配置正确，明文模式已切成安全模式
- [ ] access_token 有缓存（Redis / 文件 / 内存），不重复获取
- [ ] 应用消息推送有频控保护（200 条/人/天）
- [ ] JS-SDK signature 正确（前端 URL 去掉 # 部分）
- [ ] 应用可见范围包含所有目标用户
- [ ] 通讯录敏感字段（手机号）需要额外授权
- [ ] 回调超时 5 秒内能返回 'success'
- [ ] 所有 API 调用都有错误处理和日志
- [ ] 离职继承流程已配置自动规则

## 自测

1. access_token 的每日获取上限是多少次？正确的缓存策略应该是什么？
2. 企微回调 URL 有哪三种加密模式？开发阶段推荐哪种？
3. JS-SDK 签名失败最常见的原因是什么？怎么排查？
4. 企微和微信开放平台在身份体系上的核心差异是什么？

## 参考与官方文档

- [错误码说明](https://developer.work.weixin.qq.com/document/path/90313)
- [频率限制](https://developer.work.weixin.qq.com/document/path/91770)
- [JS-SDK 签名错误排查](https://developer.work.weixin.qq.com/document/path/94405)
- [企业微信官方文档首页](https://developer.work.weixin.qq.com/document/path/90664)
