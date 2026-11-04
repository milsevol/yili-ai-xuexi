# 06 RAG评估RAGAS

## 一句话

**RAG 的坑在于「答错了你也不知道是哪一环错了」**：是没检索到（召回问题）、还是检索到了但没用上（生成问题）？RAGAS 用「忠实度 / 答案相关性 / 上下文召回」这几个可自动计算的指标，把链路拆开打分，让优化有的放矢。

## 为什么必须评估

没有评估的 RAG 优化 = 盲调。常见症状与真实原因：

| 症状 | 你以为的原因 | 真正的原因 |
| --- | --- | --- |
| 答非所问 | 模型不行 | 检索没召回正确片段 |
| 答案有一半是编的 | 模型幻觉 | 召回的片段本身不含答案 |
| 片段对但答案错 | 模型理解差 | Prompt 没约束「只基于上下文」 |
| 有时对有时错 | 模型不稳定 | 切块把关键句切断了 |

**结论：必须分别评估「检索」与「生成」。**

## RAG 评估的三类指标

```
        ┌─ 检索质量 ── Context Recall / Context Precision
RAG 评估 ┼─ 生成质量 ── Faithfulness / Answer Relevancy
        └─ 端到端 ──── Answer Correctness / 人工评分
```

### 指标定义

| 指标 | 问的问题 | 计算方式（LLM 判定） |
| --- | --- | --- |
| **Context Recall** | 标准答案需要的信息，检索到了吗？ | 把标准答案拆成陈述句，逐句判断能否被召回上下文支持 |
| **Context Precision** | 召回的内容里，有用的排在前面吗？ | 逐条判断相关性，算加权平均精度 |
| **Faithfulness** | 答案里的每句话，上下文支持吗？ | 把答案拆成陈述句，逐句核对是否有上下文依据 |
| **Answer Relevancy** | 答案正面回答了问题吗？ | 由答案反推「可能的问题」，与原问题算相似度 |
| **Answer Correctness** | 和标准答案一致吗？ | 语义相似度 + 事实重合度 |

> 前两个评「检索器」，中间两个评「生成器」。优化时先看 Context Recall——**召回不到，后面全废**。

## 用 RAGAS 跑一次评估

```python
# pip install ragas datasets
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    context_recall, context_precision,
    faithfulness, answer_relevancy,
)

# 每个样本必须有这四列
data = {
    "question": ["年假有多少天？", "报销流程是什么？"],
    "answer": ["正式员工每年 15 天年假。", "提交发票后在系统内发起报销单。"],
    "contexts": [
        ["正式员工每年享有 15 天带薪年假，入职满一年可申请。"],
        ["报销需在系统中提交报销单并附发票，审批后 5 个工作日到账。"],
    ],
    "ground_truth": ["15 天。", "系统提交报销单 + 发票附件，审批后到账。"],
}

result = evaluate(
    Dataset.from_dict(data),
    metrics=[context_recall, context_precision, faithfulness, answer_relevancy],
)
print(result)
# {'context_recall': 0.92, 'context_precision': 0.85,
#  'faithfulness': 0.96, 'answer_relevancy': 0.88}
```

### 指标偏低时的排查顺序

```
Context Recall 低
   → 切块太大/太小？Embedding 模型不适配？Top-K 太小？查询改写缺失？
Context Precision 低
   → 需要 Rerank；或 Top-K 太大引入噪声
Faithfulness 低
   → Prompt 未约束「只依据上下文」；上下文太长导致忽略中间内容
Answer Relevancy 低
   → 答案跑题；问题表述歧义；Prompt 未明确输出要求
```

## 构建自己的评估集

自动指标只能做相对比较，**必须有 50~200 条人工标注的业务样本**作为金标准。

```python
# 评估集的一条样本
{
    "question": "用户在什么情况下可以申请退款？",
    "ground_truth": "购买后 7 天内且商品未拆封可申请退款。",
    "contexts": [...],          # 由 RAG 实际召回的片段（评估检索用）
    "answer": "...",            # 由 RAG 实际生成的答案（评估生成用）
    "difficulty": "medium",     # 可选：分层统计
    "type": "policy",           # 可选：按问题类型分组
}
```

### 评估集怎么采样

| 来源 | 比例建议 | 说明 |
| --- | --- | --- |
| 真实用户问题 | 60% | 最有价值，来自日志 |
| 业务方指定关键问题 | 20% | 覆盖核心场景与红线问题 |
| 边界/对抗问题 | 15% | 多跳、歧义、超纲（应拒答） |
| 简单事实题 | 5% | 作为基线 sanity check |

## 持续回归

```python
# 把评估做成 CI 门禁（伪代码）
def regression_gate(new_scores, baseline, tolerance=0.03):
    regressions = []
    for metric, base in baseline.items():
        if new_scores[metric] < base - tolerance:
            regressions.append(f"{metric}: {base:.2f} -> {new_scores[metric]:.2f}")
    if regressions:
        raise SystemExit("评估回退，禁止发布:\n" + "\n".join(regressions))
```

**规则**：任何切块策略、Embedding 模型、Prompt、Rerank 的改动，都必须先跑评估集，再上线。

## badcase 分析流程

```
1. 抽样失败样本（Faithfulness < 0.6 或人工判错）
2. 分三类打标：
   ├─ 检索失败（正确片段不在 contexts 里）
   ├─ 生成失败（片段在，答案没用上/答错）
   └─ 数据缺失（知识库里根本没有这个知识）
3. 按类别统计占比 → 定位投入产出最高的优化点
4. 把典型 badcase 加入评估集，防止回归
```

> 实践经验：**多数 RAG 效果问题的 70% 出在检索侧**，而不是模型不够强。

## 常见误区

| 误区 | 事实 |
| --- | --- |
| 只看答案对不对 | 端到端对不代表链路健康，换一批问题就崩 |
| 用 LLM 打分就万事大吉 | LLM 评判有偏好（偏爱长答案、偏爱同模型风格） |
| 指标 0.9 就够了 | 指标要结合业务容忍度，金融/医疗场景要求更高 |
| 一次评估管半年 | 知识库在变、用户问题在变，评估集必须持续扩充 |

## FAQ

**Q：没有标准答案怎么做评估？**
A：先人工标 50 条作为种子；也可用「LLM 生成 + 人工校正」。无标准答案时至少评 Faithfulness（有没有编）。

**Q：RAGAS 的 LLM 评判成本高吗？**
A：每条样本要多次 LLM 调用。建议评估集控制在 100-300 条，且用便宜模型评判、抽样人工复核。

**Q：Context Recall 和 Context Precision 哪个优先？**
A：先保 Recall。召回不到，精排再好也没用；Recall 达标后再用 Rerank 提 Precision。

**Q：为什么 Faithfulness 高但人工觉得答得不好？**
A：Faithfulness 只衡量「有没有依据」，不衡量「是否完整、是否有用」。需要配合 Answer Correctness / 人工评分。

**Q：小团队怎么低成本评估？**
A：50 条业务样本 + Faithfulness/Context Recall 两个指标 + 人工抽检 10 条，就足以发现 80% 的问题。
