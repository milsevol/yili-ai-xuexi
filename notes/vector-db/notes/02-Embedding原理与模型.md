# 02 Embedding 原理与模型

## 一句话

**Embedding 是把离散符号（词/句/图）映射成连续稠密向量的技术**：语义相近的对象在向量空间中距离也相近。从 Word2Vec（词级、静态）到 BERT（上下文相关）再到现代对比学习模型（bge / text-embedding-3），核心目标只有一个——**让「距离」等于「语义相似度」**。

## 为什么需要 Embedding

计算机不懂「猫」和「 kitten 」相近，只认字节。one-hot 编码维度爆炸且任意两词正交（距离相同），无法表达语义。Embedding 把词压进低维稠密空间（如 768 维），让语义可计算：

```python
# 理想中的向量空间性质
vec("国王") - vec("男人") + vec("女人") ≈ vec("女王")
cosine(vec("退货"), vec("退款")) ≈ 0.9   # 近义
cosine(vec("退货"), vec("天气")) ≈ 0.05  # 无关
```

## 演进路线：Word2Vec → BERT → 现代 Embedding

### 1. Word2Vec（2013，词级静态）

两种训练目标：
- **CBOW**：用上下文词预测中心词
- **Skip-gram**：用中心词预测上下文词（常用）

```python
# gensim 训练 Word2Vec（示例）
from gensim.models import Word2Vec
sentences = [["我", "喜欢", "机器", "学习"], ["深度", "学习", "很", "有趣"]]
model = Word2Vec(sentences, vector_size=100, window=3, min_count=1, sg=1)
print(model.wv.most_similar("学习", topn=3))
```

**局限**：一词一向量，「苹果」（水果/公司）无法区分；无法处理未登录词。

### 2. BERT（2018，上下文相关）

Transformer 双向编码：同一个词在不同句子里得到**不同向量**。

```python
from transformers import AutoTokenizer, AutoModel
import torch

tok = AutoTokenizer.from_pretrained("bert-base-chinese")
model = AutoModel.from_pretrained("bert-base-chinese")
inputs = tok("苹果手机发布了", return_tensors="pt")
with torch.no_grad():
    out = model(**inputs)
# 取 [CLS] 或 mean pooling 作为句向量
sent_vec = out.last_hidden_state.mean(dim=1)  # (1, 768)
```

**注意**：裸 BERT 的句向量直接拿来算相似度效果差（各向异性问题，向量挤在窄锥里）。做检索要用**专门微调过的 Embedding 模型**。

### 3. 现代 Embedding 模型（对比学习微调）

在 BERT 类底座上用**对比学习（Contrastive Learning）**微调：拉近正样本对（query, 相关文档），推远负样本对。代表损失函数 InfoNCE：

```
L = -log( exp(sim(q,d⁺)/τ) / Σ exp(sim(q,dᵢ)/τ) )
```

训练数据来源：搜索点击日志、问答对、NLI 数据集、弱监督（标题-正文对）。

## 主流模型对比

| 模型 | 出品 | 维度 | 中文能力 | 最大长度 | 费用 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| **bge-large-zh-v1.5** | 智源 BAAI | 1024 | ★★★★★ | 512 | 免费开源 | 中文检索标杆，可自部署 |
| **bge-m3** | 智源 BAAI | 1024 | ★★★★★ | 8192 | 免费开源 | 多语言+长文+dense/sparse 混合 |
| **m3e-base** | Moka AI | 768 | ★★★★☆ | 512 | 免费开源 | 中文轻量，CPU 可跑 |
| **text-embedding-3-small** | OpenAI | 1536 | ★★★★☆ | 8191 | $0.02/百万 token | 云端 API，可降维 |
| **text-embedding-3-large** | OpenAI | 3072 | ★★★★☆ | 8191 | $0.13/百万 token | MTEB 高分 |
| **multilingual-e5-large** | Microsoft | 1024 | ★★★★☆ | 512 | 免费开源 | 多语言老牌 |
| **GTE-Qwen2** | 阿里 | 1536 | ★★★★★ | 8192 | 免费开源 | Qwen 底座，长文强 |

**选型建议**：
- 中文场景自部署首选 **bge-large-zh** 或 **bge-m3**
- 不想运维 GPU → **text-embedding-3-small**（性价比极高）
- 长文档（>512 token）→ bge-m3 / GTE-Qwen2

## 用 sentence-transformers 跑 bge-m3

```python
from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer("BAAI/bge-m3")  # 首次自动下载 ~2GB

docs = ["退货流程：7 天内可申请", "今日天气预报：晴", "退款将在 3 个工作日到账"]
embs = model.encode(docs, normalize_embeddings=True)  # (3, 1024)

q = model.encode(["怎么把钱退回来"], normalize_embeddings=True)
scores = embs @ q[0]          # 归一化后点积 = 余弦相似度
print(scores)                 # 第 1、3 条得分应明显高于第 2 条
```

**关键细节**：
- `normalize_embeddings=True`：归一化后点积 = 余弦，检索速度更快
- bge 系列官方建议给 query 加指令前缀（如「为这个句子生成表示以用于检索相关文章：」），v1.5 之后的模型对短 query 提升明显
- 批量 encode 比逐条快 10 倍以上（GPU 利用率）

## 维度与精度的权衡

| 选择 | 存储 | 检索速度 | 精度 | 说明 |
| --- | --- | --- | --- | --- |
| 高维（3072） | 12KB/条（float32） | 慢 | 高（边际收益递减） | OpenAI large |
| 标准（768/1024） | 3-4KB/条 | 中 | 足够 | 绝大多数场景 |
| 降维（256） | 1KB/条 | 快 | 略降（< 2%） | OpenAI 支持截断 |
| float32 | 4 字节/维 | 基准 | 基准 | 默认 |
| float16 | 2 字节/维 | 略快 | 几乎无损 | GPU 友好 |
| int8 量化 | 1 字节/维 | 快 2-4x | 降 1-3% | 配合 PQ 索引 |
| 二值化 | 1/32 字节 | 极快 | 降较多 | 仅粗筛，需重排 |

**经验法则**：
- 1 亿条 1024 维 float32 向量 ≈ **400GB** 原始存储——量化是刚需
- 先 float32 跑通精度基线，再评估量化带来的精度损失是否可接受（通常可接受）

## 评估 Embedding 质量的方法

```python
# 自建小评估集：query 与其相关文档的得分应显著高于无关文档
from sklearn.metrics.pairwise import cosine_similarity

pairs = [
    ("如何申请退款", "退款申请流程说明"),      # 相关
    ("如何申请退款", "服务器重启操作手册"),    # 无关
]
for q, d in pairs:
    s = cosine_similarity([model.encode(q)], [model.encode(d)])[0][0]
    print(f"{s:.3f}  {q}  ~  {d}")
```

公开榜单参考 **MTEB**（英文）和 **C-MTEB**（中文），但**永远用自己的业务数据验证**——榜单高不代表你的领域好。

## 常见坑

1. **中英文模型混用**：拿英文模型 embed 中文，效果断崖式下跌
2. **裸 BERT 直接检索**：没用对比学习微调，向量分布差，必须换专业 Embedding 模型
3. **忘记归一化**：用余弦距离建索引却传未归一化向量，结果全乱
4. **截断超长文本**：512 上限的模型喂 2000 字，后半部分被静默丢弃——先做文档切块（第 06 章）
5. **训练/推理模型版本不一致**：向量空间随模型变化，换模型必须全量重建索引

## 自测

1. Word2Vec 与 BERT 的 Embedding 有什么本质区别？
2. 为什么裸 BERT 的句向量不适合直接做相似度检索？解决思路是什么？
3. 1 亿条 1024 维 float32 向量占多少存储？int8 量化后呢？
4. 中文场景自部署，你会选哪个模型？为什么？

## 参考与官方链接

- [MTEB 榜单（Hugging Face）](https://huggingface.co/spaces/mteb/leaderboard)
- [BGE 系列模型](https://github.com/FlagOpen/FlagEmbedding)
- [sentence-transformers 文档](https://www.sbert.net/)
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)
- [Word2Vec 论文](https://arxiv.org/abs/1301.3781) / [BERT 论文](https://arxiv.org/abs/1810.04805)
