# 05 LangGraph 状态机

## 一句话

**LangGraph 把 Agent 建模为一张状态图（StateGraph）**：节点是执行单元（调 LLM / 调工具 / 人工审批），边是流转规则（含条件分支），状态在节点间流转并被检查点持久化。相比 ReAct 自由循环，图编排换来的是**可控、可观测、可断点续跑**——这是 Agent 从 Demo 走向生产的关键一步。

## 为什么用图编排 Agent

ReAct 自由循环的痛点：

- 流程藏在模型的自由发挥里，**无法预知路径**，出了问题只能翻日志
- 想插入人工审批、想在崩溃后恢复，自由循环没有抓手
- 多步骤任务中想让某几步并行，循环结构表达不了

图（Graph）是更通用的计算模型：分支、循环、并行都能表达，且**流程显式可见**。

```
ReAct：一个黑盒 while 循环，模型说了算
LangGraph：一张你画的图，模型只在节点内发挥，走哪条边由你控制
```

**一句话区分**：LangChain Agent 是「模型指挥流程」，LangGraph 是「你设计流程、模型填内容」。

## StateGraph 核心概念

### 四要素

| 概念 | 说明 | 代码对应 |
| --- | --- | --- |
| State | 全局共享状态，所有节点可读可写 | `TypedDict` / `dataclass` |
| Node | 节点函数：接收 State，返回对 State 的局部更新 | `def node(state) -> dict` |
| Edge | 边：固定流转（A→B） | `add_edge("a", "b")` |
| Conditional Edge | 条件边：根据 State 动态决定去向 | `add_conditional_edges("a", router_fn)` |

### 最小示例：一个会循环的工具调用 Agent

```python
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

# ① 定义状态：messages 字段用 add_messages 规约（追加而非覆盖）
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    steps: int

# ② 定义节点
def llm_node(state: AgentState) -> dict:
    resp = model_with_tools.invoke(state["messages"])
    return {"messages": [resp], "steps": state["steps"] + 1}

def tool_node(state: AgentState) -> dict:
    last = state["messages"][-1]
    results = [execute(tc) for tc in last.tool_calls]
    return {"messages": results}

# ③ 条件路由：模型还要调工具就去 tool_node，否则结束
def router(state: AgentState) -> str:
    if state["steps"] > 8:                    # 刹车：步数上限
        return END
    last = state["messages"][-1]
    return "tools" if last.tool_calls else END

# ④ 组装图
g = StateGraph(AgentState)
g.add_node("llm", llm_node)
g.add_node("tools", tool_node)
g.add_edge(START, "llm")
g.add_conditional_edges("llm", router, {"tools": "tools", END: END})
g.add_edge("tools", "llm")                    # 工具结果回灌，形成循环

app = g.compile()
result = app.invoke({"messages": [("user", "茅台涨5%后多少钱？")], "steps": 0})
```

### 状态规约（Reducer）

多个节点更新同一个 State 字段时怎么合并？由字段上的 reducer 决定：

- `Annotated[list, add_messages]`：追加（对话历史场景）
- `Annotated[int, operator.add]`：累加（计数器场景）
- 无注解：直接覆盖（标记位场景）

## 人在环路（Human-in-the-loop）

关键节点暂停执行，等人工确认/修改后继续——金融、运维场景的刚需：

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

def approval_node(state: AgentState):
    decision = interrupt({                     # ← 暂停点：把状态存盘，等人来
        "pending_action": state["messages"][-1].content
    })
    if decision["approved"]:
        return {"approved": True}
    return {"approved": False, "feedback": decision["comment"]}

app = g.compile(checkpointer=MemorySaver())
config = {"configurable": {"thread_id": "task-001"}}

app.invoke(input_data, config)                 # 跑到 interrupt 处暂停
# ... 人工在前端审批 ...
app.invoke(Command(resume={"approved": True}), config)  # 从断点恢复
```

典型插入位置：发邮件前、下单前、删数据前。

## 断点续跑（Checkpointer）

LangGraph 在**每个超级步（super-step）结束**后自动把 State 快照存入 Checkpointer：

| 后端 | 适用 |
| --- | --- |
| `MemorySaver` | 开发调试 |
| `SqliteSaver` | 单机生产 |
| `PostgresSaver` | 分布式生产 |

带来的能力：

- **崩溃恢复**：进程挂了，用同一个 thread_id 重新 invoke 即从上一步继续
- **时间旅行**：回到任意历史检查点，换个输入重新走（调试神器）
- **多会话隔离**：thread_id 即会话 ID，天然支持多用户

## 进阶：并行与分支

```python
# 扇出：一个节点同时触发多个节点
g.add_edge("planner", "researcher_a")
g.add_edge("planner", "researcher_b")
# 扇入：多个节点完成后汇合（需等全部到达）
g.add_edge("researcher_a", "writer")
g.add_edge("researcher_b", "writer")
```

LangGraph 自动处理并发执行和汇合等待，State 的 reducer 负责合并多个并行节点的更新。

## LangGraph vs 手写循环 vs LangChain Agent

| 维度 | 手写 ReAct 循环 | LangChain Agent | LangGraph |
| --- | --- | --- | --- |
| 流程可控性 | 低 | 低 | **高（显式图）** |
| 人工审批 | 自己写 | 插件机制 | interrupt 原生支持 |
| 断点续跑 | 自己持久化 | 无 | Checkpointer 原生 |
| 并行分支 | 不支持 | 不支持 | 原生支持 |
| 上手成本 | 零 | 低 | 中 |
| 适用 | 学习/玩具 | 简单工具调用 | 生产级复杂 Agent |

## 工程实践建议

1. **先画流程图再写代码**：节点和边在纸上定下来，代码只是翻译
2. **State 保持精简**：只放流转必需字段，大对象存外部、State 里放引用
3. **每个节点幂等**：节点可能被重放（断点续跑），副作用要可重入
4. **条件路由里放刹车**：步数上限、预算上限都写在 router 里
5. **生产必配 Checkpointer**：没有它就没有恢复和人工审批

## 常见问题

**Q：LangGraph 和 LangChain Agent（create_react_agent）什么关系？**
A：LangChain 的 Agent 底层已经用 LangGraph 实现了——`create_react_agent` 就是一张预制的「llm ⇄ tools」图。简单场景直接用预制图，需要定制流程再自己画。

**Q：interrupt 暂停后进程重启会丢吗？**
A：不会，前提是用了持久化 Checkpointer（Sqlite/Postgres）。状态在库里，新进程用同 thread_id 即可恢复。用 MemorySaver 才会丢。

**Q：LangGraph 能不用 LangChain 的模型封装吗？**
A：可以。节点就是普通 Python 函数，里面想调 OpenAI SDK、Anthropic SDK 还是本地 vLLM 都行，LangGraph 只管编排不管调用。

**Q：图会不会过度设计？我的 Agent 只有两步。**
A：会。两步以内的线性流程（如 RAG：检索→生成）用普通函数即可。图的收益在分支、循环、审批、恢复这些**非线性**需求上。

## 自测

1. StateGraph 的四要素是什么？条件边和普通边的区别？
2. Reducer 解决什么问题？`add_messages` 和 `operator.add` 各自的语义？
3. 实现人工审批需要哪两个 API？Checkpointer 在其中起什么作用？
4. 为什么说「LangChain Agent 是模型指挥流程，LangGraph 是你设计流程」？

## 参考与官方链接

- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [LangGraph Human-in-the-loop 指南](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/)
- [LangGraph 持久化与 Checkpointer](https://langchain-ai.github.io/langgraph/concepts/persistence/)
- [LangGraph 多 Agent 模式](https://langchain-ai.github.io/langgraph/concepts/multi_agent/)
