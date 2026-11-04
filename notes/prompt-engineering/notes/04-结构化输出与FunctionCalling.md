# 04 结构化输出与 Function Calling

## 一句话

**LLM 应用要进生产，输出必须可被程序解析**。两大手段：Prompt 约束 JSON 输出（+ 校验重试兜底），和官方的 Function Calling / Structured Outputs（模型原生保证格式）。掌握 Schema 设计和格式坑，是区分玩具 Demo 和生产应用的分水岭。

## 为什么要结构化输出

```text
❌ 自由文本输出：
「这条评论是负面的，主要抱怨物流速度，建议联系物流部门。」
→ 程序怎么取「负面」？正则？祈祷格式不变？

✅ 结构化输出：
{"label": "负面", "aspect": "物流", "assignee": "物流部"}
→ json.loads() 直接进数据库
```

LLM 应用的本质是**用模型替代一段业务逻辑**——上游给你结构化输入，下游要结构化输出。自由文本只适合「人看」的最后一环。

## 方式一：Prompt 约束 JSON 输出

```text
【指令】分析评论并严格输出 JSON，不要输出任何其他文字。

【输出格式】
{"label": "正面|负面|中性", "aspect": "物流|质量|价格|服务", "keywords": ["关键词1", "关键词2"]}
```

**配套工程措施**（缺一不可）：

| 措施 | 作用 |
| --- | --- |
| `temperature=0` | 降低随机性，格式更稳定 |
| 「不要输出任何其他文字」 | 防止模型加前缀「好的，结果是：」 |
| 用 ` ```json ` 包裹要求或显式禁止 markdown | 有的模型爱把 JSON 包在代码块里 |
| 程序端 `json.loads` + 异常捕获 + 重试 | 兜底 1~3% 的格式失败 |

```python
# OpenAI SDK 风格伪代码：带校验重试的 JSON 抽取
import json
from openai import OpenAI

client = OpenAI()
REQUIRED_KEYS = {"label", "aspect", "keywords"}

def extract(review: str, max_retry: int = 3) -> dict:
    prompt = f"分析评论，严格输出 JSON：{sorted(REQUIRED_KEYS)}。评论：{review}"
    for attempt in range(max_retry):
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},  # OpenAI JSON 模式
        )
        try:
            data = json.loads(resp.choices[0].message.content)
            if REQUIRED_KEYS <= data.keys():
                return data
        except (json.JSONDecodeError, AttributeError):
            continue
    raise ValueError(f"重试 {max_retry} 次仍无法获得合法 JSON")
```

## 方式二：Function Calling / Structured Outputs

模型厂商把「输出结构化数据」做成了原生能力：你定义函数签名（JSON Schema），模型决定**是否调用**以及**填什么参数**，输出由模型保证符合 Schema。

### 定义工具

```python
# OpenAI SDK 风格伪代码：定义函数工具
tools = [{
    "type": "function",
    "function": {
        "name": "create_order",
        "description": "为用户创建订单",   # 模型靠描述决定何时调用
        "parameters": {
            "type": "object",
            "properties": {
                "product": {"type": "string", "description": "商品名"},
                "quantity": {"type": "integer", "minimum": 1},
                "address":  {"type": "string", "description": "收货地址"},
            },
            "required": ["product", "quantity", "address"],
        },
    },
}]
```

### 完整流程（四步循环）

```text
用户：帮我买 2 箱牛奶寄到北京市朝阳区xx路
  │
  ▼ ① 带 tools 调用模型
模型输出 tool_calls: create_order(product="牛奶", quantity=2, address="北京市朝阳区xx路")
  │
  ▼ ② 你的代码执行真实函数
order_id = create_order(product="牛奶", quantity=2, address="北京市朝阳区xx路")
  │
  ▼ ③ 把执行结果回填给模型（role="tool"）
  │
  ▼ ④ 模型基于结果生成自然语言回复
「已为您下单 2 箱牛奶，订单号 20261104001，明天送达。」
```

```python
# OpenAI SDK 风格伪代码：四步循环核心骨架
messages = [{"role": "user", "content": user_input}]

# ① 首次调用
resp = client.chat.completions.create(model="gpt-4o-mini", messages=messages, tools=tools)
msg = resp.choices[0].message

# ② 模型要求调函数 → 本地执行
if msg.tool_calls:
    messages.append(msg)
    for call in msg.tool_calls:
        args = json.loads(call.function.arguments)
        result = dispatch(call.function.name, args)   # 真实业务函数
        # ③ 回填结果
        messages.append({
            "role": "tool",
            "tool_call_id": call.id,
            "content": json.dumps(result, ensure_ascii=False),
        })
    # ④ 再调一次模型生成最终回复
    resp2 = client.chat.completions.create(model="gpt-4o-mini", messages=messages, tools=tools)
    final = resp2.choices[0].message.content
```

## Schema 设计要点

| 要点 | 说明 | 反例 |
| --- | --- | --- |
| 字段名自解释 | `user_age` 优于 `a` | 单字母字段模型理解差 |
| description 写清楚 | 模型靠它理解语义和格式 | 只给字段名不给说明 |
| 用 enum 限定取值 | `"enum": ["正面","负面","中性"]` | 自由字符串，模型自创标签 |
| required 最小化 | 只把必须有的放 required | 全放 required，缺信息时模型瞎编 |
| 给「未知」出口 | 枚举里加 `"未知"` 或允许 null | 模型被迫硬猜 → 幻觉 |
| 嵌套别太浅也别太深 | 1~3 层合适 | 5 层嵌套，错误率飙升 |

## 常见格式坑（踩坑速查表）

| 坑 | 现象 | 对策 |
| --- | --- | --- |
| Markdown 代码块包裹 | ` ```json {...} ``` ` 导致 json.loads 失败 | 提示词禁 markdown，或程序先剥壳 |
| 前后多余文字 | 「好的，结果是：{...}」 | response_format=json_object，或正则提取第一个 `{` 到最后一个 `}` |
| 中文引号 | `｛"标签"："负面"｝` | 校验时替换全角符号 |
| 单引号 | `{'label': '负面'}` 不是合法 JSON | 重试 + 提示词强调双引号 |
| 数字变字符串 | `{"quantity": "2"}` | Schema 声明类型 + 程序端强转 |
| 枚举外取值 | 要求「负面」输出「差」 | enum 约束 + 「只能从给定值中选」 |
| 截断 | 长输出被 max_tokens 截断，JSON 不完整 | 调大 max_tokens + 校验 JSON 完整性 |
| 多余的尾逗号 | `{"a":1,}` | 重试；或降级用宽松解析器 |

## 校验与重试策略

```text
模型输出
  │ json.loads 失败？──── 重试（最多 3 次，第二次起把错误信息喂回模型）
  ▼
字段齐全？───────────── 缺字段 → 重试，提示「缺少 xxx 字段」
  ▼
类型/枚举合法？────────── 不合法 → 重试，提示「label 必须是 正面/负面/中性 之一」
  ▼
业务规则合法？──────────── 数量>0、日期合理…不合法走业务兜底
  ▼
入库
```

**经验**：把**上一次的错误信息**拼进重试 Prompt（「上次输出缺 label 字段，请修正」），一次重试成功率 > 90%。超过 3 次仍失败，进人工队列，不要无限重试。

## 三种方案选型

| 方案 | 格式保证 | 成本 | 适用 |
| --- | --- | --- | --- |
| 纯 Prompt 约束 | 95~99% | 低 | 内部工具、格式简单 |
| JSON 模式（response_format） | 99%+ 语法合法，但不保证业务字段 | 低 | 需要 JSON 但 Schema 灵活 |
| Function Calling / Structured Outputs | 原生 Schema 保证 | 略高（Schema 占 token） | 生产环境、Agent、强约束场景 |

## 常见问题

**Q：Function Calling 是模型直接执行我的函数吗？**
A：**不是**。模型只负责「决定调用哪个函数、参数填什么」，执行永远在你的代码里。模型输出的是调用请求，你可以（也应该）在执行前做权限和参数校验。

**Q：模型没调用我期望的函数怎么办？**
A：检查三点：① 函数 `description` 是否写清楚「什么时候该调用它」；② 用户输入是否真的触发该场景；③ 工具数量是否过多（>20 个时模型选择困难，应分组或用路由）。

**Q：Structured Outputs 和 Function Calling 什么关系？**
A：Structured Outputs 是让模型**回复本身**严格符合 Schema；Function Calling 是让模型输出**工具调用请求**。前者用于信息抽取，后者用于 Agent 行动。两者底层都是 Schema 约束生成。

**Q：重试时 temperature 要调吗？**
A：如果一直是 0 且重复同样的错误，可以小幅升温（0→0.3）让模型跳出错误模式。但多数情况下「把错误信息喂回去」比调温度有效。

## 自测

1. 画出 Function Calling 的四步循环，说明每一步消息的角色是什么。
2. Schema 设计中为什么要给「未知」出口？不给会发生什么？
3. 列出至少 5 个 JSON 输出的常见格式坑及对策。
4. 设计一个带错误信息反馈的重试循环（伪代码即可）。

## 参考与官方链接

- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
- [OpenAI Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs)
- [Anthropic Tool Use](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview)
- [JSON Schema 官方文档](https://json-schema.org/learn/)
