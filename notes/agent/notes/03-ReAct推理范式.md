# 03 ReAct推理范式

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

## 完整 Trace 示例

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

**注意这个 trace 的三个细节**：
1. 每一步的 Thought 都在**明确下一步目标**——好的 ReAct 轨迹里 Thought 不是废话，是决策依据
2. 问题被自然分解成 3 个子查询，**分解策略是模型自己想出来的**，不在代码里写死
3. 最后一步有显式的「我知道答案了」判断——这是循环的终止信号

## 解析与执行代码

```python
import re, json

def parse_react_output(text: str):
    """解析模型输出：返回 ('action', name, args) 或 ('answer', content)"""
    action_match = re.search(r"Action:\s*(\w+)\s*Action Input:\s*(\{.*?\})", text, re.S)
    if action_match:
        return "action", action_match.group(1), json.loads(action_match.group(2))
    answer_match = re.search(r"Answer:\s*(.*)", text, re.S)
    if answer_match:
        return "answer", answer_match.group(1).strip()
    return "parse_error", text, None

def react_loop(question: str, tools: dict, max_iter: int = 8):
    history = f"Question: {question}\n"
    for i in range(max_iter):
        output = llm.chat(SYSTEM_PROMPT + history, stop=["Observation:"])
        history += output + "\n"
        kind, *payload = parse_react_output(output)
        if kind == "answer":
            return payload[0]
        if kind == "parse_error":
            history += "Observation: 输出格式错误，请严格按格式输出。\n"
            continue
        name, args = payload
        if name not in tools:
            obs = f"错误：工具 {name} 不存在。可用工具：{list(tools)}"
        else:
            try:
                obs = tools[name](**args)
            except Exception as e:
                obs = f"工具执行失败：{e}"
        history += f"Observation: {obs}\n"
    return "达到最大迭代次数"
```

关键技巧：`stop=["Observation:"]` 让模型在生成完 Action 后立即停止，防止它**自己编造 Observation**（这是 ReAct 最常见的解析事故）。

## ReAct vs CoT

| 维度 | CoT | ReAct |
| --- | --- | --- |
| 信息来源 | 只有模型参数内知识 | 模型知识 + 工具实时信息 |
| 幻觉控制 | 差（推理错了无从纠正） | 好（Observation 提供事实锚点） |
| 可解释性 | 有推理链 | 更强：推理 + 行动 + 观察全留痕 |
| 适用任务 | 数学/逻辑等纯推理 | 需要外部信息的多跳问答 |
| 成本 | 一次生成 | 多轮调用，token 高数倍 |

论文结论（HotpotQA/FEVER 数据集）：ReAct 显著降低幻觉率，多跳问答准确率超过 CoT；但 CoT 在纯推理题上仍有一席之地。实践中两者常混合：行动间隙用 CoT 深想，需要事实就用工具。

## 失败模式分析

### 1. 死循环

```
Thought 5: 我还是不确定，再搜一次。
Action 5: search["Tim Cook birth"]
Observation 5: ...1960 年...
Thought 6: 我再确认一下。
Action 6: search["Tim Cook birth"]    ← 同样的搜索又来一遍
```

**对策**：
- 硬上限：max_iterations
- 循环检测：相同 (tool, args) 出现 2 次以上 → 强制要求输出 Answer 或换策略
- 在 Prompt 里明示「搜索 2 次无新信息就直接回答」

### 2. 幻觉工具

```
Action 4: get_company_revenue["Apple"]   ← 这个工具根本不存在
```

**对策**：工具白名单校验，不存在的工具返回明确错误 + 可用工具列表，让模型自我纠正。

### 3. 编造 Observation

模型一次性把 Thought/Action/Observation 全生成完，观察内容是自己编的。**对策**：生成时设 `stop=["Observation:"]`，Observation 只能由真实工具填充。

### 4. 推理漂移

步骤多了以后，Thought 逐渐偏离原始问题。**对策**：每轮 Prompt 都携带原始 Question；长任务用 Plan-and-Execute 替代。

### 5. 格式崩溃

模型输出不符合 Action/Action Input 格式，解析失败。**对策**：解析失败时把错误提示喂回模型重试；生产环境直接用 Function Calling（结构化输出，无解析问题）。

## ReAct vs Function Calling

| 维度 | ReAct（文本协议） | Function Calling（结构化协议） |
| --- | --- | --- |
| 输出格式 | 自由文本，需正则解析 | 严格 JSON，模型原生支持 |
| 解析可靠性 | 脆（格式漂移常见） | 高（API 层保证） |
| 思考过程 | 显式 Thought，可审计 | 隐式（部分模型支持 reasoning 字段） |
| 通用性 | 任何 LLM 都能用 | 依赖模型厂商支持 |

工程共识：**线上用 Function Calling，学习和调试时用 ReAct 心智模型**。很多框架（LangChain 的 ReAct Agent）已把两者融合——底层走 Function Calling，日志里仍呈现 Thought/Action/Observation。

## 常见问题

**Q：Thought 字段真的有用吗，还是浪费 token？**
A：有用。实验表明显式 Thought 能让多跳任务准确率提升 10%+——它迫使模型在行动前明确目标，减少盲目调用。代价是每轮多几十个 token，值得。

**Q：ReAct 一般几轮收敛？**
A：简单查询 2-3 轮，多跳问答 3-5 轮，超过 8 轮还没收敛基本可以判定失败。设置 max_iter=8~10 是经验值。

**Q：能让 ReAct 并行调多个工具吗？**
A：经典 ReAct 是串行的。并行需要模型一次输出多个 Action（Function Calling 的 parallel_tool_calls 支持），执行后把多个 Observation 一起回灌。

## 自测

1. 写出 ReAct 一轮迭代的三元组，并说明 Observation 由谁产生。
2. 为什么解析 ReAct 输出时要设 `stop=["Observation:"]`？
3. ReAct 相比 CoT 解决了什么问题？又引入了什么成本？
4. 列举 ReAct 的三种失败模式及对策。

## 参考与官方链接

- [ReAct 论文（Yao et al., 2022）](https://arxiv.org/abs/2210.03629)
- [ReAct 官方示例仓库](https://github.com/ysymyth/ReAct)
- [LangChain ReAct Agent](https://python.langchain.com/docs/how_to/migrate_agent/)
- [Reflexion：ReAct + 自我反思](https://arxiv.org/abs/2303.11366)
