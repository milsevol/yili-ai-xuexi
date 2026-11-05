# 04 ReAct推理范式

## 一句话

**ReAct = Reasoning + Acting**，让 LLM 以「Thought（思考）→ Action（行动）→ Observation（观察）」的循环交替推理与调用工具，直到给出最终答案。它把 CoT 的「只想不做」升级成「边想边做」，是 Function Calling 出现之前最经典的 Agent 范式，至今仍是理解 Agent 循环的最佳心智模型。

## 为什么需要 ReAct

纯 CoT（Chain-of-Thought）的问题：模型只在「脑内」推理，无法获取外部信息，遇到知识盲区就开始一本正经地胡说八道。

ReAct 的思路：**把推理轨迹和行动轨迹交织在同一个序列里**——模型先写出思考（我需要查 X），再输出行动（search X），环境返回观察（搜索结果），模型接着思考下一步。

```
CoT:   Thought → Thought → Thought → Answer     （闭门造车）
ReAct: Thought → Action → Observation
              → Thought → Action → Observation
              → Thought → Answer                 （边想边做）
```

## 循环原理详解

每一轮迭代，模型输出的文本被解析成结构化三元组：

| 组件 | 含义 | 谁产生 |
| --- | --- | --- |
| Thought | 当前局势分析 + 下一步打算 | LLM |
| Action | 要调用的工具名 + 参数 | LLM |
| Observation | 工具执行结果 | 环境/工具 |
| （终态）Answer | 最终答案 | LLM |

经典 Prompt 模板（Few-shot 驱动）：

```
你是一个能使用工具的助手。按以下格式回答：

Question: 用户问题
Thought: 你的思考
Action: 工具名
Action Input: 工具参数（JSON）
Observation: 工具返回结果
...（Thought/Action/Observation 可重复多轮）
Thought: 我现在知道答案了
Answer: 最终答案

可用工具：
- search[query]: 网络搜索
- calculator[expr]: 计算表达式

Question: {question}
```

## 完整 Trace 1：多跳事实问答

问题：「苹果公司现任 CEO 出生那年，美国的总统是谁？」

```
Question: 苹果公司现任 CEO 出生那年，美国的总统是谁？

Thought 1: 我需要先知道苹果公司现任 CEO 是谁。
Action 1: search
Action Input 1: {"query": "Apple current CEO"}
Observation 1: 蒂姆·库克（Tim Cook）自 2011 年起担任苹果公司 CEO。

Thought 2: CEO 是 Tim Cook。接下来查他的出生年份。
Action 2: search
Action Input 2: {"query": "Tim Cook date of birth"}
Observation 2: 蒂姆·库克出生于 1960 年 11 月 1 日。

Thought 3: 他出生于 1960 年。现在查 1960 年的美国总统。
Action 3: search
Action Input 3: {"query": "US president in 1960"}
Observation 3: 1960 年美国总统是德怀特·艾森豪威尔（任期 1953-1961）。

Thought 4: 我得到了所有信息：CEO 是 Tim Cook，生于 1960 年，当年总统是艾森豪威尔。
Answer: 艾森豪威尔（Dwight D. Eisenhower）
```

**三个细节**：每步 Thought 都在明确下一步目标；问题被自然分解成 3 个子查询，**分解策略是模型自己想出来的**；最后一步有显式的「我知道答案了」判断，这是循环的终止信号。

## 完整 Trace 2：线上故障定位（贴近业务）

问题：「订单服务 P99 从 200ms 涨到 1.8s，定位最可能的原因并给出下一步验证动作。」

```
Question: 订单服务 P99 从 200ms 涨到 1.8s，帮我定位最可能的原因，并给出下一步验证动作。

Thought 1: 先确认当前时间，才能界定「最近 24h」这个排障窗口。
Action 1: get_time
Action Input 1: {"timezone_name": "Asia/Shanghai"}
Observation 1: 2026-11-05 14:32:10

Thought 2: 时间锚点有了。先查发布记录和告警，故障定位优先看「最近改了什么」。
Action 2: search_mock
Action Input 2: {"query": "订单服务 发布 告警"}
Observation 2: [ops-1] 11-05 09:10 发布 v2.14.0，新增优惠券远程校验；[ops-2] 09:30 起 P99 由 210ms 升至 1.7s。

Thought 3: 发布与劣化时间高度重合，但相关不等于因果。要看依赖调用耗时占比。
Action 3: search_mock
Action Input 3: {"query": "订单服务 依赖 调用 耗时 优惠券"}
Observation 3: [ops-3] 优惠券校验平均 620ms，占订单接口总耗时 41%；超时配置 3s，未触发熔断。

Thought 4: 620ms 对 1.8s 的贡献需要量化，用计算器核对比例。
Action 4: calculator
Action Input 4: {"expr": "620/1800*100"}
Observation 4: 34.44444444444444

Thought 5: 占比约 34%，加上重试放大能解释大部分增量。但必须先排除数据库慢查询这个高频干扰项。
Action 5: search_mock
Action Input 5: {"query": "订单服务 数据库 慢查询 连接池"}
Observation 5: [ops-4] 同期数据库 P99 稳定在 35ms，连接池使用率 42%，无慢查询告警。

Thought 6: 数据库已排除，证据收敛到新增的优惠券远程调用。不再检索，给出结论和验证动作。
Answer: 最可能原因：v2.14.0 新增的优惠券远程校验（平均 620ms，约占总耗时 34%，重试会放大）。
下一步验证：① 灰度关闭该调用或改本地缓存；② 超时从 3s 降到 800ms 并加降级；③ 观察 P99 是否回落。
注意：这是抽样数据上的相关性判断，因果需 A/B 验证。
```

| 轮次 | 决策依据 | 为什么不是别的动作 |
| --- | --- | --- |
| 1 | 排障先定时间窗 | 没有时间锚点，后面「最近变更」无从判断 |
| 2 | 故障优先怀疑最近发布 | 直接看监控曲线只能看到现象，看不到变更 |
| 3 | 从「时间相关」转向「耗时归因」 | 发布相关不代表是发布导致，需要量化证据 |
| 4 | 用工具算占比，而不是心算 | 避免模型算错，且计算过程可审计 |
| 5 | 主动找反证（排除数据库） | 好的 ReAct 会证伪，而不是只找支持自己的证据 |
| 6 | 信息足够即收敛 | 继续搜只会增加噪音与成本 |

业务问题的难点不在工具调用，而在**每一轮「该查什么、够不够、要不要证伪」的判断**。

## 解析与执行代码

```python
import re, json

def parse_react_output(text: str):
    """返回 ('action', name, args) / ('answer', content) / ('parse_error', text)"""
    action_match = re.search(r"Action:\s*(\w+)\s*Action Input:\s*(\{.*?\})", text, re.S)
    if action_match:
        return "action", action_match.group(1), json.loads(action_match.group(2))
    answer_match = re.search(r"Answer:\s*(.*)", text, re.S)
    if answer_match:
        return "answer", answer_match.group(1).strip()
    return "parse_error", text, None
```

两个必须注意的点：设 `stop=["Observation:"]`，让模型生成完 Action 立即停止，防止它**自己编造 Observation**（ReAct 最常见的解析事故）；先判断 Action 再判断 Answer，否则模型在中间轮提前写出的「预期答案」会被误判为终态。

## 接近可运行的 ReAct 实现

在解析器基础上补齐执行侧：三个工具（`search_mock` / `calculator` / `get_time`）+ Prompt 模板 + stop 控制 + 工具白名单 + 错误回灌 + 最大轮数。

```python
import json, os, re
from collections import Counter
from datetime import datetime, timedelta, timezone
from openai import OpenAI

client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
MODEL = "deepseek-chat"

CORPUS = {
    "ceo": "苹果公司现任 CEO 是蒂姆·库克（Tim Cook），2011 年 8 月上任。",
    "birth": "蒂姆·库克出生于 1960 年 11 月 1 日，美国阿拉巴马州。",
    "president 1960": "1960 年美国总统是德怀特·艾森豪威尔（1953-1961 在任）。",
}

def search_mock(query: str) -> str:
    hits = [v for k, v in CORPUS.items() if k in query.lower()]
    return "\n".join(hits[:2]) if hits else "未检索到结果，建议换关键词或说明信息不足。"

def calculator(expr: str) -> str:
    if not set(expr) <= set("0123456789+-*/().% "):
        return "错误：表达式含非法字符，只支持四则运算与括号。"
    try:
        return str(eval(expr, {"__builtins__": {}}, {}))   # 生产环境建议用 AST 白名单求值
    except Exception as e:
        return f"计算失败：{e}"

def get_time(timezone_name: str = "Asia/Shanghai") -> str:
    hours = 8 if timezone_name == "Asia/Shanghai" else 0
    return datetime.now(timezone(timedelta(hours=hours))).strftime("%Y-%m-%d %H:%M:%S")

TOOLS = {"search_mock": search_mock, "calculator": calculator, "get_time": get_time}

SYSTEM_PROMPT = """你是使用工具解决问题的助手，必须严格遵守格式。

可用工具（只能从中选择，禁止编造）：
- search_mock: 检索资料 {"query": "关键词"}
- calculator: 四则运算 {"expr": "1+2*3"}
- get_time: 当前时间 {"timezone_name": "Asia/Shanghai"}

每轮只输出一个动作：
Thought: 现在知道什么、还缺什么、为什么选这个动作
Action: 工具名
Action Input: JSON 参数对象

信息足够时输出：Thought: 我已经可以回答 / Answer: 最终答案
规则：不要自己写 Observation；同一工具同一参数不要重复调用；最多 6 轮。"""

ACTION_RE = re.compile(r"Action:\s*(\w+)\s*Action Input:\s*(\{.*?\})", re.S)
ANSWER_RE = re.compile(r"Answer:\s*(.+)", re.S)

def run_react(question: str, max_iter: int = 6) -> str:
    history = f"Question: {question}\n"
    seen = Counter()
    for i in range(1, max_iter + 1):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": history}],
            temperature=0,
            stop=["Observation:"],              # 防止模型自编 Observation
        )
        out = (resp.choices[0].message.content or "").strip()
        print(f"\n----- 第 {i} 轮 -----\n{out}")

        action, answer = ACTION_RE.search(out), ANSWER_RE.search(out)
        if answer and not action:               # 先看 Action，避免把中间轮误判为终态
            return answer.group(1).strip()
        if not action:
            history += out + "\nObservation: 格式错误，请按 Thought/Action/Action Input 输出。\n"
            continue

        name, raw_args = action.group(1), action.group(2)
        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError as e:
            history += out + f"\nObservation: 参数不是合法 JSON（{e}），请重新输出。\n"
            continue

        if name not in TOOLS:                   # 工具白名单
            obs = f"错误：工具 {name} 不存在。可用：{list(TOOLS)}"
        else:
            fp = f"{name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"
            seen[fp] += 1
            if seen[fp] >= 2:                   # 循环检测：重复 2 次强制收敛
                obs = ("该动作已执行过且结果不会变化。禁止重复调用，"
                       "请立即基于已有 Observation 输出 Answer，或说明信息不足。")
            else:
                try:
                    obs = str(TOOLS[name](**args))
                except Exception as e:          # 错误回灌，不中断循环
                    obs = f"工具执行失败：{e}。请修正参数或换用其他工具。"
        history += out + f"\nObservation: {obs[:1200]}\n"   # 截断，防噪音撑爆上下文

    return f"达到最大轮数 {max_iter} 仍未收敛，请人工介入。"
```

## 循环检测

只靠 `max_iter` 太晚——可能烧掉 6 轮预算才停。更早刹车的办法是给每个动作做指纹：

```python
import json
from collections import Counter

class LoopGuard:
    """把 (tool, args) 归一化成指纹；第 2 次命中即拒绝执行并强制收敛。"""
    def __init__(self, limit: int = 2):
        self.limit = limit
        self.counter = Counter()

    def hit(self, tool: str, args: dict) -> str | None:
        fp = f"{tool}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"
        self.counter[fp] += 1
        if self.counter[fp] < self.limit:
            return None
        return (f"动作 {fp} 已重复 {self.counter[fp]} 次，结果不会变化。"
                "禁止再调用，请基于已有 Observation 直接输出 Answer。")

# 用法：blocked = guard.hit(name, args); if blocked: obs = blocked
```

三个细节：**参数要排序后序列化**，否则 `{"a":1,"b":2}` 和 `{"b":2,"a":1}` 会被当成两个不同动作；**只统计成功执行的动作**，参数写错后的重试不应被误杀；**拒绝时要把原因告诉模型**，只抛一个 `False` 模型会继续换个写法试。

## ReAct vs CoT

| 维度 | CoT | ReAct |
| --- | --- | --- |
| 信息来源 | 只有模型参数内知识 | 模型知识 + 工具实时信息 |
| 幻觉控制 | 差（推理错了无从纠正） | 好（Observation 提供事实锚点） |
| 可解释性 | 有推理链 | 更强：推理 + 行动 + 观察全留痕 |
| 适用任务 | 数学/逻辑等纯推理 | 需要外部信息的多跳问答 |
| 成本 | 一次生成 | 多轮调用，token 高数倍 |

论文结论（HotpotQA/FEVER）：ReAct 显著降低幻觉率，多跳问答准确率超过 CoT；但 CoT 在纯推理题上仍有一席之地。实践中两者常混合：行动间隙用 CoT 深想，需要事实就用工具。

## 失败模式：检测信号与对策

| 失败模式 | 表现 | 检测信号 | 对策 |
| --- | --- | --- | --- |
| 死循环 | 反复调同一工具同一参数 | 相同指纹 ≥ 2、轮数逼近上限 | 指纹计数、Prompt 明示「2 次无新信息就回答」 |
| 幻觉工具 | 调用不存在的工具 | 工具名不在白名单 | 返回错误 + 可用工具列表，让模型自纠 |
| 编造 Observation | 模型自己续写观察结果 | 输出含 Observation 且非工具产生 | `stop=["Observation:"]`，Observation 只由工具填充 |
| 格式崩溃 | 无法解析 Action | 连续 2 次 `parse_error` | 错误提示回灌重试；线上直接换 Function Calling |
| 工具返回噪音 | 长网页/日志塞满上下文 | 单条 Observation 占比过高 | 截断、结构化提取、摘要后再回灌（详见第 07 章） |
| 上下文漂移 | 后几轮逐渐偏离原问题 | Thought 与原始问题关键词重合度下降 | 每轮 Prompt 携带原始 Question，阶段性小结 |
| 过早终止 | 信息不足就给出 Answer | Answer 前无关键实体、无工具验证 | 加验收 checklist，或交付前跑一次 Reflection |
| 并行缺失 | 多个独立查询串行执行 | 轮次数 ≈ 查询数、延迟线性增长 | 函数调用并行，或封装批量查询工具 |

**工具返回噪音**是最隐蔽的一个：模型不是被错误答案骗，而是被大段无关内容带偏。对策是「工具层做结构化」——返回摘要和关键字段，而不是整页 HTML。

**上下文漂移**的信号是第 5 轮之后 Thought 里不再出现原始问题的实体；低于重合度阈值就插一条「你现在要解决的原问题是……」提醒。

## ReAct 什么时候不该用

1. **步骤固定**：ETL、固定报表、固定审核流这类流程，直接用 workflow / 代码编排更便宜、更可测。让模型决定「先查 A 还是先查 B」纯属浪费。
2. **强实时性**：每轮都是一次完整的 LLM 调用，3 轮就多出 3 次网络往返。P99 要求 < 2s 的场景，ReAct 基本出局。
3. **强结构化输出**：下游要严丝合缝的 JSON Schema，文本协议解析太脆，应该用 Function Calling 或受约束解码（详见第 05 章）。

高频重复任务同样不适合——同一流程每天跑一万次，用 10 行代码固化下来比每次让模型重新推理更稳。

## ReAct / Plan-and-Execute / Function Calling 选型

| 维度 | ReAct | Plan-and-Execute | Function Calling |
| --- | --- | --- | --- |
| 决策方式 | 每步由 LLM 现场决定 | 先出全局计划再执行 | 每步由 LLM 输出结构化调用 |
| 输出协议 | 自由文本 + 正则解析 | JSON 计划 | 原生 JSON Schema |
| 可审计性 | 强（Thought 全留痕） | 强（计划可先审） | 中（推理过程常隐式） |
| 延迟 | 多轮串行 | 多一轮规划，但可并行 | 多轮串行，可并行工具 |
| 适合 | 探索型、步骤 < 10 | 长任务、依赖清晰 | 生产环境、工具多 |
| 主要风险 | 跑偏、死循环、解析崩 | 计划错误传染 | 模型不支持/参数幻觉 |

### ReAct vs Function Calling

| 维度 | ReAct（文本协议） | Function Calling（结构化协议） |
| --- | --- | --- |
| 输出格式 | 自由文本，需正则解析 | 严格 JSON，模型原生支持 |
| 解析可靠性 | 脆（格式漂移常见） | 高（API 层保证） |
| 思考过程 | 显式 Thought，可审计 | 隐式（部分模型有 reasoning 字段） |
| 通用性 | 任何 LLM 都能用 | 依赖模型厂商支持 |

工程共识：**线上用 Function Calling，设计和排障时用 ReAct 心智模型**。很多框架已把两者融合——底层走结构化调用，日志层仍呈现 Thought/Action/Observation（协议细节见第 05 章）。

## 让 ReAct 更稳的 8 条工程清单

1. **stop 序列**：必须在 `Observation:` 处截断，否则模型会自编观察。
2. **工具白名单**：执行前校验工具名，未知工具返回可用列表。
3. **每轮复述原始问题**：history 始终以 `Question:` 开头，防止上下文漂移。
4. **Observation 截断/摘要**：单条回灌限长，长文本先抽取关键字段。
5. **动作指纹循环检测**：相同 `(tool, args)` 第 2 次直接拒绝并提示收敛。
6. **三道预算**：`max_iter`、整体超时、累计 token 上限，缺一不可。
7. **结构化错误回灌**：错误是 Observation，不是异常；同时保留重试计数。
8. **全量 trace 落盘**：每轮记录 prompt、输出、工具名、参数、耗时、token，用于离线复盘与回归。

## 常见问题

**Q：Thought 字段真的有用吗，还是浪费 token？**
A：有用。显式 Thought 迫使模型在行动前明确目标，多跳任务准确率提升明显；代价是每轮多几十个 token。若成本敏感，可只要求「一句话 Thought」。

**Q：ReAct 一般几轮收敛？**
A：简单查询 2~3 轮，多跳问答 3~5 轮，超过 8 轮基本可判定失败。`max_iter=8~10` 是经验值，业务排障类任务可放宽到 10。

**Q：能让 ReAct 并行调多个工具吗？**
A：经典 ReAct 是串行的。并行需要模型一次输出多个 Action（Function Calling 的 `parallel_tool_calls`），执行后把多个 Observation 一起回灌。

## 自测

1. 写出 ReAct 一轮迭代的三元组，并说明 Observation 由谁产生。
2. 为什么解析时要设 `stop=["Observation:"]`？不设会发生什么？
3. 循环检测为什么要求「参数排序后再做指纹」？只统计成功动作的原因是什么？
4. 列举三个不适合用 ReAct 的场景，并说明替代方案。

## 参考与官方链接

- [ReAct 论文（Yao et al., 2022）](https://arxiv.org/abs/2210.03629)
- [ReAct 官方示例仓库](https://github.com/ysymyth/ReAct)
- [LangChain ReAct Agent](https://python.langchain.com/docs/how_to/migrate_agent/)
- [Reflexion：ReAct + 自我反思](https://arxiv.org/abs/2303.11366)
- [DeepSeek API 文档](https://api-docs.deepseek.com/)
