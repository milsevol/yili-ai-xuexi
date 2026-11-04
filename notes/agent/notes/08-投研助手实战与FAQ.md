# 08 投研助手实战与FAQ

## 一句话

**本章把前 7 章焊成一个实战项目：金融投研助手 Agent**——用户问「帮我分析宁德时代最近的投资价值」，Agent 自主调用行情查询、财报检索、计算器、新闻搜索四个工具，RAG 读研报，多轮推理后输出结构化分析。架构采用 LangGraph 状态机 + Function Calling 工具 + 向量库 RAG，是把 Agent 落地生产的标准姿势。

## 需求与架构

### 目标

输入：自然语言投研问题（「宁德时代最近投资价值如何」）
输出：结构化分析（基本面 + 行情 + 舆情 + 估值 + 风险提示）

### 整体架构

```
                ┌────────────────────────────────────────┐
                │              LangGraph 状态机            │
                │                                        │
                │  ┌──────┐   ┌────────┐   ┌─────────┐  │
  用户问题 ────→ │ 规划节点 │ → │ LLM 决策 │ ⇄ │ 工具执行  │  │
                │ (可选) │   │ (ReAct) │   │  节点    │  │
                │  └──────┘   └────────┘   └────┬────┘  │
                │                                │        │
                │                        ┌───────▼──────┐ │
                │                        │  汇总生成节点  │──→ 结构化报告
                │                        └──────────────┘ │
                └────────────────────────────────────────┘
                                     │
        ┌────────────┬───────────────┼────────────┬─────────────┐
        ▼            ▼               ▼            ▼             ▼
   行情查询工具   财报检索工具      计算器工具    新闻搜索工具    研报 RAG
   (实时API)    (财务数据库)     (本地执行)    (搜索API)     (向量库)
```

设计决策对应前面章节：

| 决策 | 选择 | 依据（章节） |
| --- | --- | --- |
| 推理范式 | Function Calling + ReAct 循环 | 结构化免解析（04） |
| 编排框架 | LangGraph | 要审批点和断点续跑（05） |
| 单/多 Agent | 单 Agent + 多工具 | 任务不需要角色分工（06） |
| 研报知识 | RAG 向量检索 | 私有研报接入（01） |
| 记忆 | 对话摘要 + 用户偏好向量库 | 防上下文爆（07） |

## 工具层实现

四个工具都遵循「原子性 + 幂等 + 错误可恢复」三原则：

```python
import json, re

# ---------- 工具 1：行情查询 ----------
def get_stock_price(symbol: str) -> str:
    """查询 A 股最新行情。symbol: 6位代码如 300750"""
    if not re.fullmatch(r"\d{6}", symbol):
        return json.dumps({"error": "股票代码须为 6 位数字"}, ensure_ascii=False)
    try:
        q = market_api.quote(symbol)          # 伪代码：对接行情源
        return json.dumps({"symbol": symbol, "price": q.price,
                           "pct_chg": q.pct, "turnover亿": q.turnover / 1e8},
                          ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"行情查询失败: {e}"}, ensure_ascii=False)

# ---------- 工具 2：财报检索 ----------
def get_financials(symbol: str, indicators: list[str]) -> str:
    """查询财务指标。indicators 可选: revenue/net_profit/roe/gross_margin/debt_ratio"""
    valid = {"revenue", "net_profit", "roe", "gross_margin", "debt_ratio"}
    bad = set(indicators) - valid
    if bad:
        return json.dumps({"error": f"未知指标 {bad}，可选: {sorted(valid)}"}, ensure_ascii=False)
    data = fin_db.query(symbol, indicators)    # 伪代码
    return json.dumps({"symbol": symbol, "latest_quarter": data}, ensure_ascii=False)

# ---------- 工具 3：计算器 ----------
def calculator(expression: str) -> str:
    """计算数学表达式。用于估值、增速、仓位计算"""
    if not re.fullmatch(r"[\d\s\.\+\-\*\/\(\)%]+", expression):
        return json.dumps({"error": "表达式含非法字符"}, ensure_ascii=False)
    try:
        result = eval(expression, {"__builtins__": {}})
        return json.dumps({"result": round(result, 4)})
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

# ---------- 工具 4：新闻搜索 ----------
def search_news(query: str, days: int = 7) -> str:
    """搜索最近财经新闻。返回标题+日期+摘要，最多5条"""
    hits = news_api.search(query, days=days)   # 伪代码
    return json.dumps([
        {"date": h.date, "title": h.title, "summary": h.summary[:150]}
        for h in hits[:5]                       # 源头裁剪：top5 + 摘要截断
    ], ensure_ascii=False)

TOOLS = {
    "get_stock_price": get_stock_price,
    "get_financials": get_financials,
    "calculator": calculator,
    "search_news": search_news,
}
```

**注意 `search_news` 的源头裁剪**（top5 + 摘要 150 字）——这是第 07 章「工具结果压缩」的第一层防御。

## RAG：研报检索

```python
from dataclasses import dataclass

@dataclass
class ReportChunk:
    text: str
    source: str      # 研报名
    date: str

class ReportRAG:
    """研报向量库：切块 → 嵌入 → 检索 → 注入"""

    def __init__(self):
        self.chunks: list[tuple[list[float], ReportChunk]] = []

    def ingest(self, report_text: str, source: str, date: str):
        for chunk in split_by_section(report_text, max_len=500):  # 按章节切块
            self.chunks.append((embed(chunk), ReportChunk(chunk, source, date)))

    def search(self, query: str, top_k: int = 3) -> str:
        q = embed(query)
        top = sorted(self.chunks, key=lambda x: -cosine(x[0], q))[:top_k]
        # 注入时带来源标注，方便引用且防幻觉
        return "\n\n".join(
            f"【{c.source} {c.date}】{c.text}" for _, c in top
        )

report_rag = ReportRAG()

def search_reports(query: str) -> str:
    """检索内部研报库中与 query 相关的段落"""
    result = report_rag.search(query)
    return result if result else json.dumps({"error": "研报库中未找到相关内容"})
```

## LangGraph 组装

```python
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver

SYSTEM = """你是投研助手。回答投资问题时：
1. 先用 search_reports 查内部研报观点
2. 用 get_stock_price / get_financials 拿硬数据
3. 涉及估值计算必须用 calculator，不许口算
4. 用 search_news 补充近期舆情
5. 结论必须区分「事实」「观点」「风险」三部分
数据不足就明说，禁止编造。"""

class State(TypedDict):
    messages: Annotated[list, add_messages]
    steps: int

def llm_node(state: State) -> dict:
    msgs = [{"role": "system", "content": SYSTEM}] + state["messages"]
    resp = client.chat(msgs, tools=TOOL_SCHEMAS)      # Function Calling
    return {"messages": [resp.choices[0].message], "steps": state["steps"] + 1}

def tool_node(state: State) -> dict:
    out = []
    for tc in state["messages"][-1].tool_calls:
        fn = TOOLS.get(tc.function.name)
        if fn is None:
            result = json.dumps({"error": f"工具 {tc.function.name} 不存在"})
        else:
            try:
                result = fn(**json.loads(tc.function.arguments))
            except Exception as e:
                result = json.dumps({"error": str(e)})     # 错误回灌不中断
        out.append({"role": "tool", "tool_call_id": tc.id, "content": result})
    return {"messages": out}

def router(state: State) -> str:
    if state["steps"] >= 8:                               # 刹车：步数上限
        return END
    return "tools" if state["messages"][-1].tool_calls else END

g = StateGraph(State)
g.add_node("llm", llm_node)
g.add_node("tools", tool_node)
g.add_edge(START, "llm")
g.add_conditional_edges("llm", router, {"tools": "tools", END: END})
g.add_edge("tools", "llm")

app = g.compile(checkpointer=SqliteSaver("invest.db"))     # 断点续跑

def ask(question: str, session: str = "u001") -> str:
    cfg = {"configurable": {"thread_id": session}}
    r = app.invoke({"messages": [("user", question)], "steps": 0}, cfg)
    return r["messages"][-1].content

# ask("帮我分析宁德时代(300750)最近的投资价值")
```

### 预期执行轨迹

```
[1] llm: 需要研报观点 → search_reports("宁德时代 动力电池 竞争格局")
[2] tools → 返回 2 段研报摘录
[3] llm: 拿硬数据 → get_stock_price("300750") + get_financials("300750", [...])（并行）
[4] tools → 行情 + 财报数据
[5] llm: 算增速 → calculator("(680-520)/520*100")
[6] tools → 30.77
[7] llm: 查舆情 → search_news("宁德时代", days=7)
[8] tools → 4 条新闻
[9] llm: 信息齐全 → 输出结构化报告（事实/观点/风险）
```

## 上线前检查清单

- [ ] 迭代上限（steps >= 8 强制收敛）
- [ ] token 预算告警（单次任务 > 50K token 报警）
- [ ] 工具白名单与参数 Schema 校验
- [ ] 行情/财报数据源异常时的降级话术
- [ ] **合规声明**：输出固定携带「非投资建议」免责语
- [ ] 全链路 trace 落库（每次调用存 messages + tool_calls，方便审计复盘）

## 面试 FAQ

**Q1：什么是 Agent？和 LLM、RAG 的关系？**
A：Agent = LLM + 规划 + 记忆 + 工具使用，能自主多轮决策完成任务。LLM 是大脑，RAG 是 Agent 可用的一种工具（检索增强），Agent 是更上层的编排范式。演进链：Prompt → RAG → Agent → 多 Agent。

**Q2：ReAct 的核心思想？和 CoT 的区别？**
A：ReAct 把推理（Thought）与行动（Action）交织，每轮：思考 → 调工具 → 观察结果 → 再思考。CoT 只有推理没有行动，无法获取外部信息，幻觉率高；ReAct 用工具返回的 Observation 做事实锚点。生产上 ReAct 多以 Function Calling 形式实现。

**Q3：Function Calling 的完整流程？**
A：① 注册工具 Schema（名称/描述/JSON Schema 参数）→ ② 模型返回 tool_calls（不执行！）→ ③ 应用层执行函数 → ④ 结果以 role="tool" 消息（带 tool_call_id）回灌 → ⑤ 模型生成最终答案。安全边界在于模型只表达调用意图，执行权在应用层。

**Q4：工具设计有哪些原则？**
A：① 原子性——一个工具一件事，模型可自由组合；② 幂等性——可安全重试，写操作用幂等键；③ 错误可恢复——返回结构化错误文本而非异常，让模型自我纠错；④ 返回精简——源头裁剪防上下文爆炸；⑤ 数量克制——超过 20 个按场景分组加载。

**Q5：MCP 是什么？解决了什么问题？**
A：Model Context Protocol，Anthropic 主导的工具接入标准。没有它 N 个应用 × M 个工具 = N×M 定制集成；有了它工具方实现一次 MCP Server（暴露 Tools/Resources/Prompts 三类能力），所有 MCP Host（Claude/Cursor/自研 Agent）即插即用。传输用 JSON-RPC over stdio/SSE/HTTP。它和 Function Calling 不冲突：FC 是模型↔应用的协议，MCP 是应用↔工具的协议。

**Q6：为什么用 LangGraph 而不是手写循环？**
A：四个生产刚需：① 显式图结构让流程可控可观测；② interrupt 原生支持人工审批；③ Checkpointer 支持断点续跑和崩溃恢复；④ 原生并行分支。手写循环这些都要自己造。简单场景（< 5 步、无审批）手写循环或 create_react_agent 就够。

**Q7：什么时候该用多 Agent？**
A：四个信号：任务天然分角色（研究+写作+审核）、单一上下文被污染（搜索 Agent 的网页噪音 vs 报告 Agent 的干净结论）、子任务可并行、子任务适合不同模型。不该用的情况：任务线性且短、步骤强依赖共享上下文、预算紧张。多 Agent 成本通常是单 Agent 的 3-10 倍，先优化单 Agent 再考虑拆分。

**Q8：Agent 上下文爆炸怎么治？**
A：分层治理：① 短期记忆——System 和用户目标永保留，最近 N 轮完整保留，更早的摘要化；② 工具结果——源头裁剪（top-K + 截断）、大结果外部化存文件、历史结果降级为一行摘要；③ 长期记忆——事实入向量库，用时检索注入（top_k 3-5 条）；④ 监控——prompt_tokens 达窗口 70% 触发压缩。

**Q9：如何防止 Agent 死循环和幻觉工具调用？**
A：死循环：max_iterations 硬上限 + 相同 (tool, args) 重复检测 + Prompt 明示「2 次无新信息就回答」。幻觉工具：Function Calling 结构化输出（模型只能在注册的 Schema 里选）+ 白名单校验 + 不存在时返回可用工具列表让其自纠。

**Q10：Agent 系统怎么做评估？**
A：三层：① 端到端——固定测试集跑任务成功率/人工评分；② 组件级——每个工具单元测试、路由准确率；③ 轨迹级——审计每次运行的完整 trace（轮数、token、工具选择合理性），用 LLM-as-Judge 打分轨迹质量。上线后持续收集失败 case 回流成测试集。

**Q11：Agent 的延迟和成本怎么优化？**
A：延迟——独立工具并行调用（parallel_tool_calls）、小模型做前置路由/检索、减少轮数（更好的工具描述减少试探）。成本——分层用模型（贵的只做最终综合）、工具结果压缩、相同查询缓存、设置 token 预算硬上限。

**Q12：Function Calling 的输出如何保证 JSON 合法？**
A：① 模型侧：厂商对 FC 输出做约束解码（OpenAI 的 strict: true 保证 100% 符合 Schema）；② 应用侧：json.loads 失败时把解析错误回灌让模型重试；③ 兜底：正则提取 + 默认值填充。

## 自测

1. 画出投研助手的 LangGraph 节点图，标注每条边的类型（固定/条件）。
2. 为什么 `search_news` 要在工具内部做 top5 + 摘要截断？
3. 预期轨迹第 3 步为什么可以并行？代码上如何支持？
4. 面试被问「Agent 和普通工作流的区别」，怎么用一句话回答？

## 参考与官方链接

- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
- [MCP 规范](https://modelcontextprotocol.io/)
- [Anthropic: Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
- [ReAct 论文](https://arxiv.org/abs/2210.03629)
