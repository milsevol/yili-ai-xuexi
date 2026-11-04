# 02 Prompt 结构与 Few-shot

## 一句话

**一个工程级 Prompt 由四要素组成：角色（Role）、指令（Instruction）、上下文（Context）、输出格式（Output Format）**；Few-shot（给少量示例）是提升输出稳定性最有效的单一技巧，示例的选择和顺序都会显著影响效果。

## Prompt 四要素

### 1. 角色（Role）—— 告诉模型「你是谁」

```text
你是一名有 10 年经验的电商客服主管，擅长用共情的语气处理投诉。
```

| 写角色 | 不写角色 |
| --- | --- |
| 语气、专业深度、用词风格更稳定 | 输出风格随机，时而口语时而书面 |
| 模型自动激活相关领域知识 | 回答停留在通用水平 |

**注意**：角色不是万能咒语。「你是诺贝尔奖得主」不会让模型变聪明，角色只对**风格和知识侧重**有影响。

### 2. 指令（Instruction）—— 告诉模型「做什么」

**反面 vs 正面**：

| ❌ 模糊指令 | ✅ 精确指令 |
| --- | --- |
| 总结一下这篇文章 | 用 3 句话总结这篇文章，每句不超过 30 字，面向不了解该领域的读者 |
| 分析一下这个评论 | 判断该评论的情感倾向（正面/负面/中性），并列出判断依据的关键词 |
| 写得专业一点 | 用书面语，避免「家人们」「宝子」等口语，术语首次出现给英文原名 |

**原则**：指令要包含**动作 + 对象 + 约束**。「分类这段文本」→「把这段文本分到 {售前咨询, 售后投诉, 闲聊} 之一，只输出类别名」。

### 3. 上下文（Context）—— 给模型「它需要的信息」

上下文是模型回答的依据。常见来源：

- 用户输入本身（要分类的评论、要翻译的句子）
- RAG 检索到的文档片段
- 业务背景说明（产品线、术语表、政策条款）
- 历史对话记录

**坑位提醒**：

| 坑 | 后果 | 对策 |
| --- | --- | --- |
| 上下文太长 | 中间信息被忽略（Lost in the Middle） | 关键信息放开头或结尾 |
| 上下文与任务无关 | 模型被无关信息带偏 | 只放任务相关的最小信息集 |
| 未标注上下文边界 | 模型分不清指令和数据，易被注入 | 用分隔符包裹，如 `"""..."""` 或 XML 标签 |

### 4. 输出格式（Output Format）—— 告诉模型「怎么答」

```text
请严格按以下 JSON 格式输出，不要输出任何其他内容：
{"label": "类别名", "confidence": 0到1之间的数字, "reason": "不超过20字"}
```

| 约束输出格式 | 不约束 |
| --- | --- |
| 程序可解析，可进 pipeline | 自由文本，解析靠运气 |
| 输出稳定，格式错误率低 | 时而加前缀「好的，答案是…」 |

## 完整示例：四要素拼装

```python
# OpenAI SDK 风格伪代码
from openai import OpenAI

client = OpenAI()

prompt = f"""
【角色】你是一名资深电商评论分析师。

【指令】把下面的用户评论分到以下三类之一：售前咨询、售后投诉、闲聊。
只输出类别名，不要输出任何解释。

【上下文】
- 售前咨询：询问商品参数、库存、优惠等购买前问题
- 售后投诉：已购买用户反馈质量、物流、退款等问题
- 闲聊：与商品无关的闲聊内容

【评论】
{review}
"""

resp = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}],
    temperature=0,          # 分类任务要确定性，温度调 0
)
print(resp.choices[0].message.content)
```

## Zero-shot vs Few-shot

| 维度 | Zero-shot（零示例） | Few-shot（少示例，通常 1~8 个） |
| --- | --- | --- |
| Prompt 长度 | 短 | 长（每个示例都占 token） |
| 成本/延迟 | 低 | 高（示例每次都重复发送） |
| 输出格式稳定性 | 一般 | **显著提升** |
| 边界 case 表现 | 依赖模型常识 | 可用示例「教会」边界判定 |
| 适用场景 | 简单任务、格式自由 | 格式严格、边界模糊、领域特殊 |

**经验**：先用 Zero-shot 跑评估集，如果格式错误率 > 5% 或边界 case 大量出错，就加 Few-shot。Few-shot 是「用 token 换稳定性」。

## Few-shot 实战

### 基本结构

```text
【指令】判断评论情感，输出 JSON。

【示例】
评论：物流太慢了，等了一周才到     → {"label": "负面", "aspect": "物流"}
评论：质量很好，已回购第三次       → {"label": "正面", "aspect": "质量"}
评论：请问这个有 1.5 米规格的吗？   → {"label": "中性", "aspect": "售前咨询"}

【待处理】
评论：{review}
→
```

### 示例选择策略（按效果排序）

| 策略 | 做法 | 适用 |
| --- | --- | --- |
| 覆盖类别 | 每个类别至少 1 个示例 | 分类任务必选 |
| 覆盖边界 | 选最容易判错的 case 当示例 | badcase 驱动迭代 |
| 语义相似 | 用向量检索找与当前输入最像的示例 | 输入差异大的开放任务 |
| 多样性 | 示例的句式、长度、用词尽量不同 | 防模型过拟合示例表面模式 |

**反模式**：

| ❌ 差的示例集 | ✅ 好的示例集 |
| --- | --- |
| 8 个示例全是「正面」 | 正/负/中性各 2~3 个 |
| 示例都是短句 | 长短混合，覆盖真实分布 |
| 示例输出格式不一致 | 所有示例输出格式严格统一 |
| 示例来自想象 | 示例来自真实 badcase |

### 示例顺序的影响

- 模型对**最后看到的示例**有轻微偏向（recency bias）
- 类别不平衡的示例集会拉偏输出分布（8 个正面示例后，模型更倾向答「正面」）
- **对策**：类别均衡摆放；评估时打乱顺序多跑几次取稳定结果；关键任务可对同一输入用不同示例顺序投票

## 评估 Few-shot 效果的代码骨架

```python
# OpenAI SDK 风格伪代码：批量跑评估集，算准确率
import json
from openai import OpenAI

client = OpenAI()

def classify(review: str, examples: list[dict]) -> str:
    shots = "\n".join(
        f"评论：{e['text']} → {json.dumps(e['output'], ensure_ascii=False)}"
        for e in examples
    )
    prompt = f"""判断评论情感，输出 JSON：{{"label": "正面|负面|中性"}}

【示例】
{shots}

【待处理】
评论：{review}
→"""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return resp.choices[0].message.content

# 评估集：每条含输入和期望输出
eval_set = json.load(open("eval_set.json", encoding="utf-8"))

correct = 0
for item in eval_set:
    pred = json.loads(classify(item["text"], examples=FEW_SHOT_EXAMPLES))
    if pred["label"] == item["expected"]:
        correct += 1

print(f"准确率: {correct}/{len(eval_set)} = {correct/len(eval_set):.1%}")
```

**工程要点**：

- `temperature=0`：分类/抽取任务要确定性
- 评估集固定在文件里，每次改 Prompt 后重跑对比
- 记录每条 badcase，优先把高频 badcase 改造成示例加进 Few-shot

## 常见问题

**Q：Few-shot 示例越多越好吗？**
A：不是。通常 3~8 个就到收益拐点，再多主要增加成本，还可能引入噪声。先加最能解决 badcase 的示例。

**Q：示例的输出格式和实际要求不一致会怎样？**
A：模型会模仿示例的格式而不是你文字描述的格式。**示例的优先级高于文字指令**——这是最常见的 Few-shot 翻车原因。

**Q：可以把示例放到 system message 里吗？**
A：可以，且推荐。system message 放角色 + 指令 + 示例，user message 只放待处理输入，结构更清晰，也更利于提示词缓存（prefix caching）降本。

**Q：分隔符用 ``` 还是 XML 标签？**
A：都行，关键是**全文统一**。Anthropic 系模型对 XML 标签（`<context>...</context>`）响应更好，OpenAI 系两者皆可。重点是让模型明确区分「指令」和「数据」。

**Q：Few-shot 和微调给的示例有什么区别？**
A：Few-shot 示例在**每次调用时随 Prompt 发送**（占 token、可即时改）；微调示例在**训练时烧进模型权重**（调用时不用再发，但改一次要重新训练）。示例少且常改 → Few-shot；示例多且稳定 → 微调。

## 自测

1. 默写 Prompt 四要素，并各举一个「没写 vs 写了」的正反对比例。
2. 为什么示例的输出格式比文字描述更重要？
3. 你的分类任务有 5 个类别，Few-shot 示例应该怎么选、怎么排？
4. 写一个评估 Few-shot 效果的 Python 循环，说明 temperature 应该设多少、为什么。

## 参考与官方链接

- [OpenAI Few-shot 最佳实践](https://platform.openai.com/docs/guides/prompt-engineering)
- [Anthropic：使用示例提升输出质量](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/multishot-prompting)
- [Prompt 缓存降本](https://platform.openai.com/docs/guides/prompt-caching)
- [Language Models are Few-Shot Learners（GPT-3 论文）](https://arxiv.org/abs/2005.14165)
