#!/usr/bin/env python3
"""海豚调度演示入口：默认打开可视化交互页；--cli 使用终端版。"""

from __future__ import annotations

import importlib
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CHAPTERS = [
    ("01", "概述与定位", "chapters.01_overview"),
    ("02", "架构与组件", "chapters.02_architecture"),
    ("03", "核心概念", "chapters.03_concepts"),
    ("04", "DAG与调度", "chapters.04_dag_schedule"),
    ("05", "任务类型详解", "chapters.05_tasks_resources"),
]

LAB = ROOT / "index.html"


def open_lab(chapter: str | None = None) -> None:
    if not LAB.is_file():
        print(f"找不到可视化演示页: {LAB}", file=sys.stderr)
        sys.exit(1)
    uri = LAB.resolve().as_uri()
    if chapter:
        code = chapter.strip().zfill(2) if chapter.strip().isdigit() else chapter.strip()
        uri = f"{uri}?c={code}"
    print("==> 打开可视化交互演示（浏览器）")
    print(f"    {uri}")
    print("    左侧选章节；第 04 章可单步/播放 DAG。")
    print("    若要终端版：python3 demos/main.py --cli [章节号]")
    webbrowser.open(uri)


def run_cli_chapter(code: str) -> None:
    code = code.strip().zfill(2) if code.isdigit() else code.strip()
    for num, title, module_name in CHAPTERS:
        if code in (num, num.lstrip("0") or "0"):
            print(f"\n######## 第 {num} 章 · {title}（终端版） ########\n")
            mod = importlib.import_module(module_name)
            mod.run()
            return
    print(f"未找到章节: {code}，可选: {[c[0] for c in CHAPTERS]}")
    sys.exit(1)


def cli_menu() -> None:
    print("海豚调度 · 终端演示（备用）\n")
    for num, title, _ in CHAPTERS:
        print(f"  {num}  {title}")
    print("  q   退出")
    choice = input("\n选择章节编号: ").strip().lower()
    if choice in ("q", "quit", "exit"):
        return
    run_cli_chapter(choice)


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] in {"-h", "--help"}:
        print("用法:")
        print("  python3 demos/main.py           # 打开可视化交互页")
        print("  python3 demos/main.py 04        # 打开并定位到第 4 章")
        print("  python3 demos/main.py --cli     # 终端版菜单")
        print("  python3 demos/main.py --cli 04  # 终端版直达章节")
        return

    if args and args[0] == "--cli":
        if len(args) > 1:
            run_cli_chapter(args[1])
        else:
            cli_menu()
        return

    chapter = args[0] if args else None
    open_lab(chapter)


if __name__ == "__main__":
    main()
