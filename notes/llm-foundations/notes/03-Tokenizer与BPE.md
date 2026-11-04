# 03 Tokenizer与BPE

## 一句话

**Tokenizer 是文本与模型之间的翻译官**：把字符串切成 token 序列并映射为整数 id。BPE（字节对编码）通过「反复合并最高频相邻对」从语料中自动学出词表，是 GPT/LLaMA/Qwen 的事实标准。Token 化质量直接影响模型效果、推理成本和中文能力。

## 为什么需要 Tokenizer

模型只认识数字，不能直接吃字符串。那按什么粒度切？

| 切分粒度 | 例子（"unbelievable"） | 优点 | 缺点 |
| --- | --- | --- | --- |
| 按词切 | `["unbelievable"]` | 语义完整 | 词表爆炸（英语百万词+变形）；OOV（未登录词）无法处理 |
| 按字符切 | `["u","n","b",...]` | 词表极小、无 OOV | 序列太长（10 倍+），语义碎片化，模型难学 |
| **按子词切（BPE）** | `["un","believ","able"]` | 词表可控（3-15 万）、无 OOV、序列适中 | 切分结果有时反直觉 |

子词（subword）是工程上的甜点：**常见词整词保留，罕见词拆成有意义的片段，再罕见的拆到字节**——任何文本都能表示，永不 OOV。

## BPE 算法流程

### 训练阶段（从语料学词表）

```
输入：语料 + 目标词表大小 V（如 32000）
初始化：词表 = 256 个字节（或 Unicode 字符）
循环直到词表达到 V：
  1. 统计语料中所有相邻 token 对的频率
  2. 合并最高频的一对为新 token，加入词表
  3. 用这个新 token 替换语料中所有出现
输出：词表 + 按顺序的合并规则表（merge list）
```

### 手动推演一遍迷你 BPE

语料：`low low low lower newest newest widest`

```
初始（按字符+词尾标记 </w>）:
l o w </w> ×3 | l o w e r </w> | n e w e s t </w> ×2 | w i d e s t </w>

第 1 轮：最高频对 (e, s) 出现 3 次 → 合并为 es
第 2 轮：最高频对 (es, t) 出现 3 次 → 合并为 est
第 3 轮：(est, </w>) ×3 → 合并为 est</w>
第 4 轮：(l, o) ×4 → 合并为 lo
第 5 轮：(lo, w) ×4 → 合并为 low
...
最终 "lowest" 会被切成 ["low", "est</w>"] —— 即使训练时没见过这个词！
```

### Python 极简实现

```python
from collections import Counter

def train_bpe(corpus: list[str], vocab_size: int):
    """corpus: 词列表；返回合并规则表"""
    # 初始化：每个词拆成字符元组，词尾加 </w>
    words = [tuple(w) + ("</w>",) for w in corpus]
    vocab = set(ch for w in words for ch in w)
    merges = []

    while len(vocab) < vocab_size:
        pairs = Counter()
        for w in words:
            for a, b in zip(w, w[1:]):
                pairs[(a, b)] += 1
        if not pairs:
            break
        best = pairs.most_common(1)[0][0]
        merges.append(best)
        vocab.add("".join(best))
        # 全语料执行这次合并
        words = [merge_pair(w, best) for w in words]
    return merges, vocab

def merge_pair(word, pair):
    out, i = [], 0
    while i < len(word):
        if i < len(word) - 1 and (word[i], word[i+1]) == pair:
            out.append("".join(pair)); i += 2
        else:
            out.append(word[i]); i += 1
    return tuple(out)

corpus = ["low"]*5 + ["lower"]*2 + ["newest"]*6 + ["widest"]*3
merges, vocab = train_bpe(corpus, vocab_size=30)
print("学到的前 5 条合并规则:", merges[:5])
# 输出: [('e','s'), ('es','t'), ('est','</w>'), ('l','o'), ('lo','w')]
```

### 推理阶段（编码新文本）

规则简单：**按 merge list 的顺序依次应用合并**——顺序即优先级。一个词可能被切成多种合法方案，但按规则表贪心执行保证结果唯一确定（确定性是 BPE 的重要性质）。

## 主流工具：SentencePiece 与 tiktoken

| 工具 | 出品 | 使用者 | 特点 |
| --- | --- | --- | --- |
| SentencePiece | Google | LLaMA、GLM、T5 | 把输入当原始流（空格也当字符 ▁），语言无关，训练/编码一体 |
| tiktoken | OpenAI | GPT-3.5/4 系列 | BPE 实现，Rust 内核极快（比 HF tokenizer 快 5-10x），直接 pip 安装 |
| HuggingFace Tokenizers | HF 社区 | 绝大多数开源模型 | Rust 内核 + Python 绑定，支持 BPE/WordPiece/Unigram |

```python
# tiktoken 快速体验
import tiktoken
enc = tiktoken.get_encoding("cl100k_base")   # GPT-4 用的词表
ids = enc.encode("大语言模型正在改变世界")
print(ids)                    # [9468, 243, 169, 253, ...]
print(enc.decode(ids))        # 还原
print([enc.decode([i]) for i in ids])  # 逐 token 看切分
```

```python
# SentencePiece 训练自己的 tokenizer
import sentencepiece as spm
spm.SentencePieceTrainer.train(
    input="corpus.txt", model_prefix="my_sp",
    vocab_size=32000, model_type="bpe",
    character_coverage=0.9995,   # 中文语料建议 0.9995
)
sp = spm.SentencePieceProcessor(model_file="my_sp.model")
print(sp.encode("大语言模型", out_type=str))   # ['▁大', '语言', '模型']
```

## 中文 Token 化的特殊问题

| 问题 | 说明 | 影响 |
| --- | --- | --- |
| 汉字切分碎 | 英文为主的词表里，一个汉字常被拆成 2-3 个字节级 token | 中文推理成本比英文高 2-3 倍 |
| 无天然分隔符 | 中文没有空格，子词边界全靠统计学习 | 切分质量更依赖语料配比 |
| 数字切分 | "2026" 可能被切成 "20"+"26"，影响数学能力 | 新模型普遍把 0-999 做成独立 token |
| 标点全半角 | 全角标点可能未被词表覆盖而退化成字节 | 预处理归一化很重要 |

**衡量指标——fertility（生育率）**：平均每个字/词被切成几个 token。越低越好。

```
英文好词表: "hello world" → 2 token      fertility ≈ 1.0/词
中文差词表: "人工智能" → 6~8 token        fertility ≈ 1.5-2.0/字
中文好词表: "人工智能" → 2~3 token        fertility ≈ 0.5-0.75/字
```

Qwen/GLM/DeepSeek 等国产模型都在词表中扩充了中文高频字词，中文 fertility 显著优于 LLaMA-2（LLaMA-3 已大幅改善）。

## 词表大小的权衡

| 词表大小 | 优点 | 缺点 | 代表 |
| --- | --- | --- | --- |
| 小（32K） | Embedding 参数少；单 token 语义强 | 序列长、编码碎、罕见语言差 | LLaMA-1/2（32K） |
| 中（50-100K） | 均衡 | — | GPT-2（50K）、Qwen-1（151K 偏大） |
| 大（100K-256K） | 序列短、多语言好、推理省 token | Embedding 占参数比例升高；稀有 token 训练不充分 | GPT-4（100K）、LLaMA-3（128K）、DeepSeek-V3（129K） |

**经验法则**：
- 多语言/中文场景 → 词表大一些（100K+）
- 小模型（<3B）→ 词表别太大，否则 Embedding 吃掉太多参数预算（32K 词表 × 4096 维 ≈ 1.3 亿参数）
- 稀有 token 训练不充分会产生"异物 token"（glitch tokens），触发异常输出

## 与成本直接相关：API 按 token 计费

```
GPT-4o: 输入 $2.5 / 1M token，输出 $10 / 1M token
一篇 2000 字中文文章 ≈ 3000-4000 token（中文 fertility 高！）
同样内容英文 ≈ 1500 token
```

工程启示：**中文业务的 token 成本天然比英文高约 2 倍**——做预算、设计上下文窗口、评估 RAG 分块大小时必须考虑。

## 常见问题

**Q：BPE 和 WordPiece 有什么区别？**
A：合并准则不同。BPE 合并"频率最高"的对；WordPiece（BERT 用）合并"似然提升最大"的对（频率/左右各自频率）。效果接近，BPE 更简单主流。

**Q：为什么 LLaMA-2 的中文很差，LLaMA-3 明显改善？**
A：词表从 32K 扩到 128K，大量中文高频字词成为独立 token；同时中文预训练语料比例大幅提升。Tokenizer 是语言能力的地基。

**Q：能不能给开源模型扩充中文词表？**
A：可以（词表扩充 + Embedding 初始化 + 继续预训练），中文社区对 LLaMA 做过（Chinese-LLaMA）。但成本不低，现在直接选 Qwen/DeepSeek 更划算。

**Q：token id 是连续的吗？特殊 token 有哪些？**
A：id 从 0 连续编号。特殊 token 如 `<|begin_of_text|>`（BOS）、`<|end_of_text|>`（EOS）、`<|im_start|>`/`<|im_end|>`（对话标记）、`[PAD]`。训练对话模板时用它们分隔角色。

**Q：为什么 tiktoken 里 "hello" 和 " hello"（带空格）是不同的 token？**
A：BPE 把前导空格当作字符参与合并，词首位置是重要特征。" hello" 通常是单个 token 而 "hello" 在句中可能拆开——这也是 Prompt 里空格/换行会微妙影响输出的原因。

## 自测

1. 用 BPE 训练流程手动处理语料 `["aab", "aab", "abc"]`，写出前 3 轮合并。
2. 解释为什么子词切分能同时解决"词表爆炸"和"OOV"两个对立问题。
3. 什么是 fertility？为什么中文业务的 API 成本要按英文 2 倍估算？
4. 词表从 32K 扩到 128K，对 Embedding 层参数量、推理速度、多语言能力分别有什么影响？
5. 用 tiktoken 统计你的一段中文 Prompt 的 token 数，估算一次 GPT-4o 调用的成本。

## 参考与官方链接

- [BPE 原始论文（Neural Machine Translation of Rare Words）](https://arxiv.org/abs/1508.07909)
- [SentencePiece](https://github.com/google/sentencepiece)
- [tiktoken](https://github.com/openai/tiktoken)
- [HuggingFace Tokenizers](https://github.com/huggingface/tokenizers)
- [HuggingFace LLM Course: Tokenizers](https://huggingface.co/learn/llm-course/chapter6/1)
