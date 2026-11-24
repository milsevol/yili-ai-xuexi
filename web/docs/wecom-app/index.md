# 企业微信应用开发

企业微信（WeCom）是腾讯面向企业的通讯协作平台，开放 API 让企业内部系统嵌入 IM 能力、OA 审批、客户管理、侧边栏轻应用。本主题用中文笔记 + **浏览器可视化交互演示**，梳理企微应用开发「是什么 → 怎么注册 → 消息收发 → 客户联系 → 侧边栏 JS-SDK → 审批打卡 → 通讯录 OAuth → 微应用/小程序 → 实战案例 → 调试 FAQ → 管理后台运维」的完整链路。

> 版本参考：企微 4.0 最新 API（Python 后端 + H5 微应用）。演示不连接真实企业微信；默认打开 `demos/index.html`。

## 先决知识

- 知道微信公众号 / 小程序的基本概念更佳
- 会一点 Python 或 Node.js 读 API 示例
- 理解 HTTP、JSON、OAuth2、回调通知更佳

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位) | `./start.sh 01` | 企微 vs 微信 vs 钉钉、开放能力全景、开发链路 |
| 2 | [02-应用注册与配置](./notes/02-应用注册与配置) | `./start.sh 02` | CorpID/AgentID/Secret、回调验证、access_token 缓存 |
| 3 | [03-消息收发机制](./notes/03-消息收发机制) | `./start.sh 03` | 回调接收、事件通知、主动推送、频控 |
| 4 | [04-客户联系与客户群](./notes/04-客户联系与客户群) | `./start.sh 04` | 客户联系 API、标签、客户群、离职继承 |
| 5 | [05-侧边栏与 JS-SDK](./notes/05-侧边栏与JS-SDK) | `./start.sh 05` | 侧边栏配置、wx.config、扫码/上传/定位 |
| 6 | [06-审批与打卡集成](./notes/06-审批与打卡集成) | `./start.sh 06` | 审批模板、审批回调、打卡 API |
| 7 | [07-通讯录与身份验证](./notes/07-通讯录与身份验证) | `./start.sh 07` | 通讯录 API、OAuth2 授权、UserID/OpenID 转换 |
| 8 | [08-微应用与小程序](./notes/08-微应用与小程序) | `./start.sh 08` | 微应用 vs 小程序、订阅消息 |
| 9 | [09-企业内部实战案例](./notes/09-企业内部实战案例) | `./start.sh 09` | 客户跟进助手：侧边栏 + 审批 + 提醒 + AI |
| 10 | [10-开发技巧与 FAQ](./notes/10-开发技巧与FAQ) | `./start.sh 10` | 内网穿透、沙箱、错误码、频控、上线 Checklist |
| 11 | [11-管理后台常见操作](./notes/11-管理后台常见操作) | `./start.sh 11` | 管理员体系、超级/分级管理员、通讯录、应用、客户联系、安全、审计 |

## 如何启动演示

```bash
cd notes/wecom-app
./start.sh          # 浏览器可视化交互
./start.sh 02       # 直达应用注册与配置
./start.sh --cli    # 备用终端文字版
```

也可：`python3 main.py wecom-app`。

## 参考与官方文档

- [企业微信开发文档](https://developer.work.weixin.qq.com/document/path/90664)
- [API 列表](https://developer.work.weixin.qq.com/document/path/90235)
- [错误码说明](https://developer.work.weixin.qq.com/document/path/90313)
