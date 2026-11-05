# 06 LangGraph 状态机

## 一句话

**LangGraph 把 Agent 建模为一张状态图（StateGraph）**：节点是执行单元（调 LLM / 调工具 / 人工审批），边是流转规则（含条件分支），状态在节点间流转并被检查点持久化。相比 ReAct 自由循环，图编排换来的是**可控、可观测、可断点续跑**——这是 Agent 从 Demo 走向生产的关键一步。

## 为什么用图编排 Agent

ReAct 自由循环（原理详见第 04 章）的痛点：

- 流程藏在模型的自由发挥里，**无法预知路径**，出问题只能翻日志
- 想插入人工审批、想在崩溃后恢复，自由循环没有抓手
- 多步骤任务中想让某几步并行，`while` 循环表达不了

```
ReAct：一个黑盒 while 循环，模型说了算
LangGraph：一张你画的图，模型只在节点内发挥，走哪条边由你控制
```

**一句话区分**：LangChain Agent 是「模型指挥流程」，LangGraph 是「你设计流程、模型填内容」。

## StateGraph 四要素

| 概念 | 说明 | 代码对应 |
| --- | --- | --- |
| State | 全局共享状态，所有节点可读可写 | `TypedDict` / `dataclass` |
| Node | 节点函数：接收 State，返回**局部更新** | `def node(state) -> dict` |
| Edge | 固定流转（A→B） | `add_edge("a", "b")` |
| Conditional Edge | 按 State 动态决定去向 | `add_conditional_edges("a", router)` |

## 完整可运行示例

```python
# pip install langgraph langgraph-checkpoint-sqlite openai
import json, operator, os, sqlite3
from typing import Annotated, TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from openai import OpenAI

client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")

class AgentState(TypedDict):
    messages: Annotated[list[dict], operator.add]   # 追加：多节点更新不会互相覆盖
    steps: Annotated[int, operator.add]             # 累加：每次 llm 调用 +1
    error: str                                      # 未注解：直接覆盖

SYSTEM = "你是投研助手。需要行情或计算时调用工具，不要编造。"

def get_stock_price(symbol: str) -> str:
    data = {"600519": {"name": "贵州茅台", "price": 1480.0}}
    return json.dumps(data.get(symbol, {"error": f"未找到 {symbol}"}), ensure_ascii=False)

def calculator(expression: str) -> str:
    try:
        return json.dumps({"result": eval(expression, {"__builtins__": {}})})  # 演示用，生产换安全计算器
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

TOOL_IMPL = {"get_stock_price": get_stock_price, "calculator": calculator}
TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "get_stock_price", "description": "查询 A 股最新价",
        "parameters": {"type": "object", "properties": {"symbol": {"type": "string"}},
                       "required": ["symbol"], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "calculator", "description": "计算四则运算，如 '1480*1.05'",
        "parameters": {"type": "object", "properties": {"expression": {"type": "string"}},
                       "required": ["expression"], "additionalProperties": False}}},
]

def llm_node(state: AgentState) -> dict:
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "system", "content": SYSTEM}] + state["messages"],
        tools=TOOL_SCHEMAS, tool_choice="auto", parallel_tool_calls=True,
    )
    msg = resp.choices[0].message
    assistant = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        assistant["tool_calls"] = [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls
        ]
    return {"messages": [assistant], "steps": 1}    # 只返回增量，别返回整个 state

def tool_node(state: AgentState) -> dict:
    last = state["messages"][-1]
    results = []
    for tc in last.get("tool_calls", []):
        try:
            args = json.loads(tc["function"]["arguments"] or "{}")
            content = TOOL_IMPL[tc["function"]["name"]](**args)
        except Exception as e:
            content = json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False)
        results.append({"role": "tool", "tool_call_id": tc["id"], "content": content})
    return {"messages": results}

def router(state: AgentState) -> str:
    if state["steps"] >= 8:                         # 刹车：防死循环烧钱
        return "end"
    return "tools" if state["messages"][-1].get("tool_calls") else "end"

graph = StateGraph(AgentState)
graph.add_node("llm", llm_node)
graph.add_node("tools", tool_node)
graph.add_edge(START, "llm")
graph.add_conditional_edges("llm", router, {"tools": "tools", "end": END})
graph.add_edge("tools", "llm")                      # 工具结果回灌，形成循环

conn = sqlite3.connect("agent.db", check_same_thread=False)
app = graph.compile(checkpointer=SqliteSaver(conn))

config = {"configurable": {"thread_id": "u1-s1"}, "recursion_limit": 25}
result = app.invoke(
    {"messages": [{"role": "user", "content": "茅台现价多少？涨 5% 后是多少？"}], "steps": 0},
    config,
)
print(result["messages"][-1]["content"])
```

### 每个 reducer 的语义

| 字段 | Reducer | 合并行为 | 选它的原因 |
| --- | --- | --- | --- |
| `messages` | `operator.add` | 列表拼接 `old + new` | 节点只返回新增消息，历史自然累积 |
| `steps` | `operator.add` | 整数相加 | 多个节点都能 +1，天然计数 |
| 未注解字段 | 覆盖（last-write-wins） | 新值替换旧值 | 标记位、错误信息、当前阶段 |

本例用原始 `dict` 消息，所以用 `operator.add`。若使用 LangChain 消息对象，应改用 `Annotated[list, add_messages]`：它支持按 message id 去重与替换，更适合「重试/编辑历史」场景。

## 图的执行模型

### Super-step

LangGraph 按**超级步**推进：每一步把当前所有就绪节点一起执行，**步末统一合并状态**，再计算下一批节点。

```
super-step 1:  START ──► [llm]
super-step 2:  [tools]                       （llm 返回 tool_calls）
super-step 3:  [llm]                         （工具结果已回灌）
super-step 4:  END                           （llm 无 tool_calls）
```

节点内部的多次 `await` 不算多步；只有「节点返回 → reducer 合并」才推进一个 super-step。`recursion_limit` 限制的就是步数，超限抛 `GraphRecursionError`。

### 并行节点与状态合并

扇出：一个节点连多条边；扇入：多个分支都连到同一节点，LangGraph 会等全部分支完成再执行下游。

```
        ┌──► researcher_a ──┐
planner ┤                   ├──► writer
        └──► researcher_b ──┘
```

```python
graph.add_edge("planner", "researcher_a")   # 扇出：一个节点连多条边
graph.add_edge("planner", "researcher_b")
graph.add_edge("researcher_a", "writer")    # 扇入：writer 等两个分支都完成
graph.add_edge("researcher_b", "writer")
```

并行分支对同一字段的更新在步末按 reducer 合并。`operator.add` 的拼接顺序**不保证**与代码书写顺序一致，因此：要么每个分支写不同字段，要么给结果带上可排序的键，别依赖到达顺序。

### 条件边返回值映射

```python
graph.add_conditional_edges("llm", router, {"tools": "tools", "end": END})
```

`router` 返回的是**映射的 key**，不是节点名；key 未在映射里会直接报错。多个 key 可映射到同一节点（如 `"done"` 和 `"end"` 都指向 `END`）。需要运行时动态跳转时，可用 `Command(goto=..., update=...)` 代替条件边：

```python
from langgraph.types import Command

def router_cmd(state: AgentState) -> Command:
    if state["steps"] > 8:
        return Command(goto=END, update={"error": "超出步数预算"})
    target = "tools" if state["messages"][-1].get("tool_calls") else END
    return Command(goto=target)
```

`Command` 既能跳转又能顺手写状态，适合「越界即终止」这类跨节点决策；但它绕过映射表，可读性不如显式条件边，团队里选一种统一用。

## 流式与可观测

```python
# values：每个 super-step 结束输出完整 state 快照
for snapshot in app.stream(inputs, config, stream_mode="values"):
    print(snapshot["steps"], snapshot["messages"][-1]["role"])

# updates：输出「节点名 → 该节点的增量」，最适合排查路由
for node_name, update in app.stream(inputs, config, stream_mode="updates"):
    print(node_name, list(update))
```

`stream_mode="messages"` 逐个 token 输出 `(chunk, metadata)`，但只有 LangChain 聊天模型产生流事件时才有效：

```python
for chunk, meta in app.stream(inputs, config, stream_mode="messages"):
    print(meta["langgraph_node"], chunk.content)     # 知道 token 来自哪个节点
```

本例用原生 OpenAI SDK，需要自己写 `get_stream_writer()` 并通过 `stream_mode="custom"` 输出：

```python
from langgraph.config import get_stream_writer

def llm_node(state):
    writer = get_stream_writer()
    stream = client.chat.completions.create(..., stream=True)
    for chunk in stream:
        if chunk.choices[0].delta.content:
            writer({"token": chunk.choices[0].delta.content})   # 前端直接消费
    ...
```

节点事件接前端时，建议统一成 `{thread_id, node, step, event, ts, payload}` 结构；`thread_id` 贯穿日志、指标与追踪，生产观测细节详见第 09 章。

## 人在环路（Human-in-the-loop）

关键节点暂停，等人工确认后继续——金融、运维场景的刚需：

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

def approval_node(state: AgentState) -> dict:
    decision = interrupt({"pending_action": state["messages"][-1]["content"]})
    return {"messages": [{"role": "assistant", "content": f"审批结果: {decision}"}]}

app = graph.compile(checkpointer=MemorySaver())     # 必须有 checkpointer
config = {"configurable": {"thread_id": "task-001"}}
app.invoke({"messages": [{"role": "user", "content": "删除旧数据"}], "steps": 0}, config)

# 人工在前端审批后，从断点恢复
app.invoke(Command(resume={"approved": True, "comment": "同意"}), config)
```

典型插入位置：发邮件前、下单前、删数据前。`interrupt` 会抛异常暂停并在 checkpoint 落盘，恢复时从该节点重新进入。

## 断点续跑（Checkpointer）

LangGraph 在每个 super-step 结束后把 State 快照写入 Checkpointer：

| 后端 | 适用 |
| --- | --- |
| `MemorySaver` | 开发调试（进程退出即丢） |
| `SqliteSaver` | 单机生产 |
| `PostgresSaver` | 分布式生产 |

- **崩溃恢复**：同 `thread_id` 重新 `invoke`，从最后完成的步继续
- **时间旅行**：`get_state_history(config)` 回看任意检查点，改输入重跑
- **多会话隔离**：`thread_id` 即会话 ID，天然支持多用户

## 子图与多 Agent 编排

编译后的图可以直接当节点用：

```python
research_app = research_graph.compile()

parent = StateGraph(AgentState)             # research_graph / write_node 略
parent.add_node("research", research_app)   # 编译图作为子图节点
parent.add_node("write", write_node)
parent.add_edge(START, "research")
parent.add_edge("research", "write")
```

子图与父图**同名 State key 自动透传**；schema 不同时用一个包装节点做字段映射。子图内可用 `Command(graph=Command.PARENT, goto="write")` 跳回父图。主管-工人、流水线等模式都建立在此机制上，模式细节详见第 08 章。

## 节点级重试、超时与错误边

```python
from langgraph.types import RetryPolicy

graph.add_node("llm", llm_node, retry_policy=RetryPolicy(
    max_attempts=3, initial_interval=0.5, backoff_factor=2.0))
```

- **重试**：只对幂等节点开；写操作要先确认，否则重试等于重复执行
- **超时**：LangGraph 无统一节点超时参数，在节点内用 `asyncio.wait_for(...)` 或 SDK 自带 timeout 控制
- **错误边**：节点内捕获异常写入 `state["error"]`，条件边据此走降级节点

```python
def safe_tool_node(state: AgentState) -> dict:
    try:
        return tool_node(state)
    except Exception as e:
        return {"messages": [{"role": "assistant", "content": "工具暂不可用"}], "error": str(e)}

def after_tools(state: AgentState) -> str:
    return "fallback" if state.get("error") else "llm"

def fallback_node(state: AgentState) -> dict:
    return {"messages": [{"role": "assistant", "content": "服务降级，请稍后再试"}]}

# 用条件边替换原来的固定边 graph.add_edge("tools", "llm")
graph.add_node("fallback", fallback_node)
graph.add_conditional_edges("tools", after_tools, {"llm": "llm", "fallback": "fallback"})
```

（`error` 是未注解字段，覆盖语义；降级节点负责返回可用的兜底答案并上报告警。注意 `error` 一旦写入就不会自动清除，恢复主链路前要在节点里显式置空。）

## 测试与调试

**单测节点**：节点就是纯函数，构造固定 State 直接断言，不需要起图。

```python
def test_router_goes_to_tools():
    state = {"messages": [{"role": "assistant", "content": "", "tool_calls": [
        {"id": "1", "type": "function", "function": {"name": "x", "arguments": "{}"}}]}],
        "steps": 1}
    assert router(state) == "tools"

def test_tool_node_error_is_captured():
    state = {"messages": [{"role": "assistant", "tool_calls": [
        {"id": "1", "type": "function", "function": {"name": "nope", "arguments": "{}"}}]}],
        "steps": 1}
    out = tool_node(state)["messages"][0]
    assert "error" in out["content"]
```

**回放 checkpoint**：

```python
snap = app.get_state(config)
print(snap.next, snap.values["steps"])              # 下一步要去哪、当前状态

for h in app.get_state_history(config):             # 从新到旧
    print(h.config["configurable"]["checkpoint_id"], h.next)

app.update_state(config, {"steps": 0})              # 改状态后重跑
app.invoke(None, config)                            # None = 沿用当前 state
```

**定位路由错误**：先用 `stream_mode="updates"` 看实际走过哪些节点；再查 `snap.next` 是否符合预期。也可以 `print(app.get_graph().draw_mermaid())` 把图导出成 Mermaid 核对边。常见原因：router 返回的 key 不在映射表、漏写 `END` 映射、`steps` 判断差一、工具节点后误把 `tool` 消息当 assistant 判断。

## 什么时候不要用 LangGraph

- 线性两步流程（RAG：检索 → 生成）——普通函数更直观
- 单次模型调用、无状态、无审批——引入图只是多一层抽象
- 简单 `if/else` 分支——用图会让读者先学概念再看业务
- 团队没有持久化/运维能力——Checkpointer 用不好反而制造状态不一致

**边界**：当需求出现「循环 + 持久化 + 人工审批 + 并行分支」中的两项以上，图的收益才开始大于成本；否则手写循环（见第 05 章）足够。

## LangGraph vs 手写循环 vs LangChain Agent

| 维度 | 手写循环 | LangChain Agent | LangGraph |
| --- | --- | --- | --- |
| 流程可控性 | 低 | 低 | **高（显式图）** |
| 人工审批 | 自己写 | 插件机制 | interrupt 原生 |
| 断点续跑 | 自己持久化 | 无 | Checkpointer 原生 |
| 并行分支 | 不支持 | 不支持 | 原生支持 |
| 上手成本 | 零 | 低 | 中 |
| 适用 | 学习/玩具 | 简单工具调用 | 生产级复杂 Agent |

## 工程实践建议

1. **先画流程图再写代码**：节点和边在纸上定下来，代码只是翻译
2. **State 保持精简**：只放流转必需字段，大对象存外部、State 里放引用
3. **每个节点幂等**：节点可能被重放，副作用要可重入
4. **条件路由里放刹车**：步数、预算上限都写在 router 里
5. **生产必配 Checkpointer**：没有它就没有恢复和人工审批

## 生产化清单

| 项 | 要求 |
| --- | --- |
| Checkpointer | 生产用 Postgres/Sqlite，禁止 `MemorySaver` |
| thread_id | 使用 `用户ID:会话ID` 命名，禁止复用/随机缺失 |
| interrupt | 所有写操作、外发动作前置审批 |
| 预算 | `recursion_limit` + token/费用上限，超限走降级 |
| 幂等 | 节点与工具可重放，写操作带幂等键 |
| 版本化 | 图结构变更时升版本，旧 thread 的 state 需迁移或归档 |
| 观测 | 每步记录 node、耗时、token、tool 调用与错误 |
| 告警 | 步数超限、降级触发、工具错误率异常时主动告警 |

## 常见问题

**Q：LangGraph 和 `create_react_agent` 什么关系？**
A：后者就是一张预制的「llm ⇄ tools」图。简单场景直接用预制图，需要定制节点、审批、并行时再自己画。

**Q：interrupt 暂停后进程重启会丢吗？**
A：不会，前提是用持久化 Checkpointer（Sqlite/Postgres）。状态在库里，新进程用同 `thread_id` 即可恢复；`MemorySaver` 会丢。

**Q：能不用 LangChain 的模型封装吗？**
A：可以。节点是普通 Python 函数，里面调 OpenAI SDK、Anthropic SDK 或本地 vLLM 都行，LangGraph 只管编排。

**Q：图会不会过度设计？我的 Agent 只有两步。**
A：会。两步以内的线性流程用普通函数即可，图的收益在分支、循环、审批、恢复这些非线性需求上。

## 自测

1. StateGraph 的四要素是什么？条件边与普通边的区别？
2. `add_messages` 与 `operator.add` 各适用于什么场景？为什么并行分支不能依赖拼接顺序？
3. 实现人工审批需要哪些 API？Checkpointer 在其中起什么作用？
4. 如何用固定 State 单测路由函数？如何回放某个 checkpoint 重跑？

## 参考与官方链接

- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [LangGraph Human-in-the-loop](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/)
- [LangGraph 持久化与 Checkpointer](https://langchain-ai.github.io/langgraph/concepts/persistence/)
- [LangGraph 多 Agent 模式](https://langchain-ai.github.io/langgraph/concepts/multi_agent/)
- [LangGraph 流式输出](https://langchain-ai.github.io/langgraph/concepts/streaming/)
