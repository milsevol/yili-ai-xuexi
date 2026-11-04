# 05 对齐技术SFT与RLHF

## 一句话

**对齐（Alignment）是把「会续写的 Base 模型」变成「听话、安全、符合人类偏好」的助手**。三段式：SFT 教它「照着指令答」，RM 教它「什么是好答案」，RLHF/DPO 让它「主动偏向好答案」。其中 SFT 是必做项，RLHF 与 DPO 是二选一的进阶项。

## 对齐全景

```
Base 模型（会续写，不会听指令）
   │
   │ ① SFT（Supervised Fine-Tuning）
   │    数据：指令 + 高质量回答（几万~几十万条）
   ▼
SFT 模型（会听指令，但可能啰嗦/不安全/不诚实）
   │
   │ ② 偏好对齐（二选一）
   ├─ RLHF：训练奖励模型 RM → PPO 优化策略
   └─ DPO：跳过 RM，直接用偏好对做偏好优化
   ▼
对齐后的对话模型
```

## SFT：指令微调

### 数据长什么样

SFT 的核心是**把任务写成对话格式**，并让 loss 只算答案部分：

```json
{
  "messages": [
    {"role": "system", "content": "你是严谨的投研助手，只基于给定资料回答。"},
    {"role": "user", "content": "2024 年该公司毛利率是多少？"},
    {"role": "assistant", "content": "根据 2024 年报，毛利率为 42.3%，同比提升 1.8 个百分点。"}
  ]
}
```

```python
# 关键的 loss mask：只对 assistant 部分计算损失
def build_labels(tokenizer, messages):
    prompt_ids = tokenizer.apply_chat_template(
        messages[:-1], add_generation_prompt=True, return_tensors="pt"
    )
    full_ids = tokenizer.apply_chat_template(
        messages, return_tensors="pt"
    )
    labels = full_ids.clone()
    labels[:, : prompt_ids.shape[1]] = -100   # 问题和 system 不算损失
    return full_ids, labels
```

> 如果不做 mask，模型会把「学习如何提问」也当目标，指令跟随能力明显变差。

### SFT 数据工程要点

| 要点 | 做法 | 反例 |
| --- | --- | --- |
| 数量 | 1k~50k 条高质量 > 100 万条噪声 | 爬来的低质问答直接混入 |
| 多样性 | 覆盖真实任务类型与说法 | 全是同一模板生成的样本 |
| 长度分布 | 匹配线上真实长度 | 全是超短答案，线上问长文就崩 |
| 去重 | 语义去重（embedding 聚类） | 同一题重复 500 次导致过拟合 |
| 拒答样本 | 显式教「不知道就说不知道」 | 从不给「无法回答」的样例 |

### 常用超参

| 参数 | 典型值 | 说明 |
| --- | --- | --- |
| learning rate | 1e-5 ~ 2e-5（全参）/ 1e-4 ~ 2e-4（LoRA） | 过大易破坏原能力 |
| epoch | 2 ~ 3 | 超过 3 轮常开始过拟合 |
| batch size | 全局 32 ~ 128 | 用梯度累积凑 |
| warmup ratio | 0.03 ~ 0.1 | 防止初期震荡 |
| max length | 2048 ~ 8192 | 按业务最长样本定 |

## RLHF：三阶段

### ① 奖励模型（Reward Model, RM）

用人类偏好对（chosen / rejected）训练一个打分模型：

```
损失：-log σ( r(x, y_chosen) - r(x, y_rejected) )
```

RM 通常以 SFT 模型为底座，把输出头换成标量打分头。

### ② PPO 强化学习

```
策略模型（SFT 初始化）生成回答
   → RM 打分（奖励）
   → 同时用 KL 惩罚约束「别偏离 SFT 模型太远」
   → PPO 更新策略
```

KL 惩罚是必需品：没有它，模型会学会「讨好奖励模型」的退化输出（reward hacking）。

### ③ 迭代

用新策略重新采样 → 人工标注 → 更新 RM → 再训策略。这是 ChatGPT 早期的核心工作流。

| 阶段 | 成本 | 稳定性 | 效果上限 |
| --- | --- | --- | --- |
| SFT | 低 | 高 | 中 |
| RM + PPO | 很高（4 个模型同时驻显存） | 中（易崩） | 高 |

## DPO：跳过强化学习的偏好优化

DPO（Direct Preference Optimization）的关键洞察：**RLHF 的目标函数可以解析地重写成「在偏好对上做分类」**，于是不需要 RM、不需要 PPO、不需要采样循环。

```python
import torch.nn.functional as F

def dpo_loss(policy_chosen_logp, policy_rejected_logp,
             ref_chosen_logp, ref_rejected_logp, beta=0.1):
    """
    policy_*: 当前策略对 chosen/rejected 回答的 log 概率
    ref_*:    参考模型（SFT 模型，冻结）的同口径 log 概率
    beta:     偏离参考模型的强度，越小越保守
    """
    chosen_rewards = beta * (policy_chosen_logp - ref_chosen_logp)
    rejected_rewards = beta * (policy_rejected_logp - ref_rejected_logp)
    return -F.logsigmoid(chosen_rewards - rejected_rewards).mean()
```

| 维度 | RLHF (PPO) | DPO |
| --- | --- | --- |
| 需要的模型 | 策略 / 参考 / 奖励 / 价值 共 4 个 | 策略 / 参考 共 2 个 |
| 显存 | 极高 | 中（配合 LoRA 可单卡） |
| 实现复杂度 | 高（PPO 调参很挑） | 低（一个 loss 搞定） |
| 在线采样 | 需要 | 不需要（离线偏好对） |
| 效果 | 上限略高 | 实践中多数场景够用 |

**结论：资源有限优先 DPO；追求极限效果且有人力调 PPO 时用 RLHF。**

## 对齐税（Alignment Tax）

对齐不是免费的——它常带来副作用：

| 副作用 | 表现 | 缓解 |
| --- | --- | --- |
| 能力回退 | 数学/代码分数下降 | 混入预训练数据（replay）、降学习率 |
| 过度拒答 | 正常问题也被拒 | 拒答样本要「精准」，别一刀切 |
| 风格趋同 | 回答模板化、啰嗦 | 偏好数据里加入简洁样本 |
| 谄媚（sycophancy） | 用户说错也跟着错 | 偏好对中标注「坚持事实」 |

## 选型决策

```
有 1 万条以上高质量指令数据？
  ├─ 没有 → 先做数据，别急着训
  └─ 有 → SFT（LoRA 起步）
            ├─ 效果够用 → 结束
            └─ 还差「风格/偏好/安全性」→
                  ├─ 有偏好对（chosen/rejected）且算力有限 → DPO
                  └─ 有标注团队 + 多卡集群 → RLHF (PPO)
```

## FAQ

**Q：SFT 能不能直接解决「知识缺失」？**
A：不行。SFT 主要教「怎么说」，注入新事实容易遗忘且难更新。知识类需求用 RAG 或继续预训练（CPT）。

**Q：LoRA 做 SFT 效果会比全参差很多吗？**
A：多数任务差距在 1-3 个点以内，成本和迭代速度优势巨大。数据量大且任务分布差异大时才考虑全参。

**Q：DPO 一定比 SFT 好吗？**
A：不一定。偏好数据质量差时 DPO 会让模型学到噪声偏好；数据不足时先做 SFT 更稳。

**Q：为什么 DPO 需要参考模型？**
A：参考模型（通常是 SFT 模型）提供「原本的概率」，DPO 只优化相对提升量，避免模型为了刷偏好分而破坏语言能力——这就是隐式的 KL 约束。

**Q：对齐能保证模型不说错吗？**
A：不能。对齐优化的是「符合偏好」，不是「事实正确」。幻觉要靠 RAG、工具调用与验证链路解决。
