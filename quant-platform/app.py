#!/usr/bin/env python3
"""QuantLab 本地量化工作台：标准库 HTTP 服务 + 回测 API。"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from quantlab.data import get_market
from quantlab.engine import StrategyError, run_backtest
from quantlab.store import StrategyStore
from quantlab.templates import TEMPLATES

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
STORE = StrategyStore(ROOT / "data" / "strategies.json")
MARKET = get_market()


def config_payload() -> dict:
    return {
        "universe": MARKET.universe(),
        "benchmarks": MARKET.benchmark_list(),
        "date_range": {"start": MARKET.start_date, "end": MARKET.end_date},
        "defaults": {
            "start": MARKET.default_start(),
            "end": MARKET.end_date,
            "cash": 1_000_000,
            "benchmark": "000300.XSHG",
        },
        "rules": {
            "frequency": "日线（收盘出信号，次日开盘成交）",
            "t_plus": "T+1",
            "lot_size": 100,
            "price_limit": "±10%",
            "commission": "万三，最低 5 元",
            "stamp_duty": "卖出千分之 0.5",
            "slippage": "单边千分之 0.5",
        },
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "QuantLab/1.0"

    def log_message(self, fmt: str, *args) -> None:  # 保持终端输出简洁
        if "/api/" not in (args[0] if args else ""):
            return
        print(f"[quantlab] {args[0]}")

    # ---------- 响应工具 ----------

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        if not path.is_file():
            self._send_json({"error": "文件不存在"}, 404)
            return
        body = path.read_bytes()
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix == ".js":
            ctype = "application/javascript; charset=utf-8"
        elif path.suffix in (".html", ".css"):
            ctype += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(f"请求体不是合法 JSON：{exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("请求体必须是 JSON 对象")
        return data

    # ---------- 路由 ----------

    def do_GET(self) -> None:  # noqa: N802
        path = unquote(urlparse(self.path).path)
        try:
            if path == "/api/health":
                self._send_json({"ok": True, "service": "quantlab"})
            elif path == "/api/config":
                self._send_json(config_payload())
            elif path == "/api/templates":
                self._send_json({"templates": TEMPLATES})
            elif path == "/api/strategies":
                self._send_json({"strategies": STORE.list()})
            elif path.startswith("/api/strategies/"):
                sid = path.rsplit("/", 1)[-1]
                item = STORE.get(sid)
                if item is None:
                    self._send_json({"error": "策略不存在"}, 404)
                else:
                    self._send_json({"strategy": item})
            elif path in ("/", "/index.html"):
                self._send_file(STATIC_DIR / "index.html")
            elif path.startswith("/static/"):
                target = (STATIC_DIR / path[len("/static/"):]).resolve()
                try:
                    target.relative_to(STATIC_DIR)
                except ValueError:
                    self._send_json({"error": "非法路径"}, 403)
                    return
                self._send_file(target)
            else:
                self._send_json({"error": "未知接口"}, 404)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._send_json({"error": f"服务端错误：{exc}"}, 500)

    def do_POST(self) -> None:  # noqa: N802
        path = unquote(urlparse(self.path).path)
        try:
            payload = self._read_json()
        except ValueError as exc:
            self._send_json({"error": str(exc)}, 400)
            return

        try:
            if path == "/api/backtest":
                code = payload.get("code")
                if not isinstance(code, str):
                    raise StrategyError("缺少策略代码")
                result = run_backtest(
                    code,
                    MARKET,
                    start=payload.get("start"),
                    end=payload.get("end"),
                    cash=float(payload.get("cash") or 1_000_000),
                    benchmark=payload.get("benchmark") or "000300.XSHG",
                )
                self._send_json({"result": result})
            elif path == "/api/strategies":
                name = str(payload.get("name") or "未命名策略")
                code = str(payload.get("code") or "")
                sid = payload.get("id") or None
                item = STORE.save(name, code, str(sid) if sid else None)
                self._send_json({"strategy": item}, 200)
            else:
                self._send_json({"error": "未知接口"}, 404)
        except StrategyError as exc:
            self._send_json({"error": str(exc), "logs": exc.logs}, 400)
        except (ValueError, TypeError) as exc:
            self._send_json({"error": str(exc)}, 400)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._send_json({"error": f"服务端错误：{exc}"}, 500)

    def do_DELETE(self) -> None:  # noqa: N802
        path = unquote(urlparse(self.path).path)
        if path.startswith("/api/strategies/"):
            sid = path.rsplit("/", 1)[-1]
            if STORE.delete(sid):
                self._send_json({"ok": True})
            else:
                self._send_json({"error": "策略不存在"}, 404)
        else:
            self._send_json({"error": "未知接口"}, 404)


def main() -> None:
    parser = argparse.ArgumentParser(description="QuantLab 本地量化交易工作台")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8777)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    try:
        server = ThreadingHTTPServer((args.host, args.port), Handler)
    except OSError as exc:
        print(f"错误：端口 {args.port} 不可用（{exc}）。可用 PORT=9000 ./start.sh 指定其他端口。", file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"==> QuantLab 已启动：{url}")
    print(f"    行情：内置模拟日线 {MARKET.start_date} ~ {MARKET.end_date}（{len(MARKET.calendar)} 个交易日）")
    print(f"    标的：{len(MARKET.stocks)} 只 · 基准：{len(MARKET.benchmarks)} 个")
    print("    按 Ctrl+C 停止")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在关闭...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
