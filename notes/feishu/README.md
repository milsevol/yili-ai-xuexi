# 飞书应用开发

飞书（Lark）是字节跳动面向企业的**一体化协作平台**，把即时通讯、文档、多维表格、日历、会议、审批、OKR 整合到一个入口，并通过开放平台 API 让企业自建应用嵌入这些能力。不只是「聊天工具」，更是企业数字化的**统一工作入口**。本主题用中文笔记 + **浏览器可视化交互演示**，梳理飞书应用开发「是什么 → 怎么注册应用 → 身份认证与 Token → 消息与卡片 → 多维表格 → 文档云空间 → 通讯录 OAuth → 日历会议审批 → 小程序 → 工作台详解 → 实战 → 调试 FAQ」的完整链路。

> 版本参考：以 **飞书开放平台 v1/v2 最新 API** 为准，示例以 Python 后端为主。演示不连接真实飞书；默认打开 `demos/index.html`。

## 先决知识

- 知道什么是「企业微信 / 钉钉」等企业协作平台更佳
- 会一点 Python 或 Node.js（读 API 调用示例用）
- 理解 HTTP、JSON、OAuth2、回调通知、WebSocket 等基础概念更佳

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位.md) | `./start.sh 01` | 飞书 vs 企微 vs 钉钉、开放能力全景、开发链路总览 |
| 2 | [02-开放平台与应用注册](./notes/02-开放平台与应用注册.md) | `./start.sh 02` | 开发者后台、自建应用/商店应用、App ID/App Secret、权限与发布 |
| 3 | [03-身份认证与Token](./notes/03-身份认证与Token.md) | `./start.sh 03` | tenant/app/user_access_token、OAuth2 授权登录、JSAPI 鉴权 |
| 4 | [04-消息与卡片](./notes/04-消息与卡片.md) | `./start.sh 04` | 消息类型、消息卡片、自定义机器人 Webhook、事件订阅、频控 |
| 5 | [05-多维表格Bitable](./notes/05-多维表格Bitable.md) | `./start.sh 05` | 表/字段/记录/视图 API、字段类型与公式、自动化、Python 集成 |
| 6 | [06-文档与云空间](./notes/06-文档与云空间.md) | `./start.sh 06` | 云文档 Block 模型、文档/表格 API、云空间 Drive 与权限 |
| 7 | [07-通讯录与组织架构](./notes/07-通讯录与组织架构.md) | `./start.sh 07` | 部门/成员 API、open_id/user_id/union_id、扫码登录与免登 |
| 8 | [08-日历会议与审批](./notes/08-日历会议与审批.md) | `./start.sh 08` | 日历日程、视频会议、审批定义/实例/回调、考勤打卡 |
| 9 | [09-小程序与工作台](./notes/09-小程序与工作台.md) | `./start.sh 09` | 飞书小程序、网页应用 H5、应用消息、选型决策 |
| 10 | [10-工作台详解](./notes/10-工作台详解.md) | `./start.sh 10` | 工作台组成、上架流程、终端可见性、分组排序、管理员配置、小组件、排查 |
| 11 | [11-实战与FAQ](./notes/11-实战与FAQ.md) | `./start.sh 11` | 审批流 + 多维表格报表 + AI 助手实战、调试、错误码、上线 Checklist |

建议：01–02 建立开发环境与应用凭证；03 是所有 API 调用的前提；04 消息/卡片是最高频入口；05–06 是飞书差异化能力（多维表格、云文档）；07–08 是组织与 OA 集成；09 讲前端形态；10 重点讲工作台（应用能否被员工真正用起来的关键）；11 实战串联 + 上线检查。

## 如何启动演示

```bash
cd notes/feishu
./start.sh          # 浏览器可视化交互
./start.sh 02       # 直达开放平台与应用注册
./start.sh --cli    # 备用终端文字版
```

也可从仓库根进入：`python3 main.py feishu`。

## 本地开发快速上手

### 1. 注册飞书

个人/企业均可注册：https://www.feishu.cn/ （国内）或 https://www.larksuite.com/ （海外）

### 2. 获取应用凭证

- 进入[飞书开放平台](https://open.feishu.cn/) → 创建「企业自建应用」
- **App ID**：应用唯一标识，开发者后台 → 凭证与基础信息
- **App Secret**：应用密钥，同页查看（注意保密！）

### 3. 内网穿透（接收事件回调）

```bash
cpolar http 8080        # 国内推荐
# 或
ngrok http 8080
```

### 4. 最小 Python 后端

```bash
pip install requests lark-oapi   # 飞书官方 Python SDK
```

## 参考与官方文档

- [飞书开放平台首页](https://open.feishu.cn/)
- [API 调用指南](https://open.feishu.cn/document/server-docs/api-call-guide/calling-process/overview)
- [服务端错误码](https://open.feishu.cn/document/server-docs/api-call-guide/server-error-code)
- [消息卡片搭建工具](https://open.feishu.cn/document/uAjLw4CM/ukzMukzMukzM/feishu-cards/card-struct)
- [Python SDK（lark-oapi）](https://github.com/larksuite/oapi-sdk-python)
- [开发者后台](https://open.feishu.cn/app)
