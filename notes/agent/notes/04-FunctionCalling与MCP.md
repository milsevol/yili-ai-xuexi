# 04 Function Calling 与 MCP

## 一句话

**Function Calling 是模型以结构化 JSON 声明「我要调什么工具、参数是什么」的协议**，把 ReAct 时代的文本解析升级为 API 层强约束；**MCP（Model Context Protocol）则把「工具接入」标准化**——工具方实现一次 MCP Server，所有支持 MCP 的 Agent 都能即插即用。前者解决「怎么调」，后者解决「怎么接」。

## Function Calling 协议细节

### 完整交互流程

```
① 开发者注册工具 Schema ──────────────┐
                                      ▼
② 用户提问 ──→ LLM ──→ ③ 模型决定调工具
                          返回 tool_calls: [{name, arguments(JSON)}]
                                      │
④ 你的代码执行工具 ←──────────────────┘
                                      │
⑤ 把结果以 role="tool" 消息回灌 ──→ LLM
                                      │
                              ⑥ 模型生成最终答案
```

**关键点：模型从不直接执行工具**。它只输出「调用意图」，执行权在你的代码手里——这是安全边界。

### OpenAI 风格的消息结构

```python
messages = [
    {"role": "system", "content": "你是投研助手。"},
    {"role": "user", "content": "查一下茅台最新股价"},
]

tools = [{
    "type": "function",
    "function": {
        "name": "get_stock_price",
        "description": "查询 A 股最新价与涨跌幅",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "6 位股票代码，如 600519"}
            },
            "required": ["symbol"],
            "additionalProperties": False
        }
    }
}]

# 模型响应（第③步）
response.choices[0].message.tool_calls = [{
    "id": "call_abc123",
    "function": {"name": "get_stock_price", "arguments": '{"symbol": "600519"}'}
}]

# 结果回灌（第⑤步）——id 必须对应
messages.append({"role": "tool", "tool_call_id": "call_abc123", "content": '{"price": 1480.0, "pct": 1.2}'})
```

### 协议要点清单

| 要点 | 说明 |
| --- | --- |
| `description` 质量 | 模型主要靠它决定「何时用」——写清楚用途、边界、示例 |
| 参数 Schema | JSON Schema 强校验，`required` + 枚举值能大幅减少幻觉参数 |
| `tool_choice` | `auto`（模型自选）/ `required`（必须调）/ 指定函数（强制调某个） |
| `parallel_tool_calls` | 一轮返回多个调用，并行执行后一起回灌，降延迟 |
| 错误回灌 | 工具报错也要以 tool 消息回灌，模型会自我纠错 |

## 工具设计原则

### 1. 原子性

❌ 反例：`analyze_stock(symbol)` —— 内部又查行情又查财报又算估值，模型无法分步控制
✅ 正例：拆成 `get_price(symbol)` / `get_financials(symbol)` / `calculator(expr)`

原子性让模型能**组合**工具解决新问题，而不是被工具的形状限制。

### 2. 幂等性

同一个调用执行 N 次结果一致。Agent 可能因超时/解析失败重试同一调用，非幂等工具（如 `send_email`）重试就是事故。

- 读操作天然幂等，放心重试
- 写操作用**幂等键**：`create_order(idempotency_key="agent-req-123")`，服务端去重

### 3. 错误处理

工具失败时**返回结构化错误文本，而不是抛异常**：

```python
def get_stock_price(symbol: str) -> str:
    if not re.fullmatch(r"\d{6}", symbol):
        return json.dumps({"error": f"股票代码格式错误: {symbol}，应为 6 位数字，如 600519"})
    try:
        return json.dumps(fetch_price(symbol))
    except RateLimitError:
        return json.dumps({"error": "行情接口限流，请稍后重试一次"})
```

错误信息要**面向模型可行动**：告诉它错在哪、正确的格式是什么、能不能重试。

### 4. 其他实用原则

- **返回精简**：工具返回控制在几百 token 内，长结果先截断/摘要（详见第 07 章）
- **数量克制**：工具超过 20 个后模型选择困难，按场景分组加载
- **危险操作分级**：读工具自动放行，写工具（发邮件/下单）插入人工确认

## MCP（Model Context Protocol）

### 解决什么问题

没有 MCP 时：N 个 Agent 应用 × M 个工具 = N×M 个定制集成。MCP 把工具侧标准化成 Server，应用侧标准化成 Client，**一次实现，处处可用**——类比 AI 界的 USB-C 或语言领域的 LSP。

### 架构

```
┌─────────────┐   MCP 协议    ┌──────────────────┐
│  MCP Host    │  (JSON-RPC   │   MCP Server      │
│ (Claude桌面/ │◄────────────►│  (封装某个工具/    │
│  IDE/Agent)  │  stdio/SSE)  │   数据源)         │
└─────────────┘              └──────────────────┘
        │
        ├── MCP Server: filesystem（读写本地文件）
        ├── MCP Server: postgres（查数据库）
        └── MCP Server: github（操作仓库）
```

三种传输方式：`stdio`（本地子进程，最常用）、`SSE`（HTTP 长连接，远程）、`Streamable HTTP`（新版标准）。

### Server 暴露的三类能力

| 能力 | 说明 | 例子 |
| --- | --- | --- |
| Tools | 可执行函数 | `query_db(sql)` |
| Resources | 可读取的数据源（类文件） | `file:///logs/app.log` |
| Prompts | 预置提示词模板 | `code_review` 模板 |

### 最小 MCP Server（Python）

```python
# pip install mcp
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("stock-tools")

@mcp.tool()
def get_stock_price(symbol: str) -> dict:
    """查询 A 股最新价。symbol 为 6 位代码，如 600519。"""
    return {"symbol": symbol, "price": 1480.0, "pct": 1.2}

@mcp.tool()
def calculator(expression: str) -> dict:
    """计算数学表达式，如 '100*1.05'。"""
    return {"result": eval(expression, {"__builtins__": {}})}  # 演示用，生产请用安全计算器

if __name__ == "__main__":
    mcp.run()  # 默认 stdio 传输
```

Claude Desktop / Cursor 配置里加一行指向这个脚本，工具即可被发现调用。

## 手写最小工具调用循环

不依赖任何框架，实现「模型决策 → 执行 → 回灌」闭环：

```python
import json, re

# ---------- 工具实现 ----------
def get_stock_price(symbol: str) -> str:
    data = {"600519": {"name": "贵州茅台", "price": 1480.0, "pct": 1.2}}
    if symbol not in data:
        return json.dumps({"error": f"未找到 {symbol}"}, ensure_ascii=False)
    return json.dumps(data[symbol], ensure_ascii=False)

def calculator(expression: str) -> str:
    try:
        allowed = re.fullmatch(r"[\d\s\.\+\-\*\/\(\)]+", expression)
        if not allowed:
            return json.dumps({"error": "表达式含非法字符"})
        return json.dumps({"result": eval(expression, {"__builtins__": {}})})
    except Exception as e:
        return json.dumps({"error": str(e)})

TOOLS = {"get_stock_price": get_stock_price, "calculator": calculator}

# ---------- 调用循环 ----------
def tool_loop(user_msg: str, max_iter: int = 6) -> str:
    messages = [{"role": "user", "content": user_msg}]
    for _ in range(max_iter):
        resp = client.chat(messages, tools=TOOL_SCHEMAS)   # 伪代码：你的 LLM API
        msg = resp.choices[0].message
        if not msg.tool_calls:                              # 无工具调用 → 最终答案
            return msg.content
        messages.append(msg)
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            fn = TOOLS.get(tc.function.name)
            result = fn(**args) if fn else json.dumps({"error": "工具不存在"})
            messages.append({"role": "tool",
                             "tool_call_id": tc.id,
                             "content": result})
    return "达到迭代上限"

# tool_loop("茅台现在多少钱？涨 5% 后是多少？")
# 预期轨迹：get_stock_price(600519) → calculator("1480*1.05") → 最终回答
```

## 常见问题

**Q：Function Calling 和 ReAct 选哪个？**
A：生产用 Function Calling——结构化输出免解析、模型原生训练过、支持并行调用。ReAct 用于理解原理和不支持 FC 的开源模型。

**Q：工具返回结果很长怎么办？**
A：三层压缩：工具内部先裁剪（只返回 top-N）、超过阈值存外部文件返回引用、进上下文前摘要。别让一个工具返回 10 万 token 把窗口撑爆。

**Q：MCP 和 Function Calling 是竞争关系吗？**
A：不是，是两层。Function Calling 是「模型 ↔ 应用」之间的调用协议；MCP 是「应用 ↔ 工具提供方」之间的接入协议。你的应用可以用 FC 拿到模型的调用意图，再通过 MCP Client 转发给 MCP Server 执行。

**Q：如何防止模型乱调危险工具？**
A：① Schema 层：危险参数用枚举收紧；② 执行层：写操作要求 `confirm=True` 且由人工置位；③ 审计层：所有调用落日志。

## 自测

1. 描述 Function Calling 从用户提问到最终答案的完整消息流（至少 4 步）。
2. 工具设计三原则是什么？各举一个违反它的后果。
3. MCP 的三种 Server 能力是什么？它和 Function Calling 的分工？
4. 手写工具调用循环里，`tool_call_id` 起什么作用？

## 参考与官方链接

- [OpenAI Function Calling 指南](https://platform.openai.com/docs/guides/function-calling)
- [MCP 官方规范](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Anthropic: Introducing MCP](https://www.anthropic.com/news/model-context-protocol)
