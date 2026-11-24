# 飞书应用开发

飞书（Lark）是字节跳动面向企业的一体化协作平台，把即时通讯、文档、多维表格、日历、会议、审批整合到一个入口，并通过开放平台 API 让企业自建应用嵌入这些能力。本主题用中文笔记 + **浏览器可视化交互演示**，梳理飞书应用开发「是什么 → 怎么注册应用 → 身份认证与 Token → 消息与卡片 → 多维表格 → 文档云空间 → 通讯录 OAuth → 日历会议审批 → 小程序 → 工作台详解 → 实战 → 调试 FAQ」的完整链路。

> 版本参考：飞书开放平台 v1/v2 最新 API（Python 后端为主）。演示不连接真实飞书；默认打开 `demos/index.html`。

## 先决知识

- 知道企业微信 / 钉钉等协作平台更佳
- 会一点 Python 或 Node.js 读 API 示例
- 理解 HTTP、JSON、OAuth2、回调通知、WebSocket 更佳

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位) | `./start.sh 01` | 飞书 vs 企微 vs 钉钉、开放能力全景、开发链路 |
| 2 | [02-开放平台与应用注册](./notes/02-开放平台与应用注册) | `./start.sh 02` | 开发者后台、自建/商店应用、App ID/Secret、权限与事件订阅 |
| 3 | [03-身份认证与Token](./notes/03-身份认证与Token) | `./start.sh 03` | tenant/app/user_access_token、OAuth2、JSAPI 鉴权 |
| 4 | [04-消息与卡片](./notes/04-消息与卡片) | `./start.sh 04` | 消息类型、交互式卡片、机器人 Webhook、事件订阅、频控 |
| 5 | [05-多维表格Bitable](./notes/05-多维表格Bitable) | `./start.sh 05` | 表/字段/记录/视图 API、字段类型、自动化、Python 集成 |
| 6 | [06-文档与云空间](./notes/06-文档与云空间) | `./start.sh 06` | docx Block 模型、文档 API、云空间 Drive 与权限 |
| 7 | [07-通讯录与组织架构](./notes/07-通讯录与组织架构) | `./start.sh 07` | 部门/成员 API、三种用户 ID、扫码登录与免登 |
| 8 | [08-日历会议与审批](./notes/08-日历会议与审批) | `./start.sh 08` | 日程会议、审批定义/实例/回调、考勤打卡 |
| 9 | [09-小程序与工作台](./notes/09-小程序与工作台) | `./start.sh 09` | 小程序 vs H5 vs 纯后端、应用消息、选型决策 |
| 10 | [10-工作台详解](./notes/10-工作台详解) | `./start.sh 10` | 工作台组成、上架流程、终端可见性、分组排序、管理员配置、小组件、排查 |
| 11 | [11-实战与FAQ](./notes/11-实战与FAQ) | `./start.sh 11` | 审批驱动机器人实战、调试、错误码、上线 Checklist |

## 如何启动演示

```bash
cd notes/feishu
./start.sh          # 浏览器可视化交互
./start.sh 02       # 直达开放平台与应用注册
./start.sh --cli    # 备用终端文字版
```

也可：`python3 main.py feishu`。

## 参考与官方文档

- [飞书开放平台首页](https://open.feishu.cn/)
- [API 调用指南](https://open.feishu.cn/document/server-docs/api-call-guide/calling-process/overview)
- [服务端错误码](https://open.feishu.cn/document/server-docs/api-call-guide/server-error-code)
- [消息卡片搭建工具](https://open.feishu.cn/tool/cardbuilder)
- [Python SDK（lark-oapi）](https://github.com/larksuite/oapi-sdk-python)
