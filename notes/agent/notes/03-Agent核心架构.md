# 03 Agent核心架构

## 一句话

**Agent 的三大要素是规划（Planning）、记忆（Memory）、工具（Tools）**，三者围绕「感知 → 决策 → 行动」循环运转：感知拿到环境和历史，规划决定下一步，工具执行动作，记忆沉淀中间结果。架构选型不看框架热度，只看四个问题：任务多少步、有没有审批点、要不要断点恢复、是否天然分角色。

## 三要素总览

```
                ┌─────────────────┐
                │     用户目标      │
                └────────┬────────┘
                         ▼
        ┌────────────────────────────────┐
        │ Planning 规划：拆目标、定下一步   │
        └───────┬────────────────┬───────┘
                │                │
      ┌─────────▼──────┐  ┌──────▼─────────┐
      │ Memory 记忆     │  │ Tools 工具      │
      │ 四类记忆分层     │  │ 函数 / API      │
      └─────────┬──────┘  └──────┬─────────┘
                └────────┬───────┘
                         ▼
                 Observation 观察 → 回灌规划
```

| 要素 | 职责 | 关键技术 | 缺失时的典型症状 |
| --- | --- | --- | --- |
| Planning | 把目标拆成可执行步骤，每步决定调什么工具 | ReAct、CoT/ToT、Plan-and-Execute、Reflection | 原地打转、跑偏、步骤顺序错 |
| Memory | 记住目标、中间结果、长期知识 | 对话缓冲、摘要压缩、向量库、知识图谱 | 忘约束、重复取数、上下文爆窗 |
| Tools | 让 Agent 能影响外部世界 | Function Calling、MCP、代码执行器 | 幻觉工具、参数错、异常中断循环 |

## 从一个真实任务看三要素如何配合

任务：**「分析某公司最新投资价值，给我一个买/观望/回避的结论」**。这不是一次检索能答完的问题，看三要素如何逐轮咬合。

| 轮次 | Planning 在做什么 | Memory 读/写什么 | Tools 调什么 |
| --- | --- | --- | --- |
| 1 | 澄清约束、拆四条线（行情 / 财报 / 舆情 / 同业估值） | 写工作记忆：目标、约束（只看 A 股、截止今天） | `search_company` 确定股票代码 |
| 2 | 决定先取近四个季度财报，理由是估值必须基于最新 TTM | 写：ticker、报告期；读：无历史 | `get_financials` |
| 3 | 算 PE/PB，判断「贵不贵」需要同业对照 | 读语义记忆：行业 PE 中位数口径 | `get_peer_valuation`、`calculator` |
| 4 | 发现利润增速与现金流背离，追加一条舆情线做证伪 | 读工作记忆里的第 2 轮数字 | `search_news` |
| 5 | Reflection：毛利率口径和同业不一致，回头重取一次 | 写情景记忆：「口径不一致 → 需重取」 | `get_financials`（换口径参数） |
| 6 | 信息够了，按「结论 + 三条依据 + 风险」组织输出 | 读全部中间结果，压缩成摘要 | 无（直接回答） |

**这张表说明三件事**：Planning 不是一次性的（第 4、5 轮的追加证伪、回头重取都基于新观察）；Memory 的价值在第 5、6 轮才显现（不知道之前用了什么口径就会重复踩坑）；Tools 只是执行器，真正决定质量的是「第 4 轮想到要证伪」这种规划能力。

## 感知-决策-行动循环

所有 Agent 的统一骨架，对应强化学习的经典循环：

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

## 要素一：Planning（规划）

| 模式 | 决策粒度 | 优点 | 缺点 | 适用 |
| --- | --- | --- | --- | --- |
| ReAct | 每步一次 LLM 调用，走一步看一步 | 灵活、能随观察改方向、实现简单 | 无全局观，步数多了跑偏 | 步骤 < 10 的探索型任务 |
| Plan-and-Execute | 先出完整计划，再逐步执行，失败 Replan | 全局观强、长任务稳定、计划可审查 | 多一次规划调用，计划错误会传染 | 步骤 > 10、结构可预知 |
| CoT / ToT | 纯推理内部分支，不产生行动 | 提升单步推理质量，可并行探索多条路径 | 拿不到外部事实，token 开销大 | 数学、逻辑、方案比选 |
| Reflection | 执行后自评，不合格就修正重试 | 显著降低「做完了但是错的」 | 多一轮调用，可能陷入自我否定 | 有明确验收标准的任务 |

> 关键认知：这四者不是互斥的。生产系统常见组合是 **Plan-and-Execute 做骨架 + 每步内部 ReAct + 交付前 Reflection**。ReAct 的完整机制与 trace 详见第 04 章。

### Plan-and-Execute：Planner / Executor / Replan

```
目标 ──→ Planner（输出 JSON 计划）──→ Executor 逐步执行
                  ▲                        │
                  │      失败/信息不足       │
                  └──────── Replan ◄────────┘
```

以下为伪代码级实现（工具为打桩，省略日志与持久化）：

```python
import json, os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
MODEL = "deepseek-chat"

def make_plan(goal: str, tools_desc: str, feedback: str = "") -> list[dict]:
    """Planner：只规划不执行，强制 JSON 输出，失败时带 feedback 重规划。"""
    prompt = f"""把目标拆成 2~6 步计划。每步字段：
step(序号) / action(工具名或 "think") / args(工具参数对象) / expect(预期产出)。
只输出 JSON：{{"steps": [...]}}
可用工具：{tools_desc}
目标：{goal}
{("上一轮失败信息，必须修正：" + feedback) if feedback else ""}"""
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(resp.choices[0].message.content)["steps"]

def run_plan(goal: str, tools: dict, max_replans: int = 2) -> str:
    tools_desc = "；".join(f"{k}: {v.__doc__}" for k, v in tools.items())
    feedback, results = "", []
    for _ in range(max_replans + 1):
        steps, failed = make_plan(goal, tools_desc, feedback), ""
        for s in steps:
            name, args = s.get("action", "think"), s.get("args", {})
            if name == "think":
                results.append(f"[思考] {s.get('expect', '')}")
                continue
            if name not in tools:
                failed = f"第 {s['step']} 步：工具 {name} 不存在"
                break
            try:
                results.append(f"[{name}] {tools[name](**args)}")
            except Exception as e:
                failed = f"第 {s['step']} 步 {name} 执行失败：{e}"
                break
        if not failed:
            return "\n".join(results)
        feedback = failed                    # 失败 → 只重规划剩余部分
        results.append(f"[Replan] {failed}")
    return "多次重规划仍失败：\n" + "\n".join(results)
```

Planner 用 `json_object` 约束输出、计划里显式写 `expect` 便于校验、Replan 时把**失败原因**作为输入而不是从头再来。工具实现见本章最后一节。

## 要素二：Memory（记忆）

| 类型 | 存什么 | 落在哪个组件 | 典型实现 | 生命周期 |
| --- | --- | --- | --- | --- |
| 工作记忆 | 当前目标、当前计划、最近几轮 Observation | 控制循环维护的 `messages` | `list[Message]` + 截断策略 | 单次任务 |
| 情景记忆 | 具体经历：哪次取数失败、为什么 Replan | 任务日志 / 向量库（按任务检索） | trace JSON、episodic store | 跨任务可检索 |
| 语义记忆 | 领域事实与口径：行业均值、指标定义 | RAG 知识库 / 长期存储 | 向量库、知识图谱、SQL | 长期，需更新 |
| 程序性记忆 | 怎么做：工具用法、SOP、成功轨迹 | System Prompt / Few-shot / 技能库 | few-shot 示例、prompt 模板 | 版本化管理 |

**读写时机**：工作记忆每轮读写；情景记忆在任务结束或 Replan 时写入，新任务开始时按相似度检索；语义记忆在「需要事实」时按需检索；程序性记忆随版本发布更新，不随对话变化。四类里最容易出问题的是工作记忆——多轮工具结果很快撑爆窗口，截断与压缩策略详见第 07 章。

## 要素三：Tools（工具）

一个工具 = 名称 + 描述 + 参数 Schema + 执行函数：

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

**工具设计三原则**：
1. **原子性**：一个工具只做一件事，别设计「查股价并算出估值并发邮件」的巨无霸
2. **幂等性**：同样的输入多次调用结果一致，允许 Agent 安全重试
3. **错误可恢复**：返回结构化错误信息让模型能自我纠错，而不是抛异常中断循环

Function Calling 的消息协议、并行调用、MCP 接入方式详见第 05 章。

## 控制循环：把 Agent 关进笼子

| 机制 | 解决什么 | 实现方式 |
| --- | --- | --- |
| 终止条件 | 什么时候算完成 | 模型不再返回 `tool_calls`；或状态机到达终态节点 |
| 最大步数 | 防死循环兜底 | `max_steps`（经验值 8~15） |
| 超时 | 防单次调用挂死 | 整体 deadline + 单工具 timeout |
| 重试 | 工具偶发失败 | 指数退避重试 1~2 次，仍失败则回灌错误 |
| 预算 | 防成本失控 | 累计 `usage.total_tokens` 或金额上限 |
| 重复动作检测 | 防原地打转 | 对 `(tool, args)` 做指纹计数，重复即拒绝 |
| 异常回灌 | 让模型自我修正 | 错误转成文本塞回 `role="tool"`，不抛异常 |

```
         ┌──────────┐  steps > max ──→ [结束: max_steps]
         │  Running │  now > deadline ─→ [结束: timeout]
目标 ──→ │          │  tokens > budget → [结束: budget]
         └────┬─────┘
              │ 每轮
      ┌───────▼────────┐
      │ LLM 决策        │──无 tool_calls──→ [结束: done]
      └───────┬────────┘
              │ tool_calls
      ┌───────▼────────┐  重复指纹 → 拒绝并提示换策略
      │ 校验+执行+回灌   │──异常 → 重试 → 仍失败则回灌错误
      └───────┬────────┘
              └─────────→ 回到 Running
```

带状态的循环骨架（约 60 行，可直接嵌进项目）：

```python
import json, os, time
from dataclasses import dataclass, field
from openai import OpenAI

client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
MODEL = "deepseek-chat"

@dataclass
class AgentState:
    messages: list = field(default_factory=list)
    steps: int = 0
    tokens: int = 0
    deadline: float = 0.0
    seen: dict = field(default_factory=dict)
    status: str = "running"        # running/done/max_steps/timeout/budget

def call_with_retry(fn, raw_args: str, retries: int = 2):
    try:
        args = json.loads(raw_args or "{}")
    except json.JSONDecodeError as e:
        return f"参数不是合法 JSON：{e}"
    for i in range(retries + 1):
        try:
            return fn(**args)
        except Exception as e:                 # 异常回灌，不中断循环
            if i == retries:
                return f"工具连续失败：{e}。请修正参数或换工具。"
            time.sleep(0.5 * (i + 1))

def run_agent(goal: str, tools: dict, schemas: list,
              max_steps: int = 10, timeout_s: int = 180, token_budget: int = 60_000):
    st = AgentState(deadline=time.monotonic() + timeout_s)
    st.messages = [{"role": "system", "content": "你是严谨的任务执行者。"},
                   {"role": "user", "content": goal}]
    while st.status == "running":
        st.steps += 1
        if st.steps > max_steps:             st.status = "max_steps"; break
        if time.monotonic() > st.deadline:   st.status = "timeout"; break
        if st.tokens > token_budget:         st.status = "budget"; break
        resp = client.chat.completions.create(
            model=MODEL, messages=st.messages, tools=schemas, temperature=0)
        st.tokens += resp.usage.total_tokens
        msg = resp.choices[0].message
        if not msg.tool_calls:                      # 模型主动终止
            st.status = "done"
            return msg.content, st
        st.messages.append({"role": "assistant", "content": msg.content or "",
                            "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            key = tc.function.name + tc.function.arguments
            st.seen[key] = st.seen.get(key, 0) + 1
            if st.seen[key] >= 2:                   # 重复动作检测
                result = "该动作已执行过且无新信息，请换策略或直接作答。"
            elif tc.function.name not in tools:     # 工具白名单
                result = f"未知工具 {tc.function.name}，可用：{list(tools)}"
            else:
                result = call_with_retry(tools[tc.function.name], tc.function.arguments)
            st.messages.append({"role": "tool", "tool_call_id": tc.id,
                                "content": str(result)[:2000]})
    return f"循环终止（{st.status}），未能完成任务", st
```

> `tools` 与 `schemas` 的定义见本章最后一节的自包含精简版。

## 常见架构模式对比

| 模式 | 结构 | 优点 | 缺点 | 代表框架 |
| --- | --- | --- | --- | --- |
| ReAct 单循环 | LLM ↔ 工具，线性循环 | 简单直观、好调试 | 长任务跑偏 | LangChain Agent |
| Plan-and-Execute | Planner → Executor → Replan | 全局观、长任务稳 | 规划开销大、不灵活 | BabyAGI |
| 状态机/图 | 显式节点 + 条件边 | 可控性强、可断点续跑 | 搭建成本高 | LangGraph |
| 多 Agent | 多角色协作 | 分工明确、上下文隔离 | 协调复杂、成本翻倍 | AutoGen、CrewAI |

## 架构选型决策树

```
任务能否一次 LLM 调用（含 RAG）答完？
├─ 能 ─────────────→ 不要做 Agent，直接调用
└─ 不能
   ├─ 步骤固定且 < 5？
   │    └─ 是 ───────→ ReAct 单循环（第 04 章）
   └─ 否
      ├─ 需要人工审批 / 断点恢复 / 并行分支？
      │    └─ 是 ────→ 状态机（第 06 章）
      └─ 否
         ├─ 是否天然分角色、上下文需隔离？
         │    └─ 是 ──→ 多 Agent（第 08 章）
         └─ 否 ──────→ Plan-and-Execute
```

四个问题按顺序问：步数超过 10 且依赖清晰 → Plan-and-Execute；有审批点或需要断点恢复 → 状态机 + checkpoint（第 06 章）；天然分角色 → 多 Agent（第 08 章）。

## 一个最小可运行 Agent（Function Calling 版）

```python
import json, os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
MODEL = "deepseek-chat"

def get_weather(city: str) -> str:
    """查询城市天气。city 为中文城市名。"""
    data = {"北京": (22, "晴"), "上海": (26, "多云")}
    temp, sky = data.get(city, (20, "未知"))
    return json.dumps({"city": city, "temp": temp, "weather": sky}, ensure_ascii=False)

def get_time(city: str = "北京") -> str:
    """查询城市当前时间，返回 HH:MM。"""
    return json.dumps({"city": city, "time": "14:30"}, ensure_ascii=False)

TOOLS = {"get_weather": get_weather, "get_time": get_time}

def schema(name: str, desc: str, props: dict, required: tuple = ()):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props,
                       "required": list(required)}}}

SCHEMAS = [schema("get_weather", "查询城市天气", {"city": {"type": "string"}}, ("city",)),
           schema("get_time", "查询城市当前时间", {"city": {"type": "string"}})]

def run(goal: str, max_steps: int = 5) -> str:
    messages = [{"role": "system", "content": "你是助手，需要时调用工具，不确定就调用。"},
                {"role": "user", "content": goal}]
    seen = {}
    for _ in range(max_steps):
        resp = client.chat.completions.create(
            model=MODEL, messages=messages, tools=SCHEMAS, temperature=0)
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return msg.content or "（模型没有返回内容）"
        messages.append({"role": "assistant", "content": msg.content or "",
                         "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            name = tc.function.name
            seen[name] = seen.get(name, 0) + 1
            try:
                args = json.loads(tc.function.arguments or "{}")
                if name not in TOOLS:
                    result = f"未知工具 {name}，可用：{list(TOOLS)}"
                elif seen[name] >= 2:
                    result = "该工具已调用过，请基于已有结果作答。"
                else:
                    result = TOOLS[name](**args)
            except Exception as e:
                result = f"工具执行失败：{e}"          # 错误回灌，不中断
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": str(result)})
    return "达到最大步数，任务未完成"

if __name__ == "__main__":
    print(run("北京现在几点？天气适合出门吗？"))
```

## 常见架构反模式

| 反模式 | 症状 | 根因 | 改法 |
| --- | --- | --- | --- |
| 过度设计 | 3 步任务上了多 Agent + 消息总线 + 自研调度 | 先选框架，后想任务 | 单循环跑通基线，再按决策树逐级升级 |
| 工具巨无霸 | `do_everything(action, params)` 一把梭 | 图省事、怕模型选错 | 拆成原子工具，用描述和枚举约束选择 |
| 无状态循环 | 每轮重建 `messages`，Observation 丢失 | 把 Agent 当无状态函数 | 显式维护 state，并落盘 trace |
| 全塞 prompt | 三千行系统提示塞满规则和分支 | 不敢写代码，只敢写文字 | 能代码校验的别靠 prompt：白名单、Schema、状态机 |

## 常见问题

**Q：三要素里哪个最容易被忽视？**
A：Memory。很多 Demo 只有 Planning + Tools，跑起来才发现多轮后上下文爆了、或者 Agent「忘了」开头的要求。记忆策略是 Demo 与生产的分水岭，详见第 07 章。

**Q：Plan-and-Execute 一定比 ReAct 好吗？**
A：不一定。P&E 多一次规划调用，对短任务是浪费；且计划错误会传染给所有步骤。经验法则：预期步骤 > 10 或步骤间依赖复杂时用 P&E，否则 ReAct。

**Q：选型时最先问哪个问题？**
A：先问「能不能不做 Agent」。单次调用加 RAG 能解决的，就不要引入循环；每引入一层架构，都要多一份延迟、成本和排障难度。

## 自测

1. 画出感知-决策-行动循环，并标注每个环节对应的代码实体。
2. 用四类记忆分别举例说明它们落在哪个组件、生命周期多长。
3. 控制循环里的七道护栏分别防什么？如果只允许保留三道，你选哪三个？
4. 给定任务「每天 9 点汇总 20 个数据源并生成日报，需人工审核后发送」，按决策树应选哪种架构？

## 参考与官方链接

- [LLM Powered Autonomous Agents（Lilian Weng）](https://lilianweng.github.io/posts/2023-06-23-agent/)
- [Plan-and-Execute（BabyAGI）](https://github.com/yoheinakajima/babyagi)
- [Reflexion 论文](https://arxiv.org/abs/2303.11366)
- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [DeepSeek API 文档](https://api-docs.deepseek.com/)
