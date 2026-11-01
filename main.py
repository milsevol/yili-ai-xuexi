#!/usr/bin/env python3
"""仓库总入口：选择主题并进入该主题的演示程序。"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# 新增主题时在此登记：(编号显示名, 主题目录名, 一句话说明)
TOPICS = [
    ("1", "dolphin-scheduler", "海豚调度（DolphinScheduler）"),
]


def load_topic_main(topic_dir: Path) -> Path:
    main_py = topic_dir / "demos" / "main.py"
    if not main_py.is_file():
        raise FileNotFoundError(f"主题入口不存在: {main_py}")
    return main_py


def enter_topic(topic_dir_name: str, chapter_args: list[str]) -> None:
    topic_dir = ROOT / topic_dir_name
    main_py = load_topic_main(topic_dir)
    # 把主题 demos 目录放入 path，便于 chapters 相对导入
    demos_dir = str(topic_dir / "demos")
    if demos_dir not in sys.path:
        sys.path.insert(0, demos_dir)
    sys.argv = [str(main_py), *chapter_args]
    runpy.run_path(str(main_py), run_name="__main__")


def print_menu() -> None:
    print("yili-ai-xuexi — 选择主题\n")
    if not TOPICS:
        print("（暂无主题。新增主题后在 main.py 的 TOPICS 中登记。）")
        return
    for num, dirname, desc in TOPICS:
        print(f"  {num}. {desc}  [{dirname}]")
    print("  q. 退出")


def main() -> None:
    # 支持直达：python3 main.py <主题目录名> [章节参数...]
    if len(sys.argv) >= 2 and sys.argv[1] not in {"-h", "--help"}:
        enter_topic(sys.argv[1], sys.argv[2:])
        return

    while True:
        print_menu()
        if not TOPICS:
            return
        choice = input("\n请输入编号: ").strip().lower()
        if choice in {"q", "quit", "exit"}:
            return
        matched = [t for t in TOPICS if t[0] == choice]
        if not matched:
            print("无效编号，请重试。\n")
            continue
        _, dirname, _ = matched[0]
        enter_topic(dirname, [])
        print()


if __name__ == "__main__":
    main()
