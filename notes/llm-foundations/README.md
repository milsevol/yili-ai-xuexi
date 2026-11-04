# llm-foundations · Transformer 与大模型原理

个人学习知识库的 AI 主题笔记：从 Attention 到预训练、对齐、推理采样的完整原理链路。

## 章节

| 章节 | 内容 |
| --- | --- |
| 01 概述与定位 | LLM 能做什么/不能做什么、与传统 NLP 的范式差异 |
| 02 Transformer 架构详解 | Self-Attention、Q/K/V、多头、位置编码、Pre-LN |
| 03 Tokenizer 与 BPE | BPE 合并流程、中文 token 化、词表大小权衡 |
| 04 预训练与 Scaling Law | CLM/MLM、数据清洗、Chinchilla、成本估算、loss 解读 |
| 05 对齐技术 SFT 与 RLHF | SFT loss mask、RM、PPO、DPO、对齐税 |
| 06 开源模型巡礼 | LLaMA/Qwen/DeepSeek/GLM/Mistral 对比与选型四道闸 |
| 07 推理基础与采样 | 自回归、temperature/top-p、KV Cache 与显存 |
| 08 多模态与 FAQ | VLM 三段式、Whisper、文生图、12 个面试问答 |

## 启动演示

```bash
./start.sh          # 浏览器可视化交互
./start.sh 02       # 直达 Attention 权重演示
./start.sh --cli    # 终端摘要版
```

也可在仓库根目录：`python3 main.py llm-foundations`。
