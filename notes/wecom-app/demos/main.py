#!/usr/bin/env python3
"""企微应用开发 演示入口：默认打开可视化交互页；--cli 输出终端文字版摘要。"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT / "index.html"

CHAPTERS = [
    ("01", "概述与定位", "企业微信 vs 微信 vs 钉钉。企微能做什么：自建应用、客户联系、侧边栏、JS-SDK、审批、打卡。开发链路总览。"),
    ("02", "应用注册与配置", "corpId、agentId、secret 三要素。应用可见范围、回调 URL、Token/EncodingAESKey。沙箱环境 vs 正式环境。"),
    ("03", "消息收发机制", "回调验证 URL、接收消息 XML 解析（文本/图片/卡片）、被动响应 vs 主动推送。access_token 获取与缓存。"),
    ("04", "客户联系与客户群", "客户联系 API、外部联系人标签、客户群管理、群聊成员邀请、SCRM 场景。客户联系权限配置。"),
    ("05", "侧边栏与 JS-SDK", "应用侧边栏配置、wx.invoke JS-SDK 调用（扫码、上传、定位）、自定义菜单、工具栏按钮。"),
    ("06", "审批与打卡集成", "审批模板配置、获取审批实例、审批回调事件、打卡数据获取、打卡规则设置。"),
    ("07", "通讯录与身份验证", "成员/部门管理 API、OAuth2 网页授权、UserID 转换（openid ↔ userid）、敏感数据获取权限。"),
    ("08", "微应用与小程序", "微应用 vs 小程序 vs 第三方应用。小程序开发、云开发、订阅消息、小程序跳转微应用。"),
    ("09", "企业内部实战案例", "内部工具开发全流程：需求 → 注册应用 → 开发 → 测试 → 上线。AI 客服接入、报表系统、审批流集成。"),
    ("10", "开发技巧与 FAQ", "调试技巧、沙箱环境、频率限制（每分钟调用次数）、常见坑排查、企微 vs 微信开放平台。"),
    ("11", "管理后台常见操作", "管理员体系（创建者/超级/分级/应用管理员）、转让创建者、通讯录管理、应用管理、客户联系配置、安全设置、审计日志。"),
]


def open_lab(chapter: str | None = None) -> None:
    if not LAB.is_file():
        print(f"找不到可视化演示页: {LAB}", file=sys.stderr)
        sys.exit(1)
    uri = LAB.resolve().as_uri()
    if chapter:
        code = chapter.strip().zfill(2) if chapter.strip().isdigit() else chapter.strip()
        uri = f"{uri}?c={code}"
    print("==> 打开企微应用开发 可视化交互演示（浏览器）")
    print(f"    {uri}")
    print("    左侧选章节；推荐先看 02（应用注册）、03（消息收发）、05（JS-SDK）、07（OAuth）。")
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
    print("企微应用开发 · 终端摘要版\n")
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
