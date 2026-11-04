# 02 Transformer架构详解

## 一句话

**Transformer 的核心是 Self-Attention**：每个 token 用 Query 去和所有 token 的 Key 算相似度，加权求和 Value 得到新表示——一次矩阵运算完成全序列信息交换，可并行、可堆叠。现代 LLM 基本都是它的 Decoder-only 变体。

## 整体结构：一张图看懂

```
输入文本 → Tokenizer → token id 序列
    ↓
Embedding 层（id → 向量）+ 位置编码
    ↓
┌─────────── Transformer Block × N 层 ───────────┐
│  ① Multi-Head Self-Attention（信息交换）         │
│  ② Add & LayerNorm（残差 + 归一化）              │
│  ③ FFN 前馈网络（非线性变换，2/3 参数在这）       │
│  ④ Add & LayerNorm                              │
└────────────────────────────────────────────────┘
    ↓
输出层（向量 → 词表上的概率分布）→ 预测下一个 token
```

以 LLaMA-7B 为例：N=32 层，隐藏维度 d_model=4096，注意力头数 32，FFN 中间维度 11008。

## Self-Attention 计算过程

### 第一步：Q/K/V 三个投影

每个 token 的输入向量 x（维度 d_model）分别乘三个权重矩阵：

```
Q = x @ W_q    # Query：我在找什么
K = x @ W_k    # Key：我是什么
V = x @ W_v    # Value：我携带什么信息
```

### 第二步：缩放点积注意力

$$Attention(Q, K, V) = softmax\left(\frac{QK^T}{\sqrt{d_k}}\right)V$$

逐步拆解（假设 4 个 token，d_k=64）：

```
1. Q @ K.T        → [4, 4] 相似度矩阵：每个 token 对其他 token 的关注分
2. / sqrt(64)     → 缩放！防止点积过大导致 softmax 梯度消失
3. softmax(行)     → 每行归一化为概率分布（权重和为 1）
4. @ V            → [4, 64] 加权求和，完成信息混合
```

**为什么要除以 √d_k**：维度越大，点积的方差越大，softmax 会进入饱和区（梯度≈0）。除以 √d_k 让方差回到 1 附近。

### 第三步：因果掩码（Decoder-only 的关键）

生成任务不能让 token 看到未来。加一个下三角掩码：

```
掩码前注意力分数（4 个 token）:
[[ 2.1,  0.3, -1.2,  0.8],
 [ 1.5,  2.8,  0.4, -0.3],
 [ 0.2,  1.1,  2.5,  1.9],
 [-0.5,  0.7,  1.3,  2.2]]

加因果掩码（上三角置 -inf，softmax 后变 0）:
[[ 2.1, -inf, -inf, -inf],
 [ 1.5,  2.8, -inf, -inf],
 [ 0.2,  1.1,  2.5, -inf],
 [-0.5,  0.7,  1.3,  2.2]]
```

### 完整 numpy 实现（可直接运行）

```python
import numpy as np

def softmax(x, axis=-1):
    x = x - x.max(axis=axis, keepdims=True)  # 数值稳定
    e = np.exp(x)
    return e / e.sum(axis=axis, keepdims=True)

def causal_self_attention(x, W_q, W_k, W_v):
    """x: [seq_len, d_model]，返回 [seq_len, d_k]"""
    seq_len, d_model = x.shape
    Q, K, V = x @ W_q, x @ W_k, x @ W_v
    d_k = Q.shape[-1]

    scores = Q @ K.T / np.sqrt(d_k)                    # [seq, seq] 相似度
    mask = np.triu(np.ones((seq_len, seq_len)), k=1)   # 上三角=1
    scores = scores - mask * 1e9                        # 未来位置置 -inf
    attn = softmax(scores)                              # 注意力权重
    return attn @ V, attn

# 模拟 5 个 token、d_model=8 的输入
rng = np.random.default_rng(42)
x = rng.normal(size=(5, 8))
W_q, W_k, W_v = (rng.normal(size=(8, 8)) for _ in range(3))

out, attn = causal_self_attention(x, W_q, W_k, W_v)
print("注意力权重矩阵（每行和为 1，上三角为 0）:")
print(np.round(attn, 3))
```

### 多头注意力（Multi-Head）

不只做一次注意力，而是把 d_model 切成 h 份，各自独立做注意力再拼接：

```
MultiHead(x) = Concat(head_1, ..., head_h) @ W_o
head_i = Attention(x @ W_q_i, x @ W_k_i, x @ W_v_i)
```

| 设计 | 作用 |
| --- | --- |
| 多头切分 | 不同头学习不同模式（语法、指代、位置、语义） |
| 每头维度 d_k = d_model / h | 总计算量与单头相当，表达能力更强 |
| 输出投影 W_o | 把拼接结果映射回 d_model |

经验值：d_model=4096、h=32 → 每头 128 维。头数不是越多越好，超过维度瓶颈后收益递减。

## 位置编码：让模型知道顺序

Self-Attention 本身对顺序不敏感（打乱输入，输出也对应打乱），必须显式注入位置信息。

### 正弦位置编码（原始 Transformer）

$$PE_{(pos, 2i)} = \sin\left(\frac{pos}{10000^{2i/d}}\right), \quad PE_{(pos, 2i+1)} = \cos\left(\frac{pos}{10000^{2i/d}}\right)$$

```python
def sinusoidal_pe(max_len=512, d_model=256):
    pos = np.arange(max_len)[:, None]          # [max_len, 1]
    i = np.arange(0, d_model, 2)[None, :]      # [1, d_model/2]
    angle = pos / np.power(10000, i / d_model)
    pe = np.zeros((max_len, d_model))
    pe[:, 0::2] = np.sin(angle)
    pe[:, 1::2] = np.cos(angle)
    return pe
```

优点：无需训练、理论上可外推。缺点：长序列外推实际效果差。

### RoPE 旋转位置编码（现代 LLM 主流）

LLaMA / Qwen / DeepSeek 全部使用 RoPE。核心思想：**不给输入加位置向量，而是按位置旋转 Q/K 向量**——两个 token 的注意力分数只取决于它们的**相对距离**：

```
对 Q、K 的每两个维度 (q_2i, q_2i+1) 看作复数，乘以 e^(i·pos·θ_i)
→ 相当于在二维平面上旋转 pos·θ_i 角度
→ Q_m · K_n 的内积天然包含 (m-n) 的相对位置信息
```

| 位置编码 | 代表模型 | 特点 |
| --- | --- | --- |
| 正弦绝对编码 | 原始 Transformer、BERT | 固定、免训练、外推差 |
| 可学习绝对编码 | GPT-1/2/3 | 简单、受训练长度硬限制 |
| RoPE | LLaMA、Qwen、DeepSeek | 相对位置、外推较好、可配 NTK 插值扩上下文 |
| ALiBi | BLOOM、MPT | 按距离加线性偏置，外推最好 |

## Encoder-Decoder vs Decoder-only

| 架构 | 代表 | 掩码方式 | 适合任务 | 现状 |
| --- | --- | --- | --- | --- |
| Encoder-only | BERT、RoBERTa | 双向（无掩码） | 理解类：分类、NER、检索向量 | 仍是 embedding 模型主流 |
| Encoder-Decoder | T5、原始 Transformer | Encoder 双向 + Decoder 因果 | 翻译、摘要（输入输出结构差异大） | 逐渐被 Decoder-only 取代 |
| Decoder-only | GPT 全系列、LLaMA、Qwen | 因果掩码（只看左边） | 生成、通用对话 | **现代 LLM 事实标准** |

**为什么 Decoder-only 赢了**：
- 架构最简单，训练目标统一（next token prediction），工程 scaling 最顺
- 生成 + Few-shot 能力可以覆盖理解类任务，反过来不行
- 同一个模型既能理解又能生成，部署一份搞定

## LayerNorm 与残差连接

### 残差连接：解决梯度消失

```
输出 = LayerNorm(x + Sublayer(x))     # Post-LN（原始论文）
输出 = x + Sublayer(LayerNorm(x))     # Pre-LN（现代主流）
```

几十层网络没有残差根本训不动——残差让梯度有一条"高速公路"直接回传。

### Pre-LN vs Post-LN

| 方案 | 稳定性 | 最终效果 | 使用者 |
| --- | --- | --- | --- |
| Post-LN | 深层训练易发散，需 warmup | 理论上界略高 | 原始 Transformer、BERT |
| Pre-LN | 训练稳定，可直接堆 100+ 层 | 略低但够用 | GPT、LLaMA 等所有现代 LLM |

### RMSNorm：LayerNorm 的简化版

现代 LLM（LLaMA/Qwen）普遍用 RMSNorm 替代 LayerNorm：

```python
def rms_norm(x, weight, eps=1e-6):
    # LayerNorm 要减均值再除标准差；RMSNorm 只除均方根，少一次减法
    ms = np.mean(x ** 2, axis=-1, keepdims=True)
    return x / np.sqrt(ms + eps) * weight
```

省去均值计算和偏置参数，速度快约 10-30%，效果基本无损。

## FFN 前馈网络

每个 Block 里 Attention 之后接一个两层 MLP：

```
FFN(x) = activation(x @ W_1) @ W_2
维度变化: d_model → 4×d_model → d_model   (经典比例 4 倍)
```

- **参数量占比**：FFN 约占整个模型参数的 **2/3**，Attention 只占 1/3
- **功能定位**：Attention 负责"信息路由"（token 间交换），FFN 负责"知识存储"（可以理解为键值记忆库）
- **激活函数演进**：ReLU → GELU（GPT/BERT）→ **SwiGLU**（LLaMA/Qwen 主流，需 3 个矩阵但效果更好）

## 参数量估算实战（面试高频）

以 LLaMA-7B 为例验证参数账本（d=4096, L=32, V=32000, FFN 中间维 11008）：

```
每层 Attention:  W_q + W_k + W_v + W_o = 4 × d² = 4 × 4096² ≈ 0.67 亿
每层 FFN(SwiGLU): 3 × d × 11008 ≈ 1.35 亿
每层合计 ≈ 2.02 亿 × 32 层 ≈ 64.7 亿
Embedding: V × d = 32000 × 4096 ≈ 1.3 亿
总计 ≈ 66 亿 ≈ 7B ✓
```

**速算公式**：`参数量 ≈ L × (4d² + 3·d·d_ff) + V·d`（SwiGLU 架构）。

## 常见问题

**Q：为什么 Attention 复杂度是 O(n²)，长文本为什么这么贵？**
A：Q@K.T 是 n×n 矩阵，序列长度 n 翻倍，计算量和显存都变 4 倍。这就是长上下文的核心瓶颈，催生了 FlashAttention（IO 感知分块计算）、滑动窗口注意力、稀疏注意力等优化。

**Q：多头注意力里每个头真的学到不同模式吗？**
A：是的，有可视化研究证明：有的头关注句法（主谓对应），有的头关注指代（代词→先行词），有的头几乎只看前一个 token（局部模式）。但也有冗余，实践中可以剪掉 20-30% 的头而不掉点。

**Q：为什么 LLM 都用 Pre-LN 不用 Post-LN？**
A：Pre-LN 的残差通路不被 LayerNorm 打断，梯度能无损回传，百层网络不 warmup 也能稳定收敛。Post-LN 深层训练极易 loss 爆炸。

**Q：RoPE 怎么让 4K 训练的模型支持 32K 推理？**
A：位置插值（Position Interpolation）或 NTK-aware 缩放——推理时把位置索引压缩/缩放回训练范围附近，再少量长文本微调即可。LLaMA-2 到 32K、Qwen 到 128K 都是这套思路。

**Q：FFN 为什么被称作"知识存储"？**
A：有研究（Knowledge Neurons）表明，编辑 FFN 中特定神经元可以改变模型对某个事实的输出（如"巴黎是法国首都"），而 Attention 主要决定"在哪找信息"。

## 自测

1. 手推一遍 4 个 token、d_k=64 的 Self-Attention 全流程，说明 √d_k 缩放的作用。
2. 因果掩码和普通掩码的区别是什么？为什么 Decoder-only 必须有它？
3. 对比 RoPE 和正弦位置编码：为什么现代 LLM 选择 RoPE？
4. 用速算公式估算一个 24 层、d_model=2048、FFN 维度 8192、词表 5 万的模型参数量。
5. 解释"Attention 负责路由、FFN 负责存储"这句话。

## 参考与官方链接

- [Attention Is All You Need](https://arxiv.org/abs/1706.03762)
- [The Illustrated Transformer（图解经典）](https://jalammar.github.io/illustrated-transformer/)
- [RoPE 论文：RoFormer](https://arxiv.org/abs/2104.09864)
- [FlashAttention](https://arxiv.org/abs/2205.14135)
- [LLaMA 论文](https://arxiv.org/abs/2302.13971)
