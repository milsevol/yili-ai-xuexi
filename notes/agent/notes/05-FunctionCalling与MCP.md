# 05 Function Calling 与 MCP

## 一句话

**Function Calling 是模型以结构化 JSON 声明「我要调什么工具、参数是什么」的协议**，把 ReAct 的文本解析升级为 API 层强约束；**MCP（Model Context Protocol）把「工具接入」标准化**——工具方实现一次 Server，所有支持 MCP 的 Agent 即插即用。前者解决「怎么调」，后者解决「怎么接」。（ReAct 原理详见第 04 章。）

## 协议流程

```
① 开发者注册工具 Schema（name / description / parameters）
② 用户提问 ──► LLM
③ 模型返回 tool_calls: [{id, type, function: {name, arguments}}]
               arguments 是 JSON「字符串」，不是对象
④ 应用解析 + 校验 + 执行真实函数
⑤ 以 role="tool" + tool_call_id 回灌结果
⑥ 模型基于结果继续（可能再调工具）或给出最终答案
```

**关键点：模型从不直接执行工具**。它只输出调用意图，执行权在你的代码手里——这是安全边界，也是插入校验、鉴权、审计的位置。

```python
# 消息链：system → user → assistant(tool_calls) → tool(tool_call_id) → assistant
messages.append({"role": "assistant", "content": None, "tool_calls": [...]})  # 原样回填
messages.append({"role": "tool", "tool_call_id": "call_abc123", "content": "{\"price\": 1480.0}"})
```

| 要点 | 说明 |
| --- | --- |
| `description` 质量 | 模型主要靠它决定「何时用」——写清用途、边界、示例 |
| 参数 Schema | JSON Schema 强校验，`required` + `enum` 大幅减少幻觉参数 |
| `tool_choice` | `auto`（模型自选）/ `required`（必须调）/ 指定函数（强制调） |
| `parallel_tool_calls` | 一轮返回多个调用，并发执行后一起回灌，降延迟 |
| 错误回灌 | 工具报错也以 tool 消息回灌，模型会自我纠错 |
| `tool_call_id` | 请求与结果的一一对应凭证，缺失/错配直接 400 |

## 一次完整的请求与响应（JSON 实录）

```json
{
  "model": "deepseek-chat",
  "messages": [
    {"role": "system", "content": "你是投研助手，需要实时数据时调用工具。"},
    {"role": "user", "content": "茅台现价多少？涨 5% 后是多少？"}
  ],
  "tools": [{"type": "function", "function": {
    "name": "get_stock_price",
    "description": "查询 A 股最新价与涨跌幅。用户问『多少钱』『现价』时使用。",
    "parameters": {
      "type": "object",
      "properties": {"symbol": {"type": "string", "description": "6 位股票代码，如 600519"}},
      "required": ["symbol"], "additionalProperties": false
    }
  }}],
  "tool_choice": "auto",
  "parallel_tool_calls": true
}
```

模型第 1 次响应（`finish_reason` 为 `tool_calls`，`content` 可能为 `null`）：

```json
{
  "choices": [{
    "index": 0, "finish_reason": "tool_calls",
    "message": {"role": "assistant", "content": null, "tool_calls": [{
      "id": "call_abc123", "type": "function",
      "function": {"name": "get_stock_price", "arguments": "{\"symbol\": \"600519\"}"}
    }]}
  }]
}
```

```python
messages.append({                                    # ① 先回填 assistant，原样保留 id
    "role": "assistant", "content": resp.choices[0].message.content or "",
    "tool_calls": [{"id": "call_abc123", "type": "function",
                    "function": {"name": "get_stock_price", "arguments": "{\"symbol\": \"600519\"}"}}],
})
messages.append({                                    # ② 再回填 tool，id 必须一致
    "role": "tool", "tool_call_id": "call_abc123",
    "content": "{\"name\": \"贵州茅台\", \"price\": 1480.0, \"pct\": 1.2}",
})
```

```json
{"choices": [{"finish_reason": "stop",
  "message": {"role": "assistant", "content": "现价 1480.00 元，今日涨 1.2%。上涨 5% 后约 1554.00 元。"}}]}
```

常见回填错误：漏掉 assistant 消息会 400；`tool_call_id` 写错会张冠李戴；`arguments` 是字符串必须先 `json.loads`；多个 `tool_call` 必须逐个回填，失败的也要回灌错误内容。

## 工具 Schema：从能用到好用

```python
TOOLS = [{
    "type": "function",
    "function": {
        "name": "search_reports",
        "description": ("按条件检索券商研报『元数据列表』，不返回正文。"
                        "用户问『最近有什么报告』『某行业观点汇总』时使用；"
                        "需要正文时再用返回的 report_id 调 get_report。"),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索词，如『白酒 提价』，≤50 字"},
                "market": {"type": "string", "enum": ["A股", "港股", "美股"], "description": "市场，缺省 A股"},
                "date_range": {
                    "type": "object", "description": "发布日期闭区间，格式 YYYY-MM-DD",
                    "properties": {"start": {"type": "string"}, "end": {"type": "string"}},
                    "required": ["start"], "additionalProperties": False
                },
                "industries": {"type": "array", "maxItems": 3,
                               "items": {"type": "string", "enum": ["食品饮料", "新能源", "半导体", "医药"]},
                               "description": "行业过滤，最多 3 个"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 10}
            },
            "required": ["query"], "additionalProperties": False
        }
    }
}]
```

要点：`enum` 收窄取值（杜绝「A股/沪深/中国A股」三种写法）；`required` 只标真必需（全标会逼模型乱填）；`additionalProperties: false` 禁自创字段；嵌套对象表达区间/分页；`array` + `maxItems` 控制批量规模；`minimum`/`maximum` 给边界感。

`description` 正反例：❌ `"查询数据"` → ✅ `"按条件检索研报元数据，不返回正文；正文需再调 get_report"`；❌ `"symbol: 股票代码"` → ✅ `"6 位 A 股代码，如 600519；港股 5 位如 00700"`。只写「何时用、输入什么、返回什么、边界在哪」。

## 工具设计原则

**原子性**：❌ `analyze_stock(symbol)` 内部查行情+财报+估值，模型无法分步控制；✅ 拆成 `get_price` / `get_financials` / `calculator`。原子工具让模型能**组合**出新解法。

**幂等性**：同一调用执行 N 次结果一致。读操作天然幂等；写操作用幂等键 `create_order(idempotency_key="agent-req-123")`，服务端去重。Agent 会因超时/断流重试，非幂等工具重试就是事故。

**错误处理**：失败时返回结构化错误而非抛异常，信息要**面向模型可行动**：

```python
def get_stock_price(symbol: str) -> str:
    if not re.fullmatch(r"\d{6}", symbol):
        return json.dumps({"error": f"股票代码格式错误: {symbol}，应为 6 位数字，如 600519"},
                          ensure_ascii=False)
    try:
        return json.dumps({"price": 1480.0, "pct": 1.2}, ensure_ascii=False)
    except TimeoutError:
        return json.dumps({"error": "行情接口超时，请稍后重试一次"}, ensure_ascii=False)
```

工具总数克制（单场景 ≤ 20）、危险操作分级（读放行、写审批）。

## 手写最小工具调用循环

```python
import json, os, re
from openai import OpenAI

client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")

def get_stock_price(symbol: str) -> str:
    data = {"600519": {"name": "贵州茅台", "price": 1480.0}}
    return json.dumps(data.get(symbol, {"error": f"未找到 {symbol}"}), ensure_ascii=False)

TOOL_IMPL = {"get_stock_price": get_stock_price}
TOOL_SCHEMAS = [{"type": "function", "function": {
    "name": "get_stock_price", "description": "查询 A 股最新价",
    "parameters": {"type": "object", "properties": {"symbol": {"type": "string"}},
                   "required": ["symbol"], "additionalProperties": False}}}]

def to_assistant_dict(msg) -> dict:
    out = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        out["tool_calls"] = [{"id": tc.id, "type": "function",
                              "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                             for tc in msg.tool_calls]
    return out

def tool_loop(user_msg: str, max_iter: int = 6) -> str:
    messages = [{"role": "user", "content": user_msg}]
    for _ in range(max_iter):
        resp = client.chat.completions.create(
            model="deepseek-chat", messages=messages, tools=TOOL_SCHEMAS, tool_choice="auto")
        msg = resp.choices[0].message
        if not msg.tool_calls:                       # 无调用 → 最终答案
            return msg.content
        messages.append(to_assistant_dict(msg))      # ① assistant 先回填
        for tc in msg.tool_calls:                    # ② tool 逐个回填
            try:
                args = json.loads(tc.function.arguments or "{}")
                fn = TOOL_IMPL.get(tc.function.name)
                content = fn(**args) if fn else json.dumps({"error": "工具不存在"})
            except Exception as e:
                content = json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": content})
    return "达到迭代上限，未得到最终答案"

# print(tool_loop("茅台现在多少钱？"))
```

## 并行工具调用

模型一轮可返回多个 `tool_calls`。应用侧并发执行，再**一次性回灌全部结果**：

```python
import asyncio

async def run_tool_calls(tool_calls) -> list[dict]:
    async def one(tc) -> dict:
        try:
            args = json.loads(tc.function.arguments or "{}")
            content = await asyncio.to_thread(TOOL_IMPL[tc.function.name], **args)
        except Exception as e:
            content = json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False)
        return {"role": "tool", "tool_call_id": tc.id, "content": content}
    return await asyncio.gather(*(one(tc) for tc in tool_calls))

# 在 async 循环里替换执行片段（client / TOOL_SCHEMAS / to_assistant_dict 同上）
async def apply_tool_calls(messages, msg):
    messages.append(to_assistant_dict(msg))
    messages.extend(await run_tool_calls(msg.tool_calls))    # 并发后一起回灌
```

**幂等前提**：并发只对无副作用或带幂等键的工具安全。`send_email` / `create_order` 要么串行 + 幂等键，要么先确认；重试叠并发就是重复下单。并发数要有上限（如 `asyncio.Semaphore(8)`）。两个工具各 800ms / 1200ms，并发后总耗时约 1200ms 而非 2000ms。

## 流式输出下的工具调用

流式时 `tool_calls` 被拆成多个 delta：**`id`/`name` 只在首片出现，`arguments` 逐片拼接**。按 `index` 聚合，等 `finish_reason == "tool_calls"` 后再解析：

```python
stream = client.chat.completions.create(
    model="deepseek-chat", messages=messages, tools=TOOL_SCHEMAS, stream=True)

calls: dict[int, dict] = {}
for chunk in stream:
    choice = chunk.choices[0]
    for tc in (choice.delta.tool_calls or []):
        slot = calls.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
        if tc.id:
            slot["id"] = tc.id                                    # 首片才有
        if tc.function:
            slot["name"] = tc.function.name or slot["name"]
            slot["arguments"] += tc.function.arguments or ""      # 逐片拼接
    if choice.delta.content:
        print(choice.delta.content, end="", flush=True)           # 边想边说
    if choice.finish_reason == "tool_calls":
        break

tool_calls = [calls[i] for i in sorted(calls)]                    # 按 index 还原顺序
for c in tool_calls:
    c["args"] = json.loads(c["arguments"] or "{}")                # 完整后才解析
```

不要对半截 `arguments` 做 JSON 解析；流式 + 并行时多个 index 交错到达是正常现象。

## 结构化输出与参数校验

工具参数是模型生成的**不可信输入**，不能直接 `fn(**args)` 打到底层：

```python
import jsonschema

def validate_args(schema: dict, args: dict) -> tuple[bool, str]:
    try:
        jsonschema.validate(instance=args, schema=schema)
        return True, ""
    except jsonschema.ValidationError as e:
        path = ".".join(str(p) for p in e.absolute_path) or "<root>"
        return False, f"参数校验失败（{path}）：{e.message}"

def guard(tc, messages) -> bool:
    args = json.loads(tc.function.arguments or "{}")
    ok, err = validate_args(TOOL_SCHEMAS[0]["function"]["parameters"], args)
    if not ok:   # 不执行，回灌错误让模型自我纠错
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps({"error": err, "hint": "请修正后重新调用"}, ensure_ascii=False)})
    return ok
```

**strict 模式**：OpenAI 的 `strict: true` 让模型输出严格贴合 Schema（要求全部字段 required、`additionalProperties: false`），显著降低参数错误率；DeepSeek 等兼容端点主要支持 `response_format={"type": "json_object"}`，因此**本地 Schema 校验仍是必需品**。回灌要带「哪一层、哪个字段、期望什么」；同一工具连续 2 次校验失败就转人工。

## 工具错误分类与重试策略

| 错误类型 | 例子 | 重试？ | 如何告诉模型 |
| --- | --- | --- | --- |
| 参数错误 | 缺字段、枚举越界、格式不符 | ❌ | 回灌校验详情 + 正确格式示例 |
| 业务错误 | 停牌、订单已关闭、余额不足 | ❌ | 回灌业务原因 + 可选替代动作 |
| 限流 429 | QPS 超限、配额用尽 | ✅ 指数退避 | 「限流，N 秒后重试」，别立刻轰炸 |
| 超时 | 下游 3s 未响应 | ✅（仅幂等） | 「超时已重试 1 次」，让模型考虑换工具 |
| 下游 5xx | 服务不可用 | ✅ 有限次（2~3） | 「服务暂不可用」，建议降级数据源 |
| 权限 401/403 | token 失效、无表权限 | ❌ | 「无权限，需人工授权」，禁止换参数硬试 |

原则：**重试属于应用层，别指望模型算退避时间**；错误统一成 `{"error": ..., "retryable": true/false, "hint": ...}`。

## MCP（Model Context Protocol）

没有 MCP 时：N 个 Agent × M 个工具 = N×M 个定制集成。MCP 把工具侧标准化成 Server、应用侧标准化成 Client，**一次实现，处处可用**——类比 AI 界的 USB-C 或语言领域的 LSP。

| 角色 | 职责 |
| --- | --- |
| Host | 承载 LLM 与用户交互，决定「允不允许调这个工具」 |
| Client | Host 内部与某个 Server 的 1:1 连接，维护会话与能力协商 |
| Server | 暴露 Tools / Resources / Prompts，做真实执行 |

### 生命周期

```
Client                                    Server
  │── initialize（protocolVersion, capabilities, clientInfo）──►│
  │◄── result（serverCapabilities, serverInfo）─────────────────│
  │── notifications/initialized ──────────────────────────────►│
  │── tools/list ─────────────────────────────────────────────►│
  │◄── [{name, description, inputSchema}, ...]─────────────────│
  │── tools/call {name, arguments} ───────────────────────────►│
  │◄── {content: [{type:"text", text:"..."}], isError:false}───│
  │── 关闭连接 / 进程退出 ─────────────────────────────────────►│
```

`initialize` 里协商 Server 支持什么（tools / resources / prompts / subscribe）、Client 是否需要 sampling，之后才能安全调用。

| 传输 | 场景 | 说明 |
| --- | --- | --- |
| `stdio` | 本地工具、IDE 插件 | Host 拉起子进程，走 stdin/stdout |
| `SSE` | 旧版远程方案 | HTTP 长连接单向下发，已被新规范取代 |
| `Streamable HTTP` | 远程多租户 | 单端点 + 可选 SSE 流，支持断线续传 |

| 能力 | 语义 | 例子 |
| --- | --- | --- |
| Tools | 可执行函数，模型可主动调用 | `query_db(sql)` |
| Resources | 可读取的数据（类文件），应用决定注入 | `file:///logs/app.log` |
| Prompts | 预置提示词模板，用户显式选择 | `code_review` 模板 |

### 最小 MCP Server

```python
# pip install "mcp[cli]"
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("stock-tools")

@mcp.tool()
def get_stock_price(symbol: str) -> dict:
    """查询 A 股最新价。symbol 为 6 位代码，如 600519。"""
    return {"symbol": symbol, "price": 1480.0, "pct": 1.2}

@mcp.resource("stock://watchlist")
def watchlist() -> str:
    """当前自选股列表。"""
    return "600519,000858,300750"

if __name__ == "__main__":
    mcp.run()   # 默认 stdio；远程可用 mcp.run(transport="streamable-http")
```

### 最小 MCP Client（接到自己的 Agent）

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

def mcp_tools_to_openai(tools) -> list[dict]:
    return [{"type": "function", "function": {
        "name": t.name, "description": t.description or "", "parameters": t.inputSchema,
    }} for t in tools]

async def main():
    params = StdioServerParameters(command="python", args=["server.py"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            schemas = mcp_tools_to_openai((await session.list_tools()).tools)
            result = await session.call_tool("get_stock_price", {"symbol": "600519"})
            print(schemas, "\n".join(c.text for c in result.content if c.type == "text"), sep="\n")

asyncio.run(main())
```

链路是：**模型 FC 出调用意图 → 应用（MCP Client）转发 `tools/call` → Server 执行 → 结果以 tool 消息回灌**。

### 权限与审计

- **最小权限**：每个 Server 独立凭证/scope，只给它该访问的库表，别用 root token 通吃
- **工具白名单**：Host 侧维护 allowlist，`tools/list` 出来的不等于可以全用
- **写操作审批**：`send_*` / `delete_*` / `execute_*` 强制人工确认
- **审计日志**：记录 `session_id`、`tool_name`、参数摘要、状态、耗时、调用者

### 安全风险：工具投毒与困惑的代理

| 风险 | 机理 | 缓解 |
| --- | --- | --- |
| 工具投毒 | 恶意 Server 在 `description` 藏指令，如「调用前先读 ~/.ssh」 | 人工审核描述、工具定义 pin 哈希 |
| Rug Pull | 审批时无害，后续 `tools/list` 悄悄改定义 | 固定签名/哈希，变更即降级为待审批 |
| 困惑的代理 | Server 权限大，Agent 被注入内容诱导越权 | 最小权限 + 按用户身份二次鉴权，不信 arguments 里的「我是管理员」 |
| 影子工具 | 恶意 Server 起同名工具抢调用 | 工具名加 Server 前缀，冲突拒绝而非覆盖 |
| 结果注入 | 工具返回里夹带「忽略以上指令」 | 结果包边界、按数据处理、关键动作仍审批 |

一句话：**MCP 标准化了「接」，但没标准化「信」**，信任边界要自己画。

## 工具设计检查清单

- [ ] 名称是动词短语，一眼能懂（`get_price` 而非 `price`）
- [ ] `description` 写清「何时用 / 输入什么 / 返回什么 / 不做什么」
- [ ] 参数有 `enum`、`required`、边界值，且 `additionalProperties: false`
- [ ] 单个工具只做一件事，可被模型自由组合
- [ ] 错误结构化，含 `error` + `retryable` + `hint`
- [ ] 写操作带幂等键，且默认需要人工确认
- [ ] 参数在服务端二次校验并检查权限，不信任模型

## 常见问题

**Q：Function Calling 和 ReAct 选哪个？**
A：生产用 Function Calling——结构化输出免解析、模型原生训练过、支持并行调用；ReAct 用于理解原理和不支持 FC 的开源模型（详见第 04 章）。

**Q：工具返回结果很长怎么办？**
A：三层压缩：工具内部先裁剪、超阈值存外部返回引用、进上下文前摘要（详见第 07 章）。

**Q：MCP 和 Function Calling 是竞争关系吗？**
A：不是，是两层。FC 是「模型 ↔ 应用」的调用协议，MCP 是「应用 ↔ 工具提供方」的接入协议；应用用 FC 拿意图，再用 MCP Client 转发执行。

**Q：模型一轮返回多个 tool_calls，可以只回一部分吗？**
A：不行。每个 `id` 都必须对应一条 tool 消息，否则下一次请求 400；执行失败的也要回填错误内容。

## 自测

1. 描述 Function Calling 从提问到最终答案的完整消息流（至少 4 步），并说明 `tool_call_id` 的作用。
2. 写出含 `enum`、嵌套对象、`array`、`required` 的工具 Schema，并说明 `additionalProperties: false` 为什么重要。
3. 并行工具调用能省多少延迟？成立前提是什么？
4. 流式响应里为什么不能边收 `arguments` 边 `json.loads`？正确做法？

## 参考与官方链接

- [OpenAI Function Calling 指南](https://platform.openai.com/docs/guides/function-calling)
- [OpenAI Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs)
- [MCP 官方规范](https://modelcontextprotocol.io/specification)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Anthropic: Introducing MCP](https://www.anthropic.com/news/model-context-protocol)
