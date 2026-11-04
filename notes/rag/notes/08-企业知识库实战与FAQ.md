# 08 企业知识库实战与FAQ

## 一句话

**一个能上生产的企业知识库 RAG，代码量不大，难的是「数据管道 + 检索质量 + 权限 + 可观测」这四件工程事**。这一章给一套最小可用实现（纯 Python，不依赖框架），再补齐生产化清单与面试 FAQ。

## 最小可用 RAG（纯 Python 版）

### 完整链路

```
文档目录
  → 解析（PDF/Word/TXT）
  → 切块（500 字 + 80 字重叠）
  → Embedding（bge-m3 或 API）
  → 向量入库（内存/numpy 起步，生产换 Milvus）
  → 用户提问 → 向量检索 Top-20 → Rerank Top-5
  → Prompt 拼装（只允许基于上下文回答）
  → LLM 生成 → 带引用输出
```

### 核心代码骨架

```python
"""最小可用 RAG：约 120 行，跑通即可上线验证"""
import json
from pathlib import Path
import numpy as np

# ---------- 1. 切块 ----------
def chunk_text(text: str, size: int = 500, overlap: int = 80) -> list[str]:
    """按字符切块并保留重叠，避免关键句被切断"""
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap          # 回退 overlap 个字符形成重叠
    return chunks

# ---------- 2. 向量化（此处用可替换的接口） ----------
def embed(texts: list[str]) -> np.ndarray:
    """真实项目替换为：
       - 本地: sentence_transformers.SentenceTransformer('BAAI/bge-m3')
       - 云端: 调用 embedding API
       返回后务必 L2 归一化，使内积 == 余弦相似度"""
    rng = np.random.default_rng(0)                  # 演示用占位
    vecs = rng.normal(size=(len(texts), 64))
    return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)

# ---------- 3. 建索引 ----------
class VectorIndex:
    def __init__(self):
        self.vectors: np.ndarray | None = None
        self.documents: list[dict] = []

    def add(self, chunks: list[str], source: str):
        vecs = embed(chunks)
        self.vectors = vecs if self.vectors is None else np.vstack([self.vectors, vecs])
        self.documents += [{"text": c, "source": source, "chunk_id": i}
                           for i, c in enumerate(chunks)]

    def search(self, query: str, top_k: int = 20) -> list[dict]:
        q = embed([query])[0]
        scores = self.vectors @ q                       # 归一化后即余弦相似度
        idx = np.argsort(-scores)[:top_k]
        return [{**self.documents[i], "score": float(scores[i])} for i in idx]

# ---------- 4. 构建 Prompt ----------
SYSTEM = """你是企业知识库助手。规则：
1) 只能依据【参考资料】回答，不得使用外部知识；
2) 资料中没有的信息，直接回答「知识库中未找到相关内容」；
3) 每个结论后用 [编号] 标注来源。"""

def build_prompt(question: str, hits: list[dict]) -> str:
    context = "\n\n".join(
        f"[{i+1}] (来源: {h['source']}) {h['text']}" for i, h in enumerate(hits)
    )
    return f"{SYSTEM}\n\n【参考资料】\n{context}\n\n【问题】\n{question}"

# ---------- 5. 端到端 ----------
def answer(question: str, index: VectorIndex, llm_call) -> dict:
    hits = index.search(question, top_k=20)
    hits = hits[:5]                                  # 生产环境此处插入 Rerank
    prompt = build_prompt(question, hits)
    text = llm_call(prompt)
    return {"answer": text, "sources": [h["source"] for h in hits]}
```

> **要点**：真正的生产价值不在这 120 行，而在于把 `embed`、`llm_call`、检索后端替换成真实组件，并加上下面的生产化能力。

## 生产化清单

### 数据管道

| 事项 | 做法 |
| --- | --- |
| 增量索引 | 按文件 mtime / hash 判断变更，只重算变动文件 |
| 删除同步 | 源文件删除时同步删向量（否则会答已废止的制度） |
| 版本管理 | 文档保留版本号，检索时只取最新有效版本 |
| 解析质量 | PDF 优先用版面解析（保留表格结构），扫描件走 OCR |
| 元数据 | 写入部门、生效日期、密级，供过滤使用 |

### 检索与生成

| 事项 | 做法 |
| --- | --- |
| 混合检索 | 向量 + BM25，RRF 融合，专有名词场景收益明显 |
| Rerank | Top-20 → Cross-Encoder → Top-5 |
| 无答案兜底 | 相似度阈值 + Prompt 约束，禁止硬答 |
| 引用可溯源 | 输出带文档名与 chunk 定位，便于人工核对 |
| 缓存 | 相同问题缓存答案；相同文档前缀缓存 embedding |

### 权限与合规

```
用户请求 → 身份解析 → 权限过滤（在检索阶段做，不是事后过滤！）
```

**关键坑**：先检索再过滤会导致「无权文档已进入上下文」，既不安全也无法解释。正确做法是把权限条件下推到向量检索的标量过滤（`department in user.departments AND level <= user.level`）。

| 风险 | 措施 |
| --- | --- |
| 越权访问 | 检索阶段强制元数据过滤 |
| 敏感信息外泄 | 输出侧脱敏（身份证/手机号/账号） |
| 提示词注入（文档内含恶意指令） | 上下文与指令隔离、输出校验 |
| 审计 | 记录 question / contexts / answer / user |

### 可观测

| 指标 | 用途 |
| --- | --- |
| 检索命中率 / 平均相似度 | 判断知识库覆盖度 |
| 无答案率 | 过高说明知识缺口 |
| P95 延迟（检索/重排/生成分别统计） | 定位瓶颈 |
| 用户反馈（赞/踩 + 原因） | 最有效的 badcase 来源 |

## 典型上线节奏

```
第 1 周：跑通最小链路，50 条评估集，看 Faithfulness 与 Context Recall
第 2 周：加混合检索 + Rerank，对比指标提升
第 3 周：补权限过滤与引用展示，接入真实用户灰度
第 4 周：建反馈闭环，按 badcase 迭代切块与 Prompt
```

> 别一开始就追求 GraphRAG / Agentic RAG。**先把基础链路的指标做到 0.8 以上，再谈高级架构。**

## 面试 FAQ

**Q1：RAG 和微调该怎么选？**
A：知识类、时效类、需要引用溯源 → RAG；风格、格式、领域表达习惯、固定任务模式 → 微调。二者可叠加（微调学风格 + RAG 供知识）。

**Q2：Chunk 大小怎么定？**
A：从 300~500 字起，用评估集测。小块检索准但上下文碎，大块上下文全但噪声多；常见做法是「小块检索 + 父块扩展」。

**Q3：为什么加了 Rerank 效果提升明显？**
A：向量检索是 Bi-Encoder，压缩后丢失细粒度交互；Cross-Encoder 把 query 与文档拼一起过模型，能捕捉词级匹配与否定关系。

**Q4：检索结果相关但答案还是错，怎么排查？**
A：先看 Prompt 是否约束「只依据上下文」；再看上下文是否被截断（关键句在中间被 lost in the middle）；最后检查是否有多版本冲突文档同时被召回。

**Q5：怎么处理表格与图片？**
A：表格转 Markdown/HTML 保留结构后切块；图片走 OCR 或 VLM 生成描述再入库。纯文本切块会破坏表头与数据的对应关系。

**Q6：如何评估检索质量？**
A：用 Context Recall（标准答案的信息是否被召回）与 Context Precision（有用片段是否靠前）。需要人工标注的标准答案。

**Q7：知识库更新后如何保证不答旧内容？**
A：文档带版本与生效日期，检索时按日期过滤只取生效版本；源文档删除时同步删除向量。

**Q8：用户问「你们产品和竞品比怎么样」，RAG 会怎样？**
A：这是主观/对比类问题，知识库通常没有直接答案。应识别为「非检索型问题」，走预设话术或转人工，而不是强行拼凑片段。

**Q9：多轮对话里 RAG 怎么处理指代？**
A：把对话历史做查询改写（把「它的价格」补全为「XX 产品的价格」），再检索；或把最近 2~3 轮作为检索上下文。

**Q10：RAG 系统的延迟主要在哪儿？**
A：通常是 LLM 生成的 decode 阶段与 Rerank。优化手段：减少 Top-K、流式输出、Rerank 批量化、缓存、用小模型做改写。

**Q11：怎么防止 RAG 被提示词注入？**
A：把检索内容视为不可信输入：与系统指令用明确分隔符隔离、禁止上下文中出现的指令生效、输出侧规则校验、敏感操作强制人工确认。

**Q12：为什么同样的系统，换个 Embedding 模型效果差很多？**
A：Embedding 决定了语义空间的分布。领域不匹配（如医疗/法律术语）时，通用模型召回会明显下降；需要领域微调或选领域适配模型。

## 学完本主题之后

```
RAG ✅
   ├─→ Agent 智能体：把检索当工具，自主决定何时查
   ├─→ 向量数据库：更深的索引与调优
   ├─→ 提示词工程：更强的 Prompt 约束与结构化输出
   └─→ 大数据主题：离线数据清洗与索引构建管道
```
