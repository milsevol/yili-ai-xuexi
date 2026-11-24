# 05 侧边栏与 JS-SDK

## 一句话

侧边栏是企微的「CRM 嵌入位」：员工在和客户聊天时，右侧弹出你的应用，展示客户资料、历史记录、跟进状态。JS-SDK 让微应用调起企微原生能力（扫码、上传图片、定位、选人等）。

## 侧边栏：企微独有能力

侧边栏是企微区别于普通微信公众号的杀手锏——在聊天窗口直接嵌入业务数据。

### 开启侧边栏

应用详情页 → 「客户联系」→ 「配置客户联系」→ 「客户信息栏」：
- 勾选你的自建应用
- 侧边栏 URL：`https://yourdomain.com/sidebar/customer?external_userid={external_userid}&userid={userid}`

### 侧边栏 URL 参数

| 参数 | 说明 |
| --- | --- |
| external_userid | 当前侧边栏展示的外部客户 ID |
| userid | 当前操作的企业成员 UserID |

### 侧边栏示例：CRM 客户卡片

```html
<!-- 侧边栏 H5 页面 -->
<div class="sidebar">
  <div class="customer-card">
    <div class="avatar">👤</div>
    <div class="info">
      <h3 id="cust-name">加载中...</h3>
      <div class="tags" id="cust-tags"></div>
    </div>
  </div>

  <div class="section">
    <h4>📋 跟进记录</h4>
    <div id="records">暂无记录</div>
    <button onclick="addRecord()">+ 新增跟进</button>
  </div>

  <div class="section">
    <h4>💰 历史订单</h4>
    <div id="orders">查询中...</div>
  </div>
</div>

<script>
  // 企微侧边栏会自动把 external_userid 和 userid 拼在 URL 上
  const params = new URLSearchParams(location.search)
  const external_userid = params.get('external_userid')
  const userid = params.get('userid')

  // 后端 API 查询客户数据
  fetch(`/api/customer/${external_userid}`).then(r => r.json()).then(cust => {
    document.getElementById('cust-name').textContent = cust.name
    // ... 渲染标签、跟进记录、订单
  })
</script>
```

### 侧边栏的触发方式

```
员工在企微聊天窗口
    │
    ├─ 跟外部客户聊天 → 右侧自动弹出「客户信息栏」
    │                      （展示客户联系中配置的应用）
    │
    ├─ 跟内部成员聊天 → 无侧边栏（但可配置）
    │
    └─ 群聊 → 右上角「群信息」→ 可配置群应用
```

## JS-SDK：调起企微原生能力

JS-SDK 是企微给微应用前端的一套 JS API，类似微信公众号的 JSSDK 但能力更强。

### 1. 引入 JS 文件

```html
<script src="https://res.wx.qq.com/open/js/jweixin-1.2.0.js"></script>
<script src="https://open.work.weixin.qq.com/wwopen/js/jwxwork-1.0.0.js"></script>
```

### 2. 前端初始化 wx.config

```javascript
// 前端页面加载时调用
wx.config({
  beta: true,
  debug: false,
  appId: 'CORP_ID',         // 企业 CorpID
  timestamp: 1672531200,
  nonceStr: 'abc123',
  signature: '后端生成的签名',
  jsApiList: [
    'scanQRCode',          // 扫一扫
    'chooseImage',         // 拍照
    'previewImage',        // 预览图片
    'getLocation',         // 获取定位
    'selectEnterpriseContact',  // 选人
    'openDefaultBrowser',  // 用默认浏览器打开
    'hideOptionMenu',      // 隐藏右上角菜单
  ]
})

wx.ready(function () {
  // config 成功后的回调
})

wx.error(function (res) {
  console.error('wx.config 失败:', res)
})
```

### 3. 后端生成签名（关键！）

签名算法和微信公众号 JSSDK 基本一致：

```python
import hashlib

def gen_wx_signature(corp_id, jsapi_ticket, noncestr, timestamp, url):
    """
    1. 拼接字符串：jsapi_ticket=XX&noncestr=XX&timestamp=XX&url=XX
    2. SHA1 加密得到 signature
    """
    string = f"jsapi_ticket={jsapi_ticket}&noncestr={noncestr}&timestamp={timestamp}&url={url}"
    return hashlib.sha1(string.encode()).hexdigest()

# 1. 获取 jsapi_ticket（类似 access_token，也要缓存）
# GET https://qyapi.weixin.qq.com/cgi-bin/get_jsapi_ticket?access_token=TOKEN
# 返回 { "ticket": "xxx", "expires_in": 7200 }

# 2. 传给前端的参数
sign = gen_wx_signature(corp_id, jsapi_ticket, noncestr, timestamp, current_url)
# 返回给前端 { appId, timestamp, nonceStr, signature }
```

> ⚠️ **容易踩的坑**：URL 必须是当前页面的完整 URL（从 `https://` 开始，不含 `#` 及其之后部分），且**必须编码**后再算签名。前端用 `window.location.href.split('#')[0]` 获取。

### 4. 常用 JS-SDK 示例

#### 扫一扫（扫码下单）

```javascript
wx.scanQRCode({
  needResult: 1,          // 0=由企微处理，1=返回结果
  scanType: ['qrCode'],
  success: function (res) {
    const result = res.resultStr  // 扫码结果
    // 处理扫码逻辑，比如跳转到订单页面
    location.href = `/order?code=${encodeURIComponent(result)}`
  }
})
```

#### 拍照上传（报销发票）

```javascript
wx.chooseImage({
  count: 1,
  sizeType: ['compressed'],  // 压缩图，上传快
  sourceType: ['camera', 'album'],
  success: function (res) {
    const localIds = res.localIds  // 本地图片临时路径
    // 上传到你的服务器
    uploadImage(localIds[0]).then(url => {
      document.getElementById('invoice-img').src = url
    })
  }
})
```

#### 获取定位（打卡场景）

```javascript
wx.getLocation({
  type: 'wgs84',
  success: function (res) {
    const lat = res.latitude
    const lng = res.longitude
    // 发送给后端做打卡校验
    fetch('/api/checkin', {
      method: 'POST',
      body: JSON.stringify({ lat, lng })
    })
  }
})
```

#### 选人（审批抄送人）

```javascript
wx.selectEnterpriseContact({
  fromDepartmentId: -1,     // -1=全公司
  mode: 'single',           // single=单选，multi=多选
  type: ['user'],            // user=成员，department=部门
  selectedUserIds: [],
  selectedDepartmentIds: [],
  success: function (res) {
    const users = res.result.userList
    // users = [{ userId: 'UserID1', name: '张三', avatar: '...' }]
    console.log('选中人员:', users)
  }
})
```

## 自定义菜单（微应用底部）

应用详情页 → 「应用主页」→ 「设置菜单」，类似公众号底部菜单：

```json
{
  "button": [
    {
      "name": "首页",
      "type": "single",
      "value": "https://yourdomain.com/app/home"
    },
    {
      "name": "更多",
      "sub_button": [
        {"name": "日报", "type": "single", "value": "https://yourdomain.com/report/daily"},
        {"name": "设置", "type": "single", "value": "https://yourdomain.com/settings"}
      ]
    }
  ]
}
```

也可以通过 API 动态设置菜单：

```bash
POST https://qyapi.weixin.qq.com/cgi-bin/menu/create
  ?access_token=TOKEN&agentid=1000002
  # body 就是上面的 JSON
```

## 应用工具栏按钮

企微 4.0+ 支持在聊天窗口顶部添加「工具栏按钮」，点击后打开你的应用：

管理后台 → 「应用管理」→ 「自建应用」→ 「聊天工具栏」→ 「设置」

## 自测

1. 侧边栏 URL 里有哪两个关键参数？分别代表什么？
2. 前端调 `wx.config` 需要哪些参数？其中 signature 怎么生成？
3. JS-SDK 的 jsapi_ticket 也要缓存吗？为什么？
4. `wx.scanQRCode` 和普通 HTML `<input type="file" capture="camera">` 有什么区别？

## 参考与官方文档

- [企业微信 JS-SDK](https://developer.work.weixin.qq.com/document/path/94225)
- [侧边栏开发](https://developer.work.weixin.qq.com/document/path/92175)
- [自定义菜单](https://developer.work.weixin.qq.com/document/path/93222)
