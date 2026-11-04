# 03 文档解析与Chunking

## 一句话

**垃圾进垃圾出——解析和切块是 RAG 质量的第一道生死关**：解析阶段把 PDF/Word/网页变成干净的结构化文本，切块阶段把长文本切成语义完整的 Chunk。生产环境中 **80% 的 RAG 质量问题都能追溯到这一章**，而不是模型不够强。

## 文档解析的坑（按格式分）

### PDF——深水区

| 坑 | 现象 | 对策 |
| --- | --- | --- |
| 多栏排版 | 左右栏文字交错混成一行 | 用带版面分析的解析器（MinerU / GROBID / 商业 API） |
| 扫描件 | 提取出来是空文本（本质是图片） | OCR 兜底（PaddleOCR / Tesseract） |
| 表格 | 被打散成一行行碎片文字 | 表格检测 + 转 Markdown 表格；或转 HTML |
| 页眉页脚 | 每页重复的公司名/页码混入正文 | 按位置/正则规则过滤 |
| 图片中的关键信息 | 流程图、架构图内容完全丢失 | 多模态模型生成图片描述（caption）入库 |

```python
# PyMuPDF 基础解析 + 页眉页脚过滤示例
import fitz  # pymupdf

def parse_pdf(path: str) -> str:
    doc = fitz.open(path)
    pages = []
    for page in doc:
        blocks = page.get_text("blocks")
        lines = []
        for b in blocks:
            x0, y0, x1, y1, text = b[0], b[1], b[2], b[3], b[4]
            # 过滤页面顶部 50px / 底部 50px 区域（页眉页脚高发区）
            if y0 < 50 or y1 > page.rect.height - 50:
                continue
            lines.append(text.strip())
        pages.append("\n".join(lines))
    return "\n\n".join(pages)
```

### Word / HTML / Markdown

- **Word（.docx）**：python-docx 提取段落和表格；注意「样式即语义」——标题层级要保留，它是切块的最佳边界
- **HTML**：先转正文（trafilatura / readability 去导航栏广告），再保留 h1-h3 层级；`<table>` 转 Markdown
- **Markdown**：天然友好，按 `#` 标题层级切块即可

**核心原则：保留结构信息。** 标题层级、列表、表格边界是后面语义切块的命脉，解析成一锅纯文本粥就全完了。

## 切块策略对比

### 1. 固定大小切块（Fixed-size）

按固定字符/token 数硬切，最简单也最粗暴：

```python
def fixed_chunk(text: str, size: int = 512, overlap: int = 64) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size - overlap)]
```

- 优点：实现零成本、块大小均匀
- 缺点：**拦腰切断句子和表格**，语义完整性看运气

### 2. 递归切块（Recursive，生产最常用）

按分隔符优先级递归切：`\n\n`（段落）→ `\n`（行）→ `。！？`（句）→ 硬切。LangChain 的 `RecursiveCharacterTextSplitter` 就是这个思路：

```python
def recursive_chunk(text: str, size: int = 512, overlap: int = 64) -> list[str]:
    separators = ["\n\n", "\n", "。", "！", "？", "；", " "]
    def split(t: str, seps: list[str]) -> list[str]:
        if len(t) <= size:
            return [t]
        if not seps:                        # 分隔符用完，硬切
            return [t[i:i + size] for i in range(0, len(t), size)]
        sep = seps[0]
        parts, buf = [], ""
        for seg in t.split(sep):
            candidate = buf + sep + seg if buf else seg
            if len(candidate) <= size:
                buf = candidate
            else:
                if buf:
                    parts.append(buf)
                buf = seg if len(seg) <= size else ""
                if len(seg) > size:         # 单段仍超长 → 用下一级分隔符递归
                    parts.extend(split(seg, seps[1:]))
        if buf:
            parts.append(buf)
        return parts
    chunks = split(text, separators)
    # 加重叠窗口：每块尾部拼接下一块的开头
    return [c + chunks[i + 1][:overlap] if i + 1 < len(chunks) else c
            for i, c in enumerate(chunks)]
```

### 3. 语义切块（Semantic）

先按句子 Embedding，相邻句子相似度骤降处切分（话题边界）：

- 优点：块内话题高度一致，检索精度最好
- 缺点：每篇文档要跑 N 次 Embedding，**成本高一档**；块大小不均匀
- 适用：高价值、低频更新的精品知识库

### 4. 结构化切块（按标题层级）

按 Markdown/Word 的标题树切，每个小节一个块，标题作为元数据注入每个块：

```python
# 切块时带上面包屑标题，检索时上下文更完整
chunk = "【员工手册 > 考勤管理 > 年假规定】\n正式员工每年享有 15 天年假……"
```

**这个技巧便宜且效果显著**——块脱离了上下文（"第十五条：……"）时，面包屑标题能让检索模型和 LLM 都知道它属于哪一章。

### 策略对比表

| 策略 | 语义完整性 | 成本 | 块大小均匀 | 适用 |
| --- | --- | --- | --- | --- |
| 固定大小 | 差 | 极低 | 均匀 | 快速原型 |
| 递归切块 | 较好 | 低 | 较均匀 | **生产默认选择** |
| 语义切块 | 最好 | 高 | 不均 | 精品库、高价值文档 |
| 结构化切块 | 好（依赖解析质量） | 低 | 不均 | 有标题层级的文档 |

## Chunk 大小的权衡

| 块大小 | 检索精度 | 上下文完整性 | 适用场景 |
| --- | --- | --- | --- |
| 128 token | 高（向量聚焦单一语义） | 差（可能缺前因后果） | FAQ 问答对、精确事实查询 |
| 512 token | 中 | 中 | **通用默认值**，多数场景从这里起步 |
| 1024 token | 低（向量被多个话题稀释） | 好 | 需要大段上下文的复杂推理 |

**权衡的本质**：块越小，向量语义越聚焦，检索越准；但块越小，单个块承载的上下文越少，LLM 拿到的信息越残缺。两者此消彼长。

**工程实践**：
- 从 512 token + 50~80 token 重叠起步，用评估集调（第 06 章）
- **小块检索、大块生成**（Small-to-Big）：索引用 128 token 小块提高命中，命中后把它所属的父段落/整节喂给 LLM——LlamaIndex 的 `SentenceWindowRetriever`、Parent-Document 模式都是这个思想

## 重叠窗口（Overlap）

```
块1: [..............................]
块2:                     [..............................]
块3:                                          [..............................]
                        ↑ 重叠 64 token ↑
```

- 作用：防止答案正好横跨两个块的边界时被切断
- 推荐值：块大小的 **10%~15%**（512 块配 50~80 重叠）
- 代价：索引体积增大重叠比例，可忽略
- 注意：重叠不是万能的，表格被切断时重叠救不回来——表格要整体保护

## 表格与图片的处理

### 表格（重灾区）

**绝对不要把表格当普通文本按字符切。** 推荐三种方案：

1. **整表转 Markdown 成一个块**（表不超过块大小限制时首选）：

```markdown
| 年假档位 | 工龄 | 天数 |
| --- | --- | --- |
| 一档 | 1-5 年 | 10 天 |
| 二档 | 5-10 年 | 15 天 |
```

2. **大表按行组切块 + 每块重复表头**：

```python
def chunk_large_table(headers: list[str], rows: list[list[str]], max_rows: int = 20):
    for i in range(0, len(rows), max_rows):
        block_rows = rows[i:i + max_rows]
        yield to_markdown_table(headers, block_rows)  # 每块都带表头
```

3. **表格生成文字摘要**：用 LLM 给每个表生成 2-3 句摘要，摘要向量化参与检索，命中后返回完整表格。

### 图片

- 图片里的文字信息：OCR 提取后并入正文
- 流程图/架构图：多模态模型（Qwen-VL / GPT-4o）生成描述文本入库，原文保留图片 URL 作为元数据
- 生成答案时可以把命中的图片 URL 一并返回前端展示

## 实战检查清单

```
□ 抽样 20 篇解析结果人工 review：文字顺序对吗？表格完整吗？
□ 扫描件比例有多少？OCR 管线接入了吗？
□ 切块后抽样检查：有没有句子被拦腰切断？表格是否整体保留？
□ 每个 Chunk 是否带元数据（来源文档、标题路径、页码、权限标签）？
□ 建了 badcase 反馈机制吗（答错的问题回溯到具体 Chunk）？
```

## 常见问题

**Q：Chunk 越大检索效果越差吗？**
A：不是单调关系。块太大，一个向量要表达多个话题，语义被稀释；块太小，语义不完整。512 token 是经验甜区，但最终要以你的评估集实测为准（第 06 章）。

**Q：语义切块明显更好，为什么不普及？**
A：成本。每个句子都要 Embedding，一篇 10 万字文档要跑几千次推理。而且递归切块 + 面包屑标题已经能拿到 80% 的收益，性价比更高。

**Q：PDF 解析哪个工具最好？**
A：没有银弹。纯文字 PDF 用 PyMuPDF 足够；学术论文多栏用 GROBID/MinerU；扫描件走 OCR；商业文档可以考虑付费解析 API（如 LlamaParse、Azure Document Intelligence）。**关键是建一套解析质量的抽样 review 流程**，而不是指望某个工具通吃。

**Q：切块时 overlap 设多大？**
A：块大小的 10%~15%。太小了保不住跨边界的句子，太大了索引冗余且相邻块向量过于相似（浪费召回名额）。

## 自测

1. 为什么说「解析切块是 RAG 质量的第一道关」？
2. 递归切块的分隔符优先级是什么？它比固定切块好在哪？
3. 128/512/1024 三种块大小各自的检索精度和上下文完整性如何权衡？什么是 Small-to-Big 模式？
4. 一个 50 行的超大表格入库，你会怎么处理？说出至少两种方案。

## 参考与官方链接

- [LangChain Text Splitters 文档](https://python.langchain.com/docs/concepts/text_splitters/)
- [LlamaIndex Node Parser / Chunking](https://docs.llamaindex.ai/en/stable/module_guides/loading/node_parsers/)
- [MinerU（高质量 PDF 解析）](https://github.com/opendatalab/MinerU)
- [PyMuPDF 文档](https://pymupdf.readthedocs.io/)
- [Semantic Chunking 实践（Greg Kamradt）](https://github.com/FullStackRetrieval-com/RetrievalTutorials)
