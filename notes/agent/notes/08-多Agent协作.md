# 08 多 Agent 协作

## 一句话

**多 Agent = 多个有角色分工的 Agent 通过消息或共享状态协作完成任务**，核心价值是分工带来的上下文隔离、专业化与并行，代价是协调复杂度与成本成倍上升。经验法则：**单 Agent 能做好的绝不上多 Agent**；只有任务天然分角色、上下文互相污染、或子任务可并行时才值得拆。

## 何时需要多 Agent

| 该拆的信号 | 说明 | 例子 |
| --- | --- | --- |
| 角色天然分离 | 任务本身是流水线分工 | 研究员搜集 → 分析师建模 → 写手成稿 → 审稿人把关 |
| 上下文污染 | 单 Agent 上下文被无关信息撑爆 | 搜索 Agent 看了 50 个网页，但写报告只需结论 |
| 并行加速 | 子任务互相独立 | 同时查 5 家竞对的财报 |
| 能力异构 | 不同子任务适合不同模型/工具 | 检索用小模型省钱，综合用旗舰模型 |

不该拆：任务线性且短（< 5 步）、步骤间强依赖需全程共享上下文、预算紧张（多 Agent 通常是单 Agent 的 3-10 倍 token）。

**反模式警告**：把「一个 prompt 写得不好的单 Agent」拆成多 Agent，只是把问题扩散。先优化单 Agent，再考虑拆分。

## 先算一笔账：单 Agent vs 多 Agent

任务：调研 5 家锂电公司并输出对比研报。

```text
单 Agent：12 轮 × 平均上下文 30K = 360K prompt + 8K output
Supervisor + 3 Worker：
  supervisor 10 轮 × 40K          = 400K
  5 个子任务 × 6 轮 × 12K         = 360K
  交接卡 / 摘要 / 汇总 5 次 × 15K  = 75K
  合计                            ≈ 835K（2.3 倍）
辩论模式：2 个辩手 × 3 轮 + 裁判   ≈ 再加 2 倍 → 4-5 倍
```

| 成本放大来源 | 机制 | 量级 |
| --- | --- | --- |
| 上下文重复计费 | 每个 Agent 每轮都重发自己的 system + 历史 | 基础成本 |
| 交接全量复制 | handoff 把会话整段转交，新 Agent 再读一遍 | +30-100% |
| 额外路由与摘要 | supervisor 决策、交接摘要、结果汇总各是一次 LLM 调用 | +20-50% |
| 重试与返工 | 子任务失败重跑、辩论多轮反驳 | ×2-3 |
| 并行不省钱 | 并行只压缩墙钟时间，token 总量不变甚至更高 | 成本不变 |

**结论**：多 Agent 买的是「上下文隔离 + 并行 + 专业化」，不是省钱。延迟上单 Agent 12 轮 × 2s ≈ 24s；Supervisor 串行可能到 40s，并行 worker 可压到 30s 左右——**面向用户的总延迟预算建议 < 30s**，超出就砍协作轮次或改异步。

## 四种协作模式

### 1. 主管-工人（Supervisor）

```text
        ┌────────────┐
        │ Supervisor │ → 分派 + 汇总
        └─────┬──────┘
   ┌──────────┼──────────┐
Worker1     Worker2     Worker3
(搜索)      (计算)      (写作)
```

### 2. 流水线（Pipeline）

```text
Researcher → Analyst → Writer → Reviewer → END
```

流程固定，每个 Agent 只跟上下游交接；本质是「每个环节用 LLM 的 Workflow」，可控性最强。

### 3. 辩论（Debate）

```text
     ┌─ Agent A（正方）─┐
问 ──┤                 ├──→ Judge（裁判）→ 结论
     └─ Agent B（反方）─┘
        ↑ 多轮互相反驳 ↑
```

### 4. 群体自主（Swarm / Network）

无中心，Agent 间自由 handoff；最灵活也最不可控，适合探索性任务，不适合强 SLA 场景。

| 模式 | 可控性 | 成本 | 适用 |
| --- | --- | --- | --- |
| 流水线 | ★★★ | ★ | 步骤固定的生产任务 |
| 主管-工人 | ★★ | ★★ | 通用复杂任务 |
| 辩论 | ★★ | ★★★ | 质量优先的评审任务 |
| 群体自主 | ★ | ★★★ | 探索性任务 |

## 框架对比：AutoGen vs CrewAI vs LangGraph

| 维度 | AutoGen（微软） | CrewAI | LangGraph |
| --- | --- | --- | --- |
| 抽象 | 会话式 Agent（对话驱动） | 角色 + 任务 + 流程 | 状态图（最底层） |
| 上手难度 | 中 | **低（最像业务语言）** | 中高 |
| 可控性 | 中 | 中 | **高** |
| 人工审批 | 支持 | 支持 | 原生 interrupt |
| 适用 | 研究、对话式协作 | 业务流水线快速搭建 | 生产级定制编排 |
| 心智模型 | 「几个 Agent 在群里聊天」 | 「一个团队接项目」 | 「一台状态机」 |

选型：快速验证角色分工 → CrewAI；生产环境要审批/恢复/观测 → LangGraph；学术实验、多 Agent 对话研究 → AutoGen。LangGraph 的 State/Reducer/checkpoint 细节详见第 06 章。

## Supervisor 的 LangGraph 实现

核心设计：**主管只看到「目标 + 结论列表」，工人只收到「任务卡」，谁都不携带别人的完整历史**。

```python
import os, json
from typing import TypedDict
from openai import OpenAI
from langgraph.graph import StateGraph, START, END
client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
MODEL = "deepseek-chat"
WORKERS = ("search", "calc", "write")
HINTS = {"search": "补齐缺失的关键事实", "calc": "计算并校验关键指标",
         "write": "把结论组织成段落"}
class TeamState(TypedDict):
    goal: str
    findings: list[str]       # 只存结论摘要，不存 worker 的中间过程
    next: str
    steps: int
    final: str
def call_llm(system: str, user: str) -> str:
    resp = client.chat.completions.create(
        model=MODEL, temperature=0.2,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}])
    return resp.choices[0].message.content or ""
SUPERVISOR_PROMPT = """你是团队主管。根据目标与已有结论决定下一步交给谁。
可选：search / calc / write / summarize。
规则：①同一工人连续调用不超过 2 次；②结论足够支撑目标就 summarize；
③只输出 JSON：{"next": "...", "reason": "..."}"""

def supervisor_node(state: TeamState) -> dict:
    if state["steps"] >= 8:                       # 全局步数刹车，终止条件之一
        return {"next": "summarize"}
    known = "\n".join(f"- {f}" for f in state["findings"])
    raw = call_llm(SUPERVISOR_PROMPT, f"目标：{state['goal']}\n已有结论：\n{known}")
    try:
        decision = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
        nxt = decision["next"]
    except (ValueError, KeyError):
        nxt = "summarize"
    if nxt not in (*WORKERS, "summarize"):
        nxt = "summarize"
    return {"next": nxt, "steps": state["steps"] + 1}
WORKER_PROMPTS = {
    "search": "你是检索员。只回答任务所需事实，标明来源，200 字内。",
    "calc": "你是数据分析师。给出计算过程与结果，保留单位和口径。",
    "write": "你是撰稿人。基于给定结论写作，不得编造新事实。",
}
def make_worker(name: str):
    def worker(state: TeamState) -> dict:
        task = {"instruction": HINTS[name], "goal": state["goal"], "known": state["findings"]}
        answer = call_llm(WORKER_PROMPTS[name], json.dumps(task, ensure_ascii=False))
        return {"findings": state["findings"] + [f"[{name}] {answer[:600]}"]}
    return worker
def summarize_node(state: TeamState) -> dict:
    final = call_llm("你是主笔。整合结论，标注不确定性，不要新增事实。",
                     f"目标：{state['goal']}\n结论：\n" + "\n".join(state["findings"]))
    return {"final": final, "next": "end"}
graph = StateGraph(TeamState)
graph.add_node("supervisor", supervisor_node)
for w in WORKERS:
    graph.add_node(w, make_worker(w))
graph.add_node("summarize", summarize_node)
graph.add_edge(START, "supervisor")
graph.add_conditional_edges(
    "supervisor", lambda s: s["next"],
    {**{w: w for w in WORKERS}, "summarize": "summarize"})
for w in WORKERS:
    graph.add_edge(w, "supervisor")                # 工人干完必须回主管
graph.add_edge("summarize", END)
team = graph.compile()
result = team.invoke({"goal": "对比宁德时代与比亚迪 2025 前三季度毛利率",
                      "findings": [], "next": "", "steps": 0, "final": ""})
print(result["final"])
```

两个终止条件必须同时有：**主管主动选择 summarize**（语义完成）与 **`steps >= 8`**（预算兜底）。只靠前者，模型抽风时会无限循环。

## Handoff：把任务转交给下一个 Agent

handoff 的关键不是「转移控制权」，而是**转移时裁剪上下文**。整段会话直接转交，等于把上下文污染也一起转交。

```python
import json
from dataclasses import dataclass, asdict
@dataclass
class HandoffCard:
    to: str
    reason: str
    goal: str
    constraints: list[str]
    facts: list[str]          # 每条都带来源，不含推测
    open_questions: list[str]
    artifacts: list[str]      # 文件 / URL 引用，不搬正文
def build_handoff(to: str, reason: str, goal: str, constraints: list[str],
                  facts: list[str], artifacts: list[str],
                  recent: list[dict]) -> list[dict]:
    card = HandoffCard(to=to, reason=reason, goal=goal, constraints=constraints,
                       facts=facts, open_questions=[], artifacts=artifacts)
    return [{"role": "system",
             "content": "你接手了另一个 Agent 的任务：\n"
                        + json.dumps(asdict(card), ensure_ascii=False)},
            *recent[-2:]]        # 只带最近 2 条对话，工具原文全部丢弃

messages = build_handoff(
    to="writer", reason="检索与计算完成，进入写作", goal="输出 800 字研报",
    constraints=["不引用 2026 年后的数据"],
    facts=["[search] 宁德时代 2025 前三季度毛利率 25.1%（来源：财报）"],
    artifacts=["/tmp/agent_artifacts/annual_report.txt"],
    recent=[{"role": "user", "content": "对比两家公司毛利率"}])
```

| 内容 | 处理 |
| --- | --- |
| 目标、硬约束、已确认事实 | 写进卡片，逐条带来源 |
| 最近 1-2 轮对话 | 原文保留，维持语气与即时意图 |
| 工具原始返回、中间推理与失败重试 | 丢弃，只留 artifact 路径或压成一行 |
| 整段历史 | 不进 handoff；28K 会话可裁到 2K 以内 |

## Agent 间通信协议

自然语言交接的问题是不可校验：少字段、超时、状态含糊都会在链路里放大。用 Schema 把契约固定下来：

```python
import asyncio, time
from enum import Enum
from pydantic import BaseModel, Field
class Status(str, Enum):
    OK = "ok"            # 成功，结果可直接进入下游
    RETRY = "retry"      # 可重试的临时失败（限流、超时）
    FAILED = "failed"    # 确定性失败，不要重试
    TIMEOUT = "timeout"  # 超过 deadline
class TaskSpec(BaseModel):
    task_id: str = Field(..., description="全局唯一，用于幂等与追踪")
    goal: str = Field(..., min_length=5, description="一句话可验收的目标")
    inputs: dict = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)
    deadline_s: int = Field(60, ge=5, le=600)
    max_steps: int = Field(6, ge=1, le=20)
    tenant: str
class TaskResult(BaseModel):
    task_id: str
    status: Status
    summary: str = Field(..., max_length=2000)
    facts: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    error: str | None = None
    tokens_used: int = 0
    elapsed_s: float = 0.0
async def dispatch(spec: TaskSpec, worker) -> TaskResult:
    started = time.time()
    try:
        return await asyncio.wait_for(worker(spec), timeout=spec.deadline_s)
    except asyncio.TimeoutError:
        return TaskResult(task_id=spec.task_id, status=Status.TIMEOUT,
                          summary="超时未完成", error=f">{spec.deadline_s}s",
                          elapsed_s=time.time() - started)
```

| 状态 | 语义 | 主管动作 |
| --- | --- | --- |
| `ok` | 结果完整、可被下游消费 | 进入下一步或汇总 |
| `retry` | 临时故障，重试可能成功 | 最多重试 2 次，指数退避 |
| `failed` | 确定性失败（参数错、无权限） | 不重试，改派或上报 |
| `timeout` | 超过 `deadline_s` | 杀任务，降级或并行补位 |

## 并行 worker 与 fan-out / fan-in

```text
              ┌→ Worker A ─┐
Task split ───┼→ Worker B ─┼→ 聚合器 → 去重/冲突检测 → 最终结论
              └→ Worker C ─┘
```

```python
async def run_one(spec: TaskSpec) -> TaskResult:
    started = time.time()
    answer = await asyncio.to_thread(
        call_llm, "你是执行子任务的工人，只回结论。",
        f"目标：{spec.goal}\n约束：{spec.constraints}\n输入：{spec.inputs}")
    return TaskResult(task_id=spec.task_id, status=Status.OK,
                      summary=answer[:1000], elapsed_s=time.time() - started)
async def fan_out(specs: list[TaskSpec]) -> list[TaskResult]:
    results = await asyncio.gather(*(dispatch(s, run_one) for s in specs),
                                   return_exceptions=True)
    return [r if isinstance(r, TaskResult) else
            TaskResult(task_id=s.task_id, status=Status.FAILED, summary="worker 异常")
            for s, r in zip(specs, results)]
def fan_in(results: list[TaskResult], goal: str) -> str:
    ok = [r for r in results if r.status == Status.OK]
    failed = [r.task_id for r in results if r.status != Status.OK]
    body = "\n".join(f"- {r.summary}" for r in ok)
    return call_llm("你是汇总员。合并结论，指出冲突与缺口，不要编造。",
                    f"目标：{goal}\n结论：\n{body}\n失败任务：{failed}")
```

`asyncio.gather` 默认会把第一个异常抛给调用方；生产应加 `return_exceptions=True`，并在聚合时显式处理失败任务：**缺数据的结论比没有结论更危险**。

## 通信与共享状态

| 方式 | 实现 | 优点 | 缺点 |
| --- | --- | --- | --- |
| 消息传递 | Agent 间互发消息 | 直观、可审计 | 消息膨胀、噪音多 |
| 共享状态 | 公共黑板 / State 读写 | 结构化、可控 | 需设计 Schema |
| 工具移交 | handoff 把会话转给下一个 Agent | 简单 | 上下文全量转移，无隔离 |

两条铁律：**下发要窄**（只给工人它需要的信息）、**回收要薄**（只交结论，中间过程归档或丢弃）。工人之间不要网状直连，生产系统保持星型——一切经过主管，否则出错时说不清谁污染了谁。

## 成本与延迟控制

| 手段 | 效果 |
| --- | --- |
| 分层用模型 | 主管/综合用旗舰模型，工人用 mini 级小模型，省 50-80% |
| 并行执行 | 独立工人并行跑，墙钟时间 ≈ 最慢的一个 |
| 轮数预算 | 每个 Agent 独立 `max_steps`，全局总步数也设上限 |
| 上下文裁剪 | 交接时摘要压缩，只传卡片（见第 07 章） |
| 缓存 | 相同子任务（同一股票查询）结果复用 |

## 失败模式与对策

| 失败模式 | 典型表现 | 检测信号 | 对策 |
| --- | --- | --- | --- |
| 上下文丢失 | 工人重复问已确认的事、结论互相矛盾 | 交接后重复工具调用率上升 | 交接卡 + facts 列表；关键约束写进每个 worker 的 system |
| 错误传播 | 一个 worker 的幻觉被下游当事实 | 下游引用无来源断言 | 事实必须带 source；汇总节点做冲突检测；失败结果不进入下游 |
| 死锁 / 乒乓 | 两个 Agent 互相转交，步数耗尽 | `steps` 单调升、`next` 在两值间震荡 | 全局 `max_steps`；同一 handoff 边禁止连续 2 次；访问计数 |
| 成本爆炸 | 账单或延迟突然翻倍 | tokens/task、supervisor 轮数异常 | 每任务 token 预算、分层模型、结果缓存 |
| 责任不清 | 出错后无法定位是谁的锅 | trace 缺 agent/task 维度 | 每步记录 agent、task_id、tokens、状态；单 Agent 单测 |

## 多 Agent 的评估方法

| 层级 | 指标 | 方法 |
| --- | --- | --- |
| 端到端 | 任务成功率、平均成本、P95 延迟 | 固定评测集（≥ 50 条），统计 pass@1 与「每次成功成本」 |
| 单 Agent | 输出是否符合 Schema、事实是否可溯源 | 固定输入跑单测；mock 掉上下游，单独测 worker |
| 轨迹 | 步数、重复调用率、交接次数、失败重试率 | trace 审计：按 task_id 串起完整调用链，逐跳核对 |

缺了「单 Agent 单测」，端到端失败时你只能看到最终错误，定位不到是路由错、工人错还是交接丢信息。

## 多 Agent 反模式

- **为拆而拆**：单 Agent 加两个工具就能解决，硬上 Supervisor。
- **全员群聊**：Agent 自由 mesh 互发消息，调试时无法复现。
- **自然语言交接**：不带 Schema、不带事实来源，下游只能猜。
- **主管扛全部历史**：supervisor 成了最大上下文受害者，路由质量随轮次下降。
- **用多 Agent 掩盖 prompt 问题 / 无终止条件地辩论**：前者只是扩散问题，后者成本翻倍且不收敛。

## 渐进式演进路线

```text
① 单 Agent（while 循环 + 工具）
② 单 Agent + 上下文压缩与预算控制
③ Supervisor（1 主管 + 2-3 工人，星型）
④ 并行 fan-out 或辩论（用评估数据决定去留）
```

每一步都必须用评估数据回答同一个问题：**加这一层，端到端成功率和每次成功成本是否真的变好？** 答不上来就退回上一层。

## 常见问题

**Q：多 Agent 真的比单 Agent 效果好？**
A：分场景。需要强一致上下文的任务上多 Agent 反而更差，因为信息在交接中丢失；收益明确的是并行探索（广度搜索）和上下文隔离（脏活外包）。先问「拆了之后每个 Agent 的上下文是不是更干净了」，是才拆。

**Q：主管-工人里工人之间能直接通信吗？**
A：可以但不推荐。网状通信会让调试地狱化——说不清某个错误结论是谁污染了谁。生产系统保持星型：一切经过主管。

**Q：handoff 和 Supervisor 怎么选？**
A：Supervisor 适合「主管需要持续决策、多轮分派」；handoff 适合「一次交接后由下游独立完成」，实现更轻，但要求交接卡足够完整。两者可以组合：主管决定路由，具体转交用 handoff 卡。

## 自测

1. 列举四个「该拆成多 Agent」的信号，以及为什么单 Agent 做不好。
2. 单 Agent 到多 Agent 的成本为什么可能放大 3-10 倍？至少说出三个来源。
3. 「下发要窄、回收要薄」具体指什么？违反会导致哪类失败？
4. Supervisor 系统里，除了主管主动结束，为什么还必须设置全局步数上限？

## 参考与官方链接

- [AutoGen（微软）](https://github.com/microsoft/autogen)
- [CrewAI](https://github.com/crewAIInc/crewAI)
- [LangGraph Multi-Agent 模式](https://langchain-ai.github.io/langgraph/concepts/multi_agent/)
- [Cognition: Don't Build Multi-Agents](https://cognition.ai/blog/dont-build-multi-agents)
- [OpenAI Swarm](https://github.com/openai/swarm)
