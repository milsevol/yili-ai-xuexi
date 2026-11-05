#!/usr/bin/env python3
"""提示词工程：默认打开可视化交互页；--cli 输出终端文字版摘要。"""

from __future__ import annotations

import importlib.util
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT / "index.html"
SHARED = ROOT.parents[1] / "_shared" / "ai_demo_server.py"

CHAPTERS = [
    ("01", "概述与定位", "Prompt Engineering 是「不改模型、只改输入」的优化层：零成本、见效快。边界要分清——知识缺失用 RAG，能力不足用微调，输出格式不稳用结构化约束 + 校验。"),
    ("02", "Prompt 结构与 Few-shot", "稳定 Prompt 的四要素：角色、指令、上下文、输出格式。Few-shot 用示例把模糊要求变成可模仿范式；示例顺序有近因效应，把最贴近当前输入的放最后。"),
    ("03", "思维链 CoT 与推理增强", "CoT 先写推理再给结论，多步计算与逻辑任务收益最大；简单抽取/改写/分类加 CoT 反而更慢更贵。Self-Consistency 用多路径投票进一步提升稳定性。"),
    ("04", "结构化输出与 Function Calling", "工具调用四步：定义 schema → 模型输出结构化请求 → 程序校验执行 → 结果回填。必备防护：schema 校验、失败重试、参数白名单。"),
    ("05", "评估迭代与安全防护", "评估靠业务样本集 + LLM-as-Judge + 人工抽检。Prompt 注入的根源是把不可信输入当指令：隔离、声明、输出白名单、程序侧校验四层防护。"),
    ("06", "实战模板与 FAQ", "模板必须带输出格式、禁止事项、兜底规则。提供摘要/分类/抽取/客服/翻译 5 套可直接套用的模板与 8 个高频面试问答。"),
]


def open_lab(chapter: str | None = None) -> None:
    if not LAB.is_file():
        print(f"找不到可视化演示页: {LAB}", file=sys.stderr)
        sys.exit(1)
    uri = LAB.resolve().as_uri()
    if chapter:
        code = chapter.strip().zfill(2) if chapter.strip().isdigit() else chapter.strip()
        uri = f"{uri}?c={code}"
    print("==> 打开提示词工程 可视化交互演示（浏览器）")
    print(f"    {uri}")
    print("    推荐顺序：02（结构）→ 03（CoT）→ 04（工具调用）→ 05（注入防护）。")
    webbrowser.open(uri)


def serve_lab(chapter: str | None = None, port: int = 8765) -> None:
    """启动本地服务（静态页 + DeepSeek 真实调用），并打开浏览器。"""
    if not LAB.is_file():
        print(f"找不到可视化演示页: {LAB}", file=sys.stderr)
        sys.exit(1)
    if not SHARED.is_file():  # 共享模块缺失时回退为直接打开文件
        open_lab(chapter)
        return
    spec = importlib.util.spec_from_file_location("ai_demo_server", SHARED)
    if spec is None or spec.loader is None:
        open_lab(chapter)
        return
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.run(ROOT, page=LAB.name, chapter=chapter, port=port, label="提示词工程")


def print_chapter(code: str) -> None:
    code = code.strip().zfill(2) if code.isdigit() else code.strip()
    for num, title, summary in CHAPTERS:
        if code in (num, num.lstrip("0") or "0"):
            print(f"\n## {num} {title}\n\n{summary}\n")
            return
    print(f"未找到章节: {code}，可选: {[c[0] for c in CHAPTERS]}")
    sys.exit(1)


def cli_menu() -> None:
    print("提示词工程 · 终端摘要版\n")
    for num, title, _ in CHAPTERS:
        print(f"  {num}  {title}")
    choice = input("\n选择章节编号（q 退出）: ").strip().lower()
    if choice not in ("q", "quit", "exit", ""):
        print_chapter(choice)


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] in {"-h", "--help"}:
        print("用法:")
        print("  python3 demos/main.py           # 启动本地服务并打开交互页（支持真实调用）")
        print("  python3 demos/main.py 03        # 打开并定位到第 3 章")
        print("  python3 demos/main.py --port 9000  # 指定端口")
        print("  python3 demos/main.py --cli     # 终端摘要菜单")
        print("  python3 demos/main.py --cli 03  # 终端查看某章摘要")
        return
    if args and args[0] == "--cli":
        print_chapter(args[1]) if len(args) > 1 else cli_menu()
        return
    port = 8765
    if "--port" in args:
        idx = args.index("--port")
        try:
            port = int(args[idx + 1])
            del args[idx:idx + 2]
        except (IndexError, ValueError):
            print("--port 需要一个整数端口，例如 --port 9000", file=sys.stderr)
            sys.exit(1)
    serve_lab(args[0] if args else None, port)


if __name__ == "__main__":
    main()
