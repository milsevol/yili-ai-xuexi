# 02 从零跑通第一个 Agent

## 一句话

**Agent 的最小内核就是一个 while 循环**：把问题发给模型 → 模型返回 `tool_calls` → 本地执行工具 → 把结果以 `role="tool"` 回灌 → 模型继续决策，直到它不再调工具。本章不依赖 LangChain，用约 100 行 Python 从一次普通 chat 调用写到带迭代上限、异常回灌和 trace 落盘的多工具 Agent。

## 本章目标：三个版本，一条主线

| 版本 | 能力 | 新增的关键机制 | 代码量 |
| --- | --- | --- | --- |
| v0 | 单次 LLM 调用 | `messages` 结构、无状态 | ~15 行 |
| v1 | 单工具调用 | `tools` Schema、`tool_calls`、`tool_call_id` 回灌 | ~60 行 |
| v2 | 多工具循环 Agent | 多轮循环、迭代上限、重复调用检测、异常回灌、trace | ~100 行 |

三个版本共用同一套消息格式，差别只在「循环」和「护栏」。不要小看 v0：生产里大量 Agent 故障，追到最后都是 `messages` 拼错了——少了一条 assistant 消息、`tool_call_id` 对不上、内容被 `None` 覆盖。

**为什么不用 LangChain？** 因为框架会把最关键的那个循环藏起来。先亲手写一遍，你才知道第 06 章的 LangGraph 到底替你封装了什么、代价是什么。本章只需要 `openai` 一个依赖。

## 环境准备

要求 Python 3.10+（新版 `openai` SDK 推荐环境）：

```bash
python3 --version              # 确认 >= 3.10
mkdir agent-demo && cd agent-demo
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install openai
```

配置 API Key。DeepSeek 使用 OpenAI 兼容协议，只需换 `base_url` 和模型名：

```bash
# macOS / Linux；Windows PowerShell 用 $env:NAME="..."
export DEEPSEEK_API_KEY="sk-你的key"
export USE_FAKE_LLM=0          # 有 Key 时关闭离线模式；不设置则默认 1
```

### 一个文件搞定客户端：`llm_client.py`

为了让「有 Key」和「没 Key」的读者跑同一份代码，这里做一层薄封装：真实模式走 OpenAI SDK，离线模式走规则版 `FakeLLM`。**它只模拟消息流，不模拟真实语义**，用来验证你的循环、回灌和护栏是否正确。

```python
# llm_client.py
import json
import os
from types import SimpleNamespace

from openai import OpenAI

MODEL = os.getenv("MODEL_NAME", "deepseek-chat")
USE_FAKE = os.getenv("USE_FAKE_LLM", "1") == "1"

# DeepSeek 走 OpenAI 兼容协议；换官方只改 base_url / MODEL
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY", "sk-offline-placeholder"),
    base_url="https://api.deepseek.com",
)

def _tc(call_id: str, name: str, args: dict):
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=json.dumps(args, ensure_ascii=False)),
    )


class FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.role, self.content, self.tool_calls = "assistant", content, tool_calls

    def model_dump(self, exclude_none=False):
        data = {
            "role": self.role,
            "content": self.content,
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in self.tool_calls
            ] if self.tool_calls else None,
        }
        return {k: v for k, v in data.items() if v is not None} if exclude_none else data


class FakeLLM:
    @staticmethod
    def chat(messages):
        user = next((m["content"] for m in messages if m["role"] == "user"), "")
        results = [m for m in messages if m["role"] == "tool"]
        if results:                                   # 已有工具结果 → 生成终态
            data = json.loads(results[-1]["content"])
            if "error" in data:
                return FakeMessage(content=f"工具调用失败：{data['error']}")
            if "condition" in data:
                return FakeMessage(content=f"{data['city']}今天{data['condition']}，{data['temp_c']}℃，AQI {data['aqi']}，适合跑步。")
            return FakeMessage(content=f"计算结果是 {data['value']}。")

        if "天气" in user:                             # 第一轮：决定调用工具
            city = next((c for c in ["北京", "上海", "深圳", "杭州"] if c in user), "北京")
            return FakeMessage(tool_calls=[_tc("call_weather_1", "get_weather", {"city": city})])
        if any(k in user for k in ["算", "计算", "等于"]):
            return FakeMessage(tool_calls=[_tc("call_calc_1", "calculator",
                                               {"expression": "23.5 * 1.08"})])
        return FakeMessage(content="Agent 是能调用工具、根据反馈多步执行任务以达成目标的 AI 系统。")

def create(messages, tools=None, temperature=0):
    if USE_FAKE:
        return SimpleNamespace(choices=[SimpleNamespace(message=FakeLLM.chat(messages))])
    kwargs = {"model": MODEL, "messages": messages, "temperature": temperature}
    if tools:
        kwargs["tools"] = tools
    return client.chat.completions.create(**kwargs)
```

## v0：先看清一次普通调用

```python
# v0.py
from llm_client import create

messages = [
    {"role": "system", "content": "你是一个简洁的助手。"},
    {"role": "user", "content": "用一句话解释什么是 Agent。"},
]

resp = create(messages=messages)
print("输入:", messages, "\n输出:", resp.choices[0].message.content)
```

这一版必须理解三件事：

1. **`messages` 是唯一的状态**。模型本身不记得上一次请求，所谓「多轮对话」是每次把全部历史重新发过去。
2. **`role` 只有四种**：`system`（行为约束）、`user`（用户输入）、`assistant`（模型输出，含工具调用意图）、`tool`（工具执行结果）。
3. **模型没有手**。它只能生成文字；要查天气，必须由你的代码去执行——这正是下一版要加的东西。

## v1：让模型调用一个工具

### 1. 声明工具（JSON Schema）

模型靠 `description` 判断「什么时候用」，靠 `parameters` 判断「参数怎么填」。这两处写得含糊，工具就永远不会被调用，或者参数永远错。

```python
import json

TOOLS = [{"type": "function", "function": {
    "name": "get_weather",
    "description": "查询指定城市当天的实时天气，返回天气状况、气温和空气质量指数。",
    "parameters": {"type": "object",
                   "properties": {"city": {"type": "string", "description": "中文城市名"}},
                   "required": ["city"], "additionalProperties": False},
}}]

FAKE_WEATHER = {
    "北京": {"condition": "晴", "temp_c": 24, "aqi": 62},
    "上海": {"condition": "多云", "temp_c": 27, "aqi": 48},
}

def get_weather(city: str) -> str:
    """真实项目替换成天气 API；这里用固定数据保证可复现。"""
    data = FAKE_WEATHER.get(city)
    if data is None:
        return json.dumps({"error": f"暂不支持城市 {city}"}, ensure_ascii=False)
    return json.dumps({"city": city, **data}, ensure_ascii=False)
```

### 2. 手写 Function Calling 循环（与上面拼成同一个文件）

```python
# v1_weather.py
import json

from llm_client import create

SYSTEM = "你是生活助手。凡涉及实时天气，必须先调用 get_weather，不要凭记忆回答。"

def run(question: str, max_steps: int = 5) -> str:
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": question},
    ]

    for _ in range(1, max_steps + 1):
        resp = create(messages=messages, tools=TOOLS)
        msg = resp.choices[0].message

        # 关键 1：assistant 消息（含 tool_calls）必须先入历史
        messages.append(msg.model_dump(exclude_none=True))

        if not msg.tool_calls:                 # 没有工具调用 = 终态
            return msg.content or ""

        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments or "{}")

            try:
                result = get_weather(**args)
            except Exception as exc:           # 参数错误也要回灌，模型才能改
                result = json.dumps({"error": str(exc)}, ensure_ascii=False)

            # 关键 2：tool 消息用 tool_call_id 与上面的调用一一对应
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    return "达到最大步数仍未得到最终答案"

if __name__ == "__main__":
    print(run("北京今天天气怎么样？适合跑步吗？"))
```

### 3. 完整消息流长什么样

```
① user      北京今天天气怎么样？适合跑步吗？
② assistant content=None, tool_calls=[{id: "call_weather_1",
             function: {name: "get_weather", arguments: '{"city": "北京"}'}}]
③ tool      tool_call_id="call_weather_1", content='{"city":"北京","condition":"晴",...}'
④ assistant "北京今天晴，24℃，AQI 62，适合跑步……"
```

三个高频坑都在这里：

| 坑 | 后果 | 正确做法 |
| --- | --- | --- |
| 不回灌 assistant 消息 | 400：tool 消息没有对应的 tool_calls | 先 append assistant（含 `tool_calls`），再 append tool |
| `tool_call_id` 写错 | 400 或模型答非所问 | 直接用 `tc.id`，不要自己编 |
| 工具异常直接抛出 | 循环中断，模型没有纠错机会 | 捕获异常，把 `{"error": ...}` 当结果回灌 |

## v2：多工具循环 Agent（约 100 行）

v2 在 v1 上补齐五件事：第二个工具、多轮循环、最大迭代次数、重复调用检测、trace 落盘。

```python
# v2_agent.py
import json
import re
import time

from llm_client import create

MAX_STEPS = 6

def get_weather(city: str) -> str:
    db = {"北京": {"condition": "晴", "temp_c": 24, "aqi": 62},
          "上海": {"condition": "多云", "temp_c": 27, "aqi": 48}}
    if city not in db:
        return json.dumps({"error": f"暂不支持城市 {city}"}, ensure_ascii=False)
    return json.dumps({"city": city, **db[city]}, ensure_ascii=False)

def calculator(expression: str) -> str:
    if not re.fullmatch(r"[\d\.\+\-\*/\(\)\s]+", expression):
        raise ValueError("只支持数字与 + - * / 运算")
    value = eval(expression, {"__builtins__": {}}, {})   # 字符集已限制，避免执行任意代码
    return json.dumps({"expression": expression, "value": round(value, 4)}, ensure_ascii=False)

TOOLS = [
    {"type": "function", "function": {
        "name": "get_weather",
        "description": "查询指定城市当天的实时天气，返回天气状况、气温和 AQI。",
        "parameters": {"type": "object", "properties": {"city": {"type": "string", "description": "中文城市名"}},
                       "required": ["city"], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "calculator", "description": "计算数学表达式，支持 + - * /。涉及精确数字时使用。",
        "parameters": {"type": "object", "properties": {"expression": {"type": "string", "description": "如 23.5 * 1.08"}},
                       "required": ["expression"], "additionalProperties": False}}},
]

TOOL_MAP = {"get_weather": get_weather, "calculator": calculator}

class Tracer:
    def __init__(self, path="trace.jsonl"):
        self._f = open(path, "a", encoding="utf-8")

    def log(self, **event):
        event["ts"] = time.strftime("%H:%M:%S")
        self._f.write(json.dumps(event, ensure_ascii=False) + "\n")
        self._f.flush()
        print(json.dumps(event, ensure_ascii=False))

def run_agent(question: str, tracer: Tracer) -> str:
    messages = [
        {"role": "system", "content": "你是生活助手。需要实时信息或精确计算时必须调用工具，不要编造。"},
        {"role": "user", "content": question},
    ]
    seen = {}

    for step in range(1, MAX_STEPS + 1):
        msg = create(messages=messages, tools=TOOLS).choices[0].message
        messages.append(msg.model_dump(exclude_none=True))
        tracer.log(step=step, type="llm", content=msg.content, tool_calls=[
            {"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments}
            for tc in (msg.tool_calls or [])
        ])

        if not msg.tool_calls:
            tracer.log(step=step, type="final", content=msg.content)
            return msg.content or ""

        for tc in msg.tool_calls:
            name, raw = tc.function.name, tc.function.arguments
            try:
                args = json.loads(raw or "{}")
                if not isinstance(args, dict):
                    raise ValueError("arguments 必须是 JSON 对象")
            except (json.JSONDecodeError, ValueError) as exc:
                result = json.dumps({"error": f"参数解析失败：{exc}，请重新生成合法 JSON"},
                                    ensure_ascii=False)
            else:
                signature = f"{name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"
                seen[signature] = seen.get(signature, 0) + 1
                if seen[signature] > 1:              # 刹车 1：重复调用
                    tracer.log(step=step, type="guard", reason="duplicate", signature=signature)
                    return "检测到重复的工具调用，已中止。请换一种方式提问。"
                if name not in TOOL_MAP:             # 刹车 2：工具白名单
                    result = json.dumps({"error": f"未知工具 {name}"}, ensure_ascii=False)
                else:
                    try:
                        result = TOOL_MAP[name](**args)
                    except Exception as exc:         # 工具异常回灌给模型
                        result = json.dumps({"error": f"{type(exc).__name__}: {exc}"},
                                            ensure_ascii=False)

            tracer.log(step=step, type="tool", tool=name, result=result)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    tracer.log(type="guard", reason="max_steps", max_steps=MAX_STEPS)   # 刹车 3：迭代上限
    return "已达到最大步数，任务终止。"

if __name__ == "__main__":
    print(run_agent("北京今天天气怎么样？适合跑步吗？", Tracer("trace.jsonl")))
```

这段代码刻意保留了「不优雅」：所有逻辑在一个函数里，方便你看清 Agent 的真正骨架。生产代码会把工具、模型、trace、护栏拆成独立模块——但拆完还是这三步：**调用模型 → 执行工具 → 回灌结果**。

## 一次真实运行轨迹

问题：**「北京今天天气怎么样？适合跑步吗？」**

```text
[10:21:02] step=1 type=llm    content=None
  tool_calls = [{"id": "call_weather_1", "name": "get_weather", "arguments": "{\"city\": \"北京\"}"}]

[10:21:02] step=1 type=tool   get_weather → {"city":"北京","condition":"晴","temp_c":24,"aqi":62}

[10:21:03] step=2 type=llm    content="北京今天晴，24℃，AQI 62，适合跑步……"
[10:21:03] step=2 type=final  同上
```

对应 `trace.jsonl` 里就是这四行事件，`type` 分别是 `llm / tool / llm / final`。

逐步解释模型为什么这样决策：

| 步骤 | 模型看到了什么 | 为什么这样决策 |
| --- | --- | --- |
| 第 1 轮 | system 约束 + 用户问题 + 工具清单 | 问题含「今天天气」，模型自己不知道实时天气，工具描述写明「实时天气」→ 选 `get_weather` |
| 参数生成 | Schema 要求 `city: string` | 从「北京今天……」抽取城市，生成 `{"city": "北京"}`，并带上唯一 `id` |
| 第 2 轮 | assistant 的 `tool_calls` + 一条 `role="tool"` 的结果 | 已经拿到 `condition/temp_c/aqi`，信息足够回答「适不适合跑步」，不再调工具，直接生成终态 |
| 答案措辞 | 工具返回 24℃、AQI 62 | 模型做常识判断：温度适宜、空气良好 → 适合跑步，并补一句防晒/避开高温的建议 |

注意：**「适合跑步」不是工具算出来的**，是模型基于工具事实做的常识推理。这也是为什么工具要返回结构化字段（温度、AQI），而不是一句「天气不错」——后者会剥夺模型的推理依据。

## 调试与排错

### 打印完整 messages

出问题时先看消息，不要先怀疑模型：

```python
import json

def dump(messages):
    for i, m in enumerate(messages):
        print(i, m["role"], m.get("tool_call_id"), json.dumps(m, ensure_ascii=False)[:300])
```

如果是 SDK 返回的对象，先 `model_dump()` 再序列化；直接 `json.dumps(msg)` 会报 `not JSON serializable`。

### 保存 trace

- 每次 LLM 调用记录：`messages` 摘要、`tool_calls`、`finish_reason`、token 用量、耗时；每次工具调用记录：工具名、入参、出参、异常、耗时。
- 用 JSONL（一行一个事件）而不是一个大 JSON，便于追加、grep 和后续导入评估系统（详见第 09 章）。

### 常见错误速查表

| 现象 | 常见原因 | 处理 |
| --- | --- | --- |
| `401 AuthenticationError` | Key 没导出、拼错、过期 | `echo $DEEPSEEK_API_KEY`；确认 `USE_FAKE_LLM=0` |
| `400 invalid tools` | Schema 少了 `type/function/parameters`，或 `required` 写成字符串 | 用 JSON Schema 校验器检查；`required` 必须是数组 |
| 模型从不调工具 | `description` 太含糊；问题无需工具；模型能力弱 | 写清「何时用/返回什么」；必要时 `tool_choice="required"` |
| 模型连续调同一工具 | 工具结果没解决问题、结果太长/格式差 | 加重复检测；把错误和空结果明确回灌；精简返回值 |
| 死循环 / 步数爆炸 | 没有上限，或模型一直「再查一次」 | `MAX_STEPS` + 重复签名检测 + 预算告警 |
| `JSONDecodeError: arguments` | 模型输出空串或非法 JSON | `try/except` 后把错误回灌，让模型重试；Schema 加 `additionalProperties: False` |
| `tool_call_id not found` | 漏回灌、id 写错、一条 assistant 消息对应多个调用却只回了一条 | 每个 `tc.id` 必须有一条 `role="tool"` 消息 |
| `content=None` 导致拼接报错 | 模型返回 `tool_calls` 时 `content` 通常为空 | 统一用 `msg.content or ""` |
| `finish_reason=length` | 输出被 max_tokens 截断，工具调用 JSON 不完整 | 提高 `max_tokens`；把截断事件记入 trace |

一个快速判断法：看 `finish_reason`。`tool_calls` 表示模型要调工具，`stop` 表示正常结束，`length` 表示被截断。如果它明明是 `stop` 却答非所问，那多半是 `messages` 拼错了，而不是模型笨。

## 从 Demo 到生产还缺什么

| 缺口 | Demo 现状 | 生产要补的东西 | 详见 |
| --- | --- | --- | --- |
| 状态持久化 | `messages` 在内存，进程挂就全丢 | 检查点存储、断点续跑、会话恢复 | 第 06 章 |
| 人工审批 | 工具被模型直接执行 | 写操作前中断，等人确认（Human-in-the-loop） | 第 06 章 |
| 可观测性 | `print` + JSONL | trace_id、span、token/延迟/成本指标、告警 | 第 09 章 |
| 评估 | 凭感觉试几个问题 | 固定测试集、成功率/平均步数/单任务成本 | 第 09 章 |
| 多租户与权限 | 单用户、单 Key、全部工具可见 | 租户隔离、配额、工具级权限、审计日志 | 第 09 / 10 章 |

判断标准很简单：**如果这个 Agent 挂了，你能不能从日志还原它每一步做了什么、花了多少钱、为什么停下？** 答不上来就还在 Demo 阶段。

## 练习题

1. **加一个工具**：实现 `get_time(city, timezone)`，故意传错时区，观察错误如何回灌给模型、模型是否会改正重试。
2. **接真实 API**：把 `get_weather` 换成真实天气接口（和风 / OpenWeather），处理超时与 429，记录模型在失败后的行为变化。
3. **加人工审批**：在 `calculator` 执行前用 `input()` 模拟审批，拒绝时回灌「用户拒绝执行」，对比 trace 与最终答案的差异。

## 常见问题

**Q：为什么不用 LangChain，直接手写不重复造轮子吗？**
A：第一遍必须手写，否则你无法定位「模型没调工具」到底是提示词问题、Schema 问题，还是框架把工具藏起来了。理解循环后，第 06 章再用 LangGraph 解决状态持久化和人工审批，才知道框架替你做了什么。

**Q：离线 `FakeLLM` 和真实模型差在哪？**
A：它只用关键词规则返回固定的 `tool_calls`，用于验证消息结构、循环、刹车和 trace，不理解语义。真实模型的工具选择、参数抽取、纠错能力都强得多，但也更不确定——所以护栏必须自己写。

**Q：为什么模型有时不调用工具？**
A：按概率从高到低：`description` 没写清用途；问题确实不需要工具；`tool_choice` 或模型不支持工具调用；上下文里已经有答案。先改描述、加「涉及实时信息必须调用」的 system 约束，再考虑换模型。

**Q：`max_steps` 设多少合适？**
A：按任务复杂度分档：单工具问答 3~5，多工具任务 6~10，研究型 15~30。更重要的是同时看平均步数，如果 80% 的任务 4 步内结束，上限设 10 就足够兜底。

**Q：工具返回错误，应该抛异常还是回灌？**
A：回灌。异常会中断循环，模型失去纠错机会；把 `{"error": "...", "hint": "..."}` 作为 tool 消息回灌，模型往往能改参数或换工具。只有鉴权失败、配额耗尽这类「重试也没用」的错误才直接终止。

## 自测

1. 画出一次 Function Calling 的完整消息流，标出 `tool_calls` 与 `tool_call_id` 的对应关系。
2. 如果删掉 `messages.append(msg.model_dump(...))` 这一行，会发生什么？为什么？
3. 给 v2 再加两个护栏：token 预算上限、危险工具审批，分别写在哪一步？
4. 用自己的话说清：为什么「工具返回结构化 JSON」比「返回一句自然语言」更有利于 Agent 推理？

## 参考与官方链接

- [OpenAI Function Calling 指南](https://platform.openai.com/docs/guides/function-calling)
- [OpenAI Python SDK](https://github.com/openai/openai-python)
- [DeepSeek API 文档](https://api-docs.deepseek.com/)
- [JSON Schema 入门](https://json-schema.org/learn/getting-started-step-by-step)
- [Anthropic: Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
