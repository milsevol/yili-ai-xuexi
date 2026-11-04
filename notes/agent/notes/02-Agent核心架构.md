# 02 Agent核心架构

## 一句话

**Agent 的三大要素是规划（Planning）、记忆（Memory）、工具（Tools）**，三者围绕「感知 → 决策 → 行动」循环运转：感知拿到环境和历史，规划决定下一步，工具执行动作，记忆沉淀中间结果。架构选型上，简单场景用 ReAct 单循环，复杂场景用 LangGraph 显式状态机。

## 三要素总览

```
                    ┌─────────────────┐
                    │      用户目标     │
                    └────────┬────────┘
                             ▼
              ┌──────────────────────────┐
              │       Planning 规划       │ ← 拆解目标、决定下一步
              │  （LLM 推理 + 任务分解）   │
              └──────┬───────────┬───────┘
                     │           │
            ┌────────▼───┐   ┌───▼────────┐
            │ Memory 记忆 │   │ Tools 工具  │ ← 执行动作、获取外部信息
            │ 短期+长期   │   │ 函数/API   │
            └────────┬───┘   └───┬────────┘
                     │           │
                     └─────┬─────┘
                           ▼
                     Observation 观察
                     （结果回灌给规划）
```

| 要素 | 职责 | 关键技术 |
| --- | --- | --- |
| Planning | 把目标拆成可执行步骤，每步决定调什么工具 | ReAct、CoT、Plan-and-Execute、任务分解 |
| Memory | 记住对话历史、中间结果、长期知识 | 对话缓冲、摘要压缩、向量库、知识图谱 |
| Tools | 让 Agent 能影响外部世界 | Function Calling、MCP、代码执行器 |

## 要素一：Planning（规划）

规划是 Agent 的「大脑皮层」，常见四种模式：

### 1. ReAct（边想边做）

每轮生成 Thought（思考）+ Action（动作），观察结果后再进入下一轮。**不预先规划全程**，走一步看一步。

- 优点：灵活，能根据中间结果调整方向
- 缺点：步骤多了容易跑偏，无全局观
- 适用：步骤数 < 10 的中小型任务

### 2. Plan-and-Execute（先规划后执行）

先让一个 Planner LLM 生成完整计划（步骤列表），再由 Executor 逐步执行，必要时 Replan。

- 优点：全局观强，长任务不跑偏
- 缺点：计划赶不上变化，Replan 成本高
- 适用：步骤数 > 10、结构可预知的任务

### 3. CoT / ToT（思维链 / 思维树）

纯推理层技术：CoT 让模型「一步步想」，ToT 让模型同时探索多条推理路径再选最优。常作为 Planning 的子组件。

### 4. 自我反思（Reflection）

Agent 执行后自我评估「结果对吗」，不对就修正重试。代表：Reflexion 框架，把失败经验写入记忆。

## 要素二：Memory（记忆）

| 类型 | 类比 | 实现 | 生命周期 |
| --- | --- | --- | --- |
| 短期记忆 | 工作记忆 | 对话历史 buffer（list[Message]） | 单次会话 |
| 长期记忆 | 知识库 | 向量库检索、KV 存储、知识图谱 | 跨会话持久 |
| 程序性记忆 | 肌肉记忆 | Few-shot 示例、学到的技能/SOP | 固化在 Prompt/配置 |

短期记忆的核心工程问题是**上下文窗口不够**：多轮工具调用的结果很快撑爆窗口，需要截断/摘要策略（详见第 07 章）。

## 要素三：Tools（工具）

工具是 Agent 的「手和脚」。一个工具 = 名称 + 描述 + 参数 Schema + 执行函数：

```python
tool = {
    "name": "get_stock_price",
    "description": "查询股票最新价格。输入股票代码，返回最新价和涨跌幅。",
    "parameters": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "股票代码，如 600519"}
        },
        "required": ["symbol"]
    }
}
```

**工具设计三原则**（详见第 04 章）：
1. **原子性**：一个工具只做一件事，别设计「查股价并算出估值并发邮件」的巨无霸工具
2. **幂等性**：同样的输入调用多次结果一致，允许 Agent 安全重试
3. **错误可恢复**：返回结构化错误信息让模型能自我纠错，而不是抛异常中断循环

## 感知-决策-行动循环

这是所有 Agent 的统一骨架，对应强化学习的经典循环：

```
        ┌──────────────────────────────────────┐
        │                                      │
        ▼                                      │
   [感知 Perceive]                      [行动 Act]
   读取用户输入/工具结果/记忆    ──→    调用工具/输出答案
        │                                      ▲
        ▼                                      │
   [决策 Decide]                         [环境反馈]
   LLM 推理：现在该做什么？        工具返回 Observation
```

用 Python 表达最小骨架：

```python
def agent_loop(goal: str, tools: dict, max_iter: int = 10):
    messages = [{"role": "user", "content": goal}]
    for i in range(max_iter):                    # ← 刹车 1：迭代上限
        resp = llm.chat(messages, tools=tools)   # 决策：LLM 决定做什么
        if resp.final_answer:                    # 终止条件
            return resp.final_answer
        for call in resp.tool_calls:             # 行动
            result = execute_tool(call, tools)   # 执行 + 异常兜底
            messages.append(tool_msg(call, result))  # 感知：结果回灌
    return "达到最大迭代次数，任务未完成"
```

**三个关键工程点**：
1. **终止条件**：模型显式给出 final_answer，或达到 max_iter
2. **消息累积**：每轮的思考和工具结果都追加进 messages，作为下轮上下文
3. **异常兜底**：工具报错不中断循环，把错误信息喂回模型让它自我修正

## 常见架构模式对比

| 模式 | 结构 | 优点 | 缺点 | 代表框架 |
| --- | --- | --- | --- | --- |
| ReAct 单循环 | LLM ↔ 工具，线性循环 | 简单直观、好调试 | 长任务跑偏 | LangChain Agent |
| Plan-and-Execute | Planner → Executor → Replan | 全局观、长任务稳 | 规划开销大、不灵活 | BabyAGI、LangGraph |
| 状态机/图 | 显式节点 + 条件边 | 可控性强、可断点续跑 | 搭建成本高 | LangGraph |
| 多 Agent | 多角色协作 | 分工明确、上下文隔离 | 协调复杂、成本翻倍 | AutoGen、CrewAI |

**选型建议**：
- 任务 < 5 步、工具 < 3 个 → ReAct 单循环就够了
- 任务步骤多、需要人工审批点、要可恢复 → LangGraph 状态机
- 任务天然分角色（研究+写作+审核）→ 多 Agent

## 一个最小可运行 Agent

```python
import json

def get_weather(city: str) -> str:
    return json.dumps({"city": city, "temp": 22, "weather": "晴"})

TOOLS = {"get_weather": get_weather}
SCHEMAS = [{
    "name": "get_weather",
    "description": "查询城市天气",
    "parameters": {"type": "object",
                   "properties": {"city": {"type": "string"}},
                   "required": ["city"]}
}]

def run(goal: str):
    messages = [{"role": "system", "content": "你是助手，可用工具回答问题。"},
                {"role": "user", "content": goal}]
    for _ in range(5):
        resp = llm.chat(messages, tools=SCHEMAS)   # 伪代码：调用 LLM API
        if not resp.tool_calls:
            return resp.content                     # 模型给出最终答案
        for tc in resp.tool_calls:
            args = json.loads(tc.arguments)
            try:
                result = TOOLS[tc.name](**args)     # 执行工具
            except Exception as e:
                result = f"工具执行失败: {e}"        # 错误回灌，不中断
            messages.append({"role": "tool", "name": tc.name, "content": result})
    return "超出迭代上限"

# run("北京今天天气怎么样，适合出门吗？")
```

这个骨架不到 30 行，但已经包含了 Agent 的全部本质：循环、工具调用、结果回灌、异常兜底、迭代上限。生产框架（LangChain/LangGraph）做的无非是把这些环节做得更健壮。

## 常见问题

**Q：三要素里哪个最容易被忽视？**
A：Memory。很多 Demo 只有 Planning + Tools，跑起来才发现多轮后上下文爆了、或者 Agent「忘了」开头的要求。记忆策略（截断/摘要/向量化）是生产化的分水岭。

**Q：Plan-and-Execute 一定比 ReAct 好吗？**
A：不一定。P&E 多一次规划调用，对短任务是浪费；且计划错误会传染给所有步骤。经验法则：预期步骤 > 10 或步骤间依赖复杂时用 P&E，否则 ReAct。

**Q：Agent 需要微调（Fine-tuning）吗？**
A：大多数场景不需要。Prompt + 好工具 + 好框架能解决 90% 问题。只有当工具调用格式要求极严、或领域术语极特殊时，才考虑在 Agent 轨迹数据上微调。

## 自测

1. 画出感知-决策-行动循环，并标注每个环节对应的代码实体。
2. ReAct 和 Plan-and-Execute 各自适合什么规模的任务？
3. 工具设计三原则是什么？为什么幂等性对 Agent 特别重要？
4. 最小 Agent 骨架里，哪三处是「刹车」？

## 参考与官方链接

- [LLM Powered Autonomous Agents（Lilian Weng）](https://lilianweng.github.io/posts/2023-06-23-agent/)
- [Plan-and-Execute（BabyAGI）](https://github.com/yoheinakajima/babyagi)
- [Reflexion 论文](https://arxiv.org/abs/2303.11366)
- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
