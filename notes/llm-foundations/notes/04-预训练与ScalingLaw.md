# 04 预训练与ScalingLaw

## 一句话

**预训练是「用海量文本做下一个词预测」这件极简的事，但规模和工程决定了模型上限**。Scaling Law 告诉我们：参数量 N、数据量 D、算力 C 之间存在可预测的幂律关系，所以「加多少参数、喂多少 token、花多少钱」不再靠拍脑袋，而是可以先算再训。

## 预训练目标

### CLM（Causal Language Modeling，因果语言建模）

GPT / LLaMA / Qwen 全系用的目标。给定前文，预测下一个 token：

```
输入：  <BOS> 今 天 天 气 真
标签：        今 天 天 气 真 好
```

损失函数是逐位置的交叉熵：

```python
import torch
import torch.nn.functional as F

def clm_loss(logits, labels):
    """
    logits: [B, L, V]  每个位置的词表分布
    labels: [B, L]     右移一位的真实 token（-100 表示不算损失）
    """
    return F.cross_entropy(
        logits.view(-1, logits.size(-1)),
        labels.view(-1),
        ignore_index=-100,
    )
```

关键细节：**因果掩码（causal mask）**保证位置 t 只能看到 ≤ t 的 token，否则模型会「抄答案」。

### MLM（Masked Language Modeling）

BERT 系用的目标：随机遮住 15% 的 token，让模型还原。

| 维度 | CLM（GPT 系） | MLM（BERT 系） |
| --- | --- | --- |
| 可见上下文 | 只看左侧 | 左右都看 |
| 擅长任务 | 生成、对话、推理 | 分类、抽取、检索向量 |
| 训练效率 | 每个 token 都能算损失 | 只有 15% 位置算损失 |
| 能否直接生成 | ✅ | ❌ |

> 现代 LLM 几乎清一色 CLM；MLM 主要活在 Embedding 模型（如 BGE）与分类模型里。

## 数据：比模型结构更决定成败

### 数据配比的大致经验

| 数据类型 | 典型占比 | 作用 |
| --- | --- | --- |
| 网页（CommonCrawl 清洗后） | 50-70% | 通用世界知识 |
| 代码（GitHub） | 10-20% | 提升推理与结构化能力 |
| 书籍 / 论文 | 5-15% | 长文本连贯性、深度知识 |
| 百科 / 问答 | 3-10% | 事实准确性 |
| 数学（合成/竞赛题） | 2-10% | 数值与多步推理 |

### 数据清洗流水线

```
原始网页
  → 语言识别（过滤非目标语言）
  → 去重（MinHash / SimHash 近似去重，重复数据会让模型「背诵」）
  → 质量过滤（困惑度过滤 / 分类器打分 / 规则剔除）
  → 隐私与有害内容过滤（PII 脱敏、黑名单）
  → 模板与导航栏剔除（boilerplate removal）
  → 分词打包（packing 成固定长度序列，减少 padding 浪费）
```

**工程经验**：清洗带来的效果提升，往往大于同等成本下换一个更花哨的模型结构。

## Scaling Law：把「加多少」变成可计算的

### 三条幂律（Chinchilla 结论）

给定算力预算 C（FLOPs），最优分配满足：

```
N_opt ∝ C^0.5     （参数量）
D_opt ∝ C^0.5     （训练 token 数）
且 D_opt ≈ 20 × N_opt
```

也就是说：**1B 参数模型，大约要喂 20B token 才算「训到位」**。

| 模型规模 | 建议训练 token | 训练算力（粗估） |
| --- | --- | --- |
| 1B | 20B | ~6×10^20 FLOPs |
| 7B | 140B | ~4×10^21 FLOPs |
| 70B | 1.4T | ~4×10^22 FLOPs |

> 算力估算公式：`C ≈ 6 × N × D`（N = 参数量，D = token 数）。前向 2ND、反向 4ND。

### 一条实用计算链

```python
def estimate_cost(params_b: float, tokens_b: float,
                  gpu_tflops: float = 400,      # A100 BF16 实测约 300-400 TFLOPS
                  gpu_hour_usd: float = 2.0,
                  mfu: float = 0.4):            # 模型算力利用率
    """粗估预训练算力与费用（单位：B = 十亿）"""
    n = params_b * 1e9
    d = tokens_b * 1e9
    total_flops = 6 * n * d
    gpu_seconds = total_flops / (gpu_tflops * 1e12 * mfu)
    gpu_hours = gpu_seconds / 3600
    return {
        "flops": f"{total_flops:.2e}",
        "gpu_hours": round(gpu_hours),
        "cost_usd": round(gpu_hours * gpu_hour_usd),
    }

print(estimate_cost(7, 140))    # 7B 模型 / 140B token
# {'flops': '5.88e+21', 'gpu_hours': 10208, 'cost_usd': 20417}
```

> 真实成本还要加上：试错重跑（×2~3）、数据管线、存储与网络、失败重启。**估算结果至少乘 3 再对外说。**

## Loss 曲线怎么读

| 现象 | 可能原因 | 处理 |
| --- | --- | --- |
| Loss 一开始就 NaN | 学习率过大 / 数据有脏 token | 降 warmup、加梯度裁剪、查数据 |
| Loss 平在某个值不动 | 学习率过小 / 数据重复度高 | 调 lr schedule、重新去重 |
| 训练 loss 降但验证 loss 升 | 过拟合（小模型 + 小数据常见） | 增数据、减 epoch、加 dropout |
| Loss 周期性尖刺 | 坏数据批次 / 长序列显存抖动 | 定位 batch、按长度分桶 |
| Loss 缓慢下降但陡降段缺失 | 学习率衰减过早 | 延长 warmup / 调整 cosine 周期 |

**判断训「到位」的实用标准**：验证集 loss 的下降速度明显变缓，继续训的边际收益低于数据/算力成本。

## 从预训练到可用模型

```
预训练（Base 模型）
   ↓ 会续写，但不会听指令
SFT 指令微调
   ↓ 会听指令，但不够符合人类偏好
RLHF / DPO 对齐
   ↓ 有用、无害、诚实
推理部署
```

Base 模型只是「读过很多书的哑巴」——下一章的 SFT 与 RLHF 才让它变成助手。

## 常见误区

| 误区 | 事实 |
| --- | --- |
| 参数越大越好 | 同等算力下，小模型 + 更多数据常常更优（Chinchilla） |
| 数据越多越好 | 低质重复数据的边际收益为负，清洗比堆量重要 |
| 训练 loss 越低越好 | 关心的是下游能力与验证集表现，不是训练集数字 |
| 可以从小规模外推一切 | Scaling Law 有拐点，能力涌现（emergence）不保证可预测 |
| 预训练能自学对齐 | Base 模型不会拒绝有害请求，对齐必须单独做 |

## FAQ

**Q：为什么现在的模型都训远超 20×N 的 token？**
A：Chinchilla 是「算力最优」，但推理成本也要算。小模型训更多数据，推理更便宜——所以出现了「过度训练」（over-training），例如 7B 模型喂 2T+ token。

**Q：预训练需要多少数据才够？**
A：高质量去重后，中文可用数据远少于英文。这也是为什么很多中文模型要靠合成数据与翻译数据补充。

**Q：MoE 会改变 Scaling Law 吗？**
A：会改变「激活参数量 vs 总参数量」的关系。MoE 用更大的总参数换更低的单次推理激活量，但显存占用仍按总参数算。

**Q：怎么判断预训练是否值得自己从头做？**
A：几乎不需要。绝大多数场景应该「拿开源 Base 模型 + 继续预训练（CPT）」，而不是从零训练。
