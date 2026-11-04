#!/usr/bin/env python3
"""Transformer 与大模型原理：默认打开可视化交互页；--cli 输出终端文字版摘要。"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT / "index.html"

CHAPTERS = [
    ("01", "概述与定位", "大模型是「基于上下文的概率生成器」，不是数据库也不是搜索引擎。擅长改写/摘要/抽取/对话；不擅长精确计算、实时私有知识、长链严格逻辑。三条边界决定了必须配 RAG、工具与校验。"),
    ("02", "Transformer 架构详解", "Self-Attention 让每个 token 按相关性加权聚合其他 token 的信息：Attention(Q,K,V)=softmax(QKᵀ/√d_k)V。多头并行捕捉不同关系模式；RoPE 用旋转编码相对位置；Pre-LN + 残差保证深层可训。"),
    ("03", "Tokenizer 与 BPE", "Tokenizer 把文本切成子词并映射为 id。BPE 从字节出发反复合并最高频相邻对，词表可控（3~15 万）且永不 OOV。中文常见单字与双字组合，token 化质量直接影响效果与成本。"),
    ("04", "预训练与 Scaling Law", "CLM（下一个词预测）是现代 LLM 的统一目标。Chinchilla 结论：D ≈ 20 × N，算力 C ≈ 6ND。数据清洗的收益常大于结构改进；loss 曲线的异常形态各有对应病因。"),
    ("05", "对齐技术 SFT 与 RLHF", "SFT 教「照着答」（只对答案算 loss），RM 学「哪个更好」，PPO 带 KL 惩罚优化策略。DPO 把 RL 目标改写成偏好分类损失，无需 RM 与在线采样，资源有限时的首选。"),
    ("06", "开源模型巡礼", "选型四道闸：许可（Apache/MIT 最宽松）→ 中文能力（Qwen/GLM/DeepSeek 更强）→ 显存（BF16 每 B 参数 2GB）→ 生态（vLLM/LLaMA-Factory 支持度）。榜单只做初筛，最终看自己的业务评估集。"),
    ("07", "推理基础与采样", "自回归：一次生成一个 token 再拼回输入。temperature 缩放 logits、top_p 做核采样、top-k 限候选数。KV Cache 让历史 K/V 复用，是推理加速核心，但显存随上下文线性增长。"),
    ("08", "多模态与 FAQ", "VLM 三段式：视觉编码器切 patch → 投影层对齐词嵌入空间 → 与文本 token 一起进 LLM。视觉 token 很贵（256~2048/图）。附 12 个高频面试问答。"),
]


def open_lab(chapter: str | None = None) -> None:
    if not LAB.is_file():
        print(f"找不到可视化演示页: {LAB}", file=sys.stderr)
        sys.exit(1)
    uri = LAB.resolve().as_uri()
    if chapter:
        code = chapter.strip().zfill(2) if chapter.strip().isdigit() else chapter.strip()
        uri = f"{uri}?c={code}"
    print("==> 打开 Transformer 与大模型原理 可视化交互演示（浏览器）")
    print(f"    {uri}")
    print("    推荐顺序：02（Attention）→ 03（BPE）→ 07（采样与 KV Cache）。")
    webbrowser.open(uri)


def print_chapter(code: str) -> None:
    code = code.strip().zfill(2) if code.isdigit() else code.strip()
    for num, title, summary in CHAPTERS:
        if code in (num, num.lstrip("0") or "0"):
            print(f"\n## {num} {title}\n\n{summary}\n")
            return
    print(f"未找到章节: {code}，可选: {[c[0] for c in CHAPTERS]}")
    sys.exit(1)


def cli_menu() -> None:
    print("Transformer 与大模型原理 · 终端摘要版\n")
    for num, title, _ in CHAPTERS:
        print(f"  {num}  {title}")
    choice = input("\n选择章节编号（q 退出）: ").strip().lower()
    if choice not in ("q", "quit", "exit", ""):
        print_chapter(choice)


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] in {"-h", "--help"}:
        print("用法:")
        print("  python3 demos/main.py           # 打开可视化交互页")
        print("  python3 demos/main.py 02        # 打开并定位到第 2 章")
        print("  python3 demos/main.py --cli     # 终端摘要菜单")
        print("  python3 demos/main.py --cli 02  # 终端查看某章摘要")
        return
    if args and args[0] == "--cli":
        print_chapter(args[1]) if len(args) > 1 else cli_menu()
        return
    open_lab(args[0] if args else None)


if __name__ == "__main__":
    main()
