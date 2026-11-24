# 企业微信应用开发

企业微信（WeCom）是腾讯面向企业的通讯协作平台，开放 API 让企业内部系统嵌入 IM 能力、OA 审批、客户管理、侧边栏轻应用。本主题用中文笔记 + **浏览器可视化交互演示**，梳理企微应用开发「是什么 → 怎么注册 → 消息收发 → 客户联系 → 侧边栏 JS-SDK → 审批打卡 → 通讯录 OAuth → 微应用/小程序 → 实战案例 → 调试 FAQ → 管理后台运维」的完整链路。

> 版本参考：以 **企微 4.0 最新 API** 为准，示例以 Python 后端 + H5 微应用为主。演示不连接真实企业微信；默认打开 `demos/index.html`。

## 先决知识

- 知道什么是「微信公众号 / 小程序」，对开放平台有基本概念更佳
- 会一点 Python 或 Node.js（读 API 调用示例用）
- 理解 HTTP、JSON、OAuth2、回调通知等基础概念更佳

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位.md) | `./start.sh 01` | 企微 vs 微信 vs 钉钉、开放能力全景、开发链路总览 |
| 2 | [02-应用注册与配置](./notes/02-应用注册与配置.md) | `./start.sh 02` | CorpID/AgentID/Secret 三要素、回调 URL 验证、access_token 缓存 |
| 3 | [03-消息收发机制](./notes/03-消息收发机制.md) | `./start.sh 03` | 回调接收消息、事件通知、主动推送、频控限制 |
| 4 | [04-客户联系与客户群](./notes/04-客户联系与客户群.md) | `./start.sh 04` | 客户联系 API、标签管理、客户群、离职继承、SCRM 场景 |
| 5 | [05-侧边栏与JS-SDK](./notes/05-侧边栏与JS-SDK.md) | `./start.sh 05` | 侧边栏配置、wx.config 签名生成、扫码/上传/定位/选人 JS-SDK |
| 6 | [06-审批与打卡集成](./notes/06-审批与打卡集成.md) | `./start.sh 06` | 审批模板、审批回调、审批实例 API、打卡数据 |
| 7 | [07-通讯录与身份验证](./notes/07-通讯录与身份验证.md) | `./start.sh 07` | 通讯录 API、OAuth2 网页授权、敏感数据权限、UserID/OpenID 转换 |
| 8 | [08-微应用与小程序](./notes/08-微应用与小程序.md) | `./start.sh 08` | 微应用 vs 小程序 vs 第三方应用、小程序登录、订阅消息 |
| 9 | [09-企业内部实战案例](./notes/09-企业内部实战案例.md) | `./start.sh 09` | 客户跟进助手全流程：侧边栏 CRM + 审批流 + 沉睡客户提醒 + AI 接入 |
| 10 | [10-开发技巧与FAQ](./notes/10-开发技巧与FAQ.md) | `./start.sh 10` | 内网穿透、沙箱、错误码、频控、常见坑排查、上线 Checklist |
| 11 | [11-管理后台常见操作](./notes/11-管理后台常见操作.md) | `./start.sh 11` | 管理员体系、超级/分级管理员设置、通讯录、应用、客户联系、安全、审计 |

建议：01–02 建立开发环境；03 是消息/回调核心；04–07 是企微独有的能力（客户联系、侧边栏、审批、通讯录、OAuth）；08 讲前端形态选择；09 实战串联；10 做上线前检查；11 面向管理员/运维同学。

## 如何启动演示

```bash
cd notes/wecom-app
./start.sh          # 浏览器可视化交互
./start.sh 02       # 直达应用注册与配置
./start.sh --cli    # 备用终端文字版
```

也可从仓库根进入：`python3 main.py wecom-app`。

## 本地开发快速上手

### 1. 注册企业微信

个人也可以注册试用：https://work.weixin.qq.com/

### 2. 获取三要素

- **CorpID**：管理后台 → 我的企业 → 企业信息
- **AgentID**：创建自建应用后自动生成
- **Secret**：自建应用详情页 → 查看（管理员扫码）

### 3. 内网穿透

```bash
cpolar http 8080        # 国内推荐
# 或
ngrok http 8080
```

### 4. 最小 Flask 后端

```bash
pip install flask requests pycryptodome
python -m pip install pycryptodome  # AES 加解密
```

## 参考与官方文档

- [企业微信开发文档](https://developer.work.weixin.qq.com/document/path/90664)
- [API 列表](https://developer.work.weixin.qq.com/document/path/90235)
- [错误码说明](https://developer.work.weixin.qq.com/document/path/90313)
- [管理后台](https://work.weixin.qq.com/)
