# 提示词工程

提示词工程是**不训练模型、只改输入**就能显著提升效果的那一层能力。它便宜、见效快，但边界也很清楚：Prompt 解决不了知识缺失（要 RAG）、解决不了能力不足（要微调）、也解决不了不稳定的输出格式（要结构化约束 + 校验）。本主题用中文笔记 + **浏览器可视化交互演示**，把「怎么写得准、怎么迭代得快、怎么防注入」讲成可操作的方法。

> 版本参考：以 GPT-4o / Claude / Qwen / DeepSeek 等主流对话模型的通用行为为准。演示不发起真实 API 调用；默认打开 `demos/index.html`。

## 先决知识

- 会用至少一个大模型对话产品（能理解上下文长度、温度等基本概念）
- Python 基础（能读懂 API 调用示例伪代码）
- 了解 JSON 结构（结构化输出章节需要）

## 学习路径

| 顺序 | 笔记 | 交互演示 | 内容 |
| --- | --- | --- | --- |
| 1 | [01-概述与定位](./notes/01-概述与定位) | `./start.sh 01` | Prompt Engineering 的能力边界、与微调/RAG 的分工 |
| 2 | [02-Prompt结构与Few-shot](./notes/02-Prompt结构与Few-shot) | `./start.sh 02` | 四要素结构、Zero-shot vs Few-shot、示例选择 |
| 3 | [03-思维链CoT与推理增强](./notes/03-思维链CoT与推理增强) | `./start.sh 03` | CoT、Self-Consistency、Tree-of-Thought、失效场景 |
| 4 | [04-结构化输出与FunctionCalling](./notes/04-结构化输出与FunctionCalling) | `./start.sh 04` | JSON 约束、Schema 设计、工具调用流程与校验 |
| 5 | [05-评估迭代与安全防护](./notes/05-评估迭代与安全防护) | `./start.sh 05` | 评估方法、A/B 迭代、Prompt 注入与防护 |
| 6 | [06-实战模板与FAQ](./notes/06-实战模板与FAQ) | `./start.sh 06` | 摘要/分类/抽取/翻译/客服模板盒 + 面试 FAQ |

## 与其他主题的关系

```
提示词工程（本主题） ← 最轻量的落地手段
   ├─ 上游：Transformer 原理（理解为什么会「不听话」）
   ├─ 下游：RAG（把知识塞进上下文）
   ├─ 下游：Agent（把工具调用写成结构化指令）
   └─ 替代方案：微调技术（当 Prompt 到极限时）
```

## 如何启动演示

```bash
cd notes/prompt-engineering
./start.sh          # 浏览器可视化交互
./start.sh 03       # 直达 CoT 对比演示
./start.sh --cli    # 备用终端文字版
```

也可：`python3 main.py prompt-engineering` / `python3 main.py prompt-engineering 03`。

## 参考与官方文档

- [OpenAI Prompt Engineering Guide](https://platform.openai.com/docs/guides/prompt-engineering)
- [Chain-of-Thought 论文](https://arxiv.org/abs/2201.11903)
- [Prompt Injection 综述](https://arxiv.org/abs/2302.12173)
- [Anthropic Prompt Engineering 文档](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview)
