#!/usr/bin/env python3
"""飞书应用开发 演示入口：默认打开可视化交互页；--cli 输出终端文字版摘要。"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT / "index.html"

CHAPTERS = [
    ("01", "概述与定位", "飞书 vs 企微 vs 钉钉。飞书能做什么：IM 消息、多维表格、云文档、日历会议、审批、小程序。开发链路总览。"),
    ("02", "开放平台与应用注册", "开发者后台、自建应用/商店应用、App ID/App Secret、权限 scope、事件订阅（HTTP 回调 / WebSocket）、版本发布与可见范围。"),
    ("03", "身份认证与 Token", "tenant/app/user 三种 access_token、OAuth2 授权码换 user_access_token、token 缓存刷新、JSAPI 鉴权、open_id/user_id/union_id。"),
    ("04", "消息与卡片", "发消息 API 与 msg_type、消息卡片（交互式按钮回调）、自定义机器人 Webhook、接收消息事件、频控。"),
    ("05", "多维表格 Bitable", "app/table/field/record/view 模型、字段类型与写入格式、记录 CRUD 与批量、自动化流程、Python 集成当 CRM。"),
    ("06", "文档与云空间", "docx Block 模型、文档块读写、电子表格 sheet 单元格 API、云空间 Drive 上传下载与权限。"),
    ("07", "通讯录与组织架构", "部门树与成员 API、open_id/user_id/union_id、扫码登录、网页应用免登、组织架构同步。"),
    ("08", "日历会议与审批", "日历日程与参会人、视频会议与妙记、审批定义/实例/回调事件、考勤打卡数据。"),
    ("09", "小程序与工作台", "飞书小程序 vs 网页应用 H5 vs 纯后端、tt 命名空间 API、应用消息推送、选型决策。"),
    ("10", "工作台详解", "工作台组成与布局、应用上架全流程、终端可见性、可用范围、分组排序、管理员配置、工作台小组件、常见排查。"),
    ("11", "实战与 FAQ", "审批驱动的费用管理机器人全链路实战、调试技巧、错误码速查、频控应对、上线 Checklist、常见问题。"),
]


def open_lab(chapter: str | None = None) -> None:
    if not LAB.is_file():
        print(f"找不到可视化演示页: {LAB}", file=sys.stderr)
        sys.exit(1)
    uri = LAB.resolve().as_uri()
    if chapter:
        code = chapter.strip().zfill(2) if chapter.strip().isdigit() else chapter.strip()
        uri = f"{uri}?c={code}"
    print("==> 打开飞书应用开发 可视化交互演示（浏览器）")
    print(f"    {uri}")
    print("    左侧选章节；推荐先看 02（应用注册）、03（Token）、04（消息卡片）、05（多维表格）、10（工作台）。")
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
    print("飞书应用开发 · 终端摘要版\n")
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
