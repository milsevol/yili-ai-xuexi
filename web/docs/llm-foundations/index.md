# Transformer 与大模型原理

大模型的全部魔法，几乎都收束在一个结构里：**Transformer**。本主题从 Attention 的矩阵运算讲起，一路串到 Tokenizer、预训练、Scaling Law、对齐（SFT/RLHF/DPO）、开源模型选型与推理采样。目标不是背公式，而是能回答「这个模型为什么这样训练、为什么这么贵、为什么这样输出」。本主题用中文笔记 + **浏览器可视化交互演示**，把抽象机制变成可点、可调、可看的图。

> 版本参考：以 2024–2026 年主流开源模型（LLaMA 3、Qwen 2.5/3、DeepSeek 系列）为准。演示不连接真实模型；默认打开 `demos/index.html`。

## 先决知识

- Python 基础（能读懂 numpy 矩阵运算）
- 线性代数直觉（向量、矩阵乘法、点积）
- 概率基础（条件概率、softmax）
- 不要求深度学习经验，但了解「神经网络 = 多层矩阵变换 + 非线性」会更快

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位) | `./start.sh 01` | LLM 能做什么/不能做什么、与传统 NLP 的范式差异 |
| 2 | [02-Transformer架构详解](./notes/02-Transformer架构详解) | `./start.sh 02` | Self-Attention、Q/K/V、位置编码、残差与 LayerNorm |
| 3 | [03-Tokenizer与BPE](./notes/03-Tokenizer与BPE) | `./start.sh 03` | BPE 合并流程、中文 token 化、词表大小权衡 |
| 4 | [04-预训练与ScalingLaw](./notes/04-预训练与ScalingLaw) | `./start.sh 04` | 预训练目标、数据配比、Scaling Law 与成本估算 |
| 5 | [05-对齐技术SFT与RLHF](./notes/05-对齐技术SFT与RLHF) | `./start.sh 05` | SFT、RLHF 三阶段、DPO 简化原理、对齐税 |
| 6 | [06-开源模型巡礼](./notes/06-开源模型巡礼) | `./start.sh 06` | LLaMA / Qwen / DeepSeek / GLM / Mistral 对比与选型 |
| 7 | [07-推理基础与采样](./notes/07-推理基础与采样) | `./start.sh 07` | 自回归生成、temperature/top-p/top-k、KV Cache |
| 8 | [08-多模态与FAQ](./notes/08-多模态与FAQ) | `./start.sh 08` | VLM 架构、语音与文生图简介、面试 FAQ |

## 与其他主题的关系

```
Transformer 原理（本主题） ← 一切 AI 应用的底座
   ├─→ 提示词工程：不改模型，只改输入
   ├─→ 微调技术：改模型参数（LoRA/DPO）
   ├─→ 向量库 + RAG：不改模型，补外部知识
   └─→ Agent：让模型自己决定调什么工具
```

## 如何启动演示

```bash
cd notes/llm-foundations
./start.sh          # 浏览器可视化交互
./start.sh 02       # 直达 Attention 权重演示
./start.sh --cli    # 备用终端文字版
```

也可：`python3 main.py llm-foundations` / `python3 main.py llm-foundations 02`。

## 参考与官方文档

- [Attention Is All You Need（Transformer 原始论文）](https://arxiv.org/abs/1706.03762)
- [Training Compute-Optimal LLMs（Chinchilla / Scaling Law）](https://arxiv.org/abs/2203.15556)
- [DPO 论文](https://arxiv.org/abs/2305.18290)
- [The Illustrated Transformer](https://jalammar.github.io/illustrated-transformer/)
