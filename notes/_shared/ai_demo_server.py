"""AI 主题演示的本地服务：静态页 + DeepSeek 真实调用代理。

设计约束：
- Key 只从环境变量 DEEPSEEK_API_KEY 读取，不落盘、不下发到浏览器。
- 仅监听 127.0.0.1，页面与接口同源，避免浏览器端持有密钥。
- 未配置 Key 时静态页仍可离线浏览，接口返回明确的错误提示。

用法（由各主题 demos/main.py 调用）：
    from ai_demo_server import run
    run(demo_dir=Path(".../demos"), page="index.html", chapter="03")
"""

from __future__ import annotations

import ast
import functools
import json
import os
import re
import socket
import sys
import threading
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_BASE = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEFAULT_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
DEFAULT_PORT = 8765


class DemoError(Exception):
    """可直接展示给用户的错误（不包含密钥等敏感信息）。"""


def api_key() -> str:
    return os.environ.get("DEEPSEEK_API_KEY", "").strip()


def deepseek_chat(payload: dict[str, Any]) -> dict[str, Any]:
    key = api_key()
    if not key:
        raise DemoError("未检测到 DEEPSEEK_API_KEY，请先按开发环境信息配置环境变量")

    body = {"model": DEFAULT_MODEL, **payload}
    req = Request(
        f"{API_BASE}/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        detail = ""
        try:
            err = json.loads(exc.read().decode("utf-8"))
            detail = (err.get("error") or {}).get("message") or ""
        except Exception:
            pass
        raise DemoError(f"DeepSeek 接口返回 {exc.code}" + (f"：{detail}" if detail else "")) from None
    except URLError as exc:
        raise DemoError(f"无法连接 DeepSeek：{exc.reason}") from None


def _content_of(resp: dict[str, Any]) -> str:
    choices = resp.get("choices") or []
    if not choices:
        raise DemoError("DeepSeek 返回为空，请稍后重试")
    return (choices[0].get("message") or {}).get("content") or ""


# ---------------------------------------------------------------- RAG 演示 --

RAG_DOCS: list[dict[str, str]] = [
    {"id": "1", "title": "出差申请", "text": "员工出差前需在系统提交申请，经直属主管审批后方可订票。未审批的行程不予报销。"},
    {"id": "2", "title": "住宿标准", "text": "住宿标准按城市分级：一线城市每晚不超过 600 元，二线城市不超过 450 元，三线及以下城市不超过 320 元。"},
    {"id": "3", "title": "超标处理", "text": "住宿费超标部分需自行承担；确有特殊情况，须提前报备财务总监并留存书面说明。"},
    {"id": "4", "title": "报销材料", "text": "报销时须附发票、行程单与审批单，三者缺一不可，抬头须为公司全称。"},
    {"id": "5", "title": "报销时限", "text": "报销单审批通过后 5 个工作日内到账；每月 25 日后提交的顺延至次月处理。"},
    {"id": "6", "title": "交通标准", "text": "市内交通实报实销；城际出行高铁二等座、飞机经济舱，3 小时以内行程优先选择高铁。"},
    {"id": "7", "title": "出差补贴", "text": "出差补贴按天计算：一线城市 120 元/天，二线城市 90 元/天，其他城市 60 元/天。"},
    {"id": "8", "title": "国际差旅", "text": "国际差旅需提前 10 个工作日申请，住宿与补贴按目的地标准执行，汇率以报销当日中间价为准。"},
    {"id": "9", "title": "常见问题", "text": "周末出差可申请调休；住宿费按实际入住天数计算，提前退房按实际天数报销。"},
]


def _tokens(text: str) -> list[str]:
    text = text.lower()
    cjk = re.findall(r"[\u4e00-\u9fff]", text)
    latin = re.findall(r"[a-z0-9]+", text)
    bigrams = [a + b for a, b in zip(cjk, cjk[1:])]
    return cjk + latin + bigrams


def _bm25(query: str, docs: list[dict[str, str]], top_k: int = 3) -> list[dict[str, Any]]:
    q = _tokens(query)
    corpus = [_tokens(d["title"] + " " + d["text"]) for d in docs]
    n = len(corpus)
    avg_len = sum(len(c) for c in corpus) / max(n, 1)
    df: dict[str, int] = {}
    for doc in corpus:
        for term in set(doc):
            df[term] = df.get(term, 0) + 1

    k1, b = 1.5, 0.75
    scored = []
    for doc, terms in zip(docs, corpus):
        tf: dict[str, int] = {}
        for term in terms:
            tf[term] = tf.get(term, 0) + 1
        score = 0.0
        for term in q:
            if term not in tf:
                continue
            idf = ((n - df[term] + 0.5) / (df[term] + 0.5)) + 1.0
            freq = tf[term]
            score += idf * (freq * (k1 + 1)) / (
                freq + k1 * (1 - b + b * len(terms) / max(avg_len, 1e-9))
            )
        if score > 0:
            scored.append({"id": doc["id"], "title": doc["title"], "text": doc["text"], "score": round(score, 4)})
    scored.sort(key=lambda x: x["score"], reverse=True)
    if not scored:
        scored = [{"id": d["id"], "title": d["title"], "text": d["text"], "score": 0.0} for d in docs[:top_k]]
    return scored[:top_k]


def run_rag(question: str) -> dict[str, Any]:
    started = time.time()
    chunks = _bm25(question, RAG_DOCS, top_k=3)
    context = "\n".join(f"[{c['id']}] {c['title']}：{c['text']}" for c in chunks)
    prompt = (
        "你是企业知识库助手。只能依据【参考资料】回答，每个结论用 [编号] 标注来源；"
        "资料不足时明确回答「知识库中未找到依据」，不要编造。\n\n"
        f"【参考资料】\n{context}\n\n【问题】{question}"
    )
    resp = deepseek_chat(
        {
            "messages": [
                {"role": "system", "content": "你是严谨的企业制度问答助手，回答简洁、带引用编号。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 500,
        }
    )
    return {
        "question": question,
        "chunks": chunks,
        "prompt": prompt,
        "answer": _content_of(resp).strip(),
        "model": resp.get("model", DEFAULT_MODEL),
        "elapsed_ms": int((time.time() - started) * 1000),
    }


# -------------------------------------------------------------- Agent 演示 --

def _safe_calc(expression: str) -> str:
    allowed_bin = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)
    allowed_unary = (ast.UAdd, ast.USub)

    def walk(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and isinstance(node.op, allowed_bin):
            left, right = walk(node.left), walk(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 12:
                raise DemoError("指数过大，已拒绝计算")
            return {
                ast.Add: lambda: left + right,
                ast.Sub: lambda: left - right,
                ast.Mult: lambda: left * right,
                ast.Div: lambda: left / right,
                ast.FloorDiv: lambda: left // right,
                ast.Mod: lambda: left % right,
                ast.Pow: lambda: left**right,
            }[type(node.op)]()
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, allowed_unary):
            val = walk(node.operand)
            return val if isinstance(node.op, ast.UAdd) else -val
        raise DemoError("表达式仅支持数字与 + - * / // % ** 运算")

    try:
        value = walk(ast.parse(expression, mode="eval"))
    except DemoError:
        raise
    except Exception:
        raise DemoError("表达式无法解析") from None
    return f"{value:.6g}"


FINANCIALS = {
    ("XX科技", "2024"): "营业收入 128.6 亿元，同比 +18.2%；归母净利润 15.3 亿元。来源：2024 年报 P42。",
    ("XX科技", "2023"): "营业收入 108.8 亿元，同比 +12.1%；归母净利润 12.4 亿元。来源：2023 年报 P38。",
}

INDUSTRY = {
    ("半导体", "revenue_growth", "2024"): "半导体行业 2024 年平均营收增速 11.4%。来源：行业协会 2025-03-01 发布。",
}


def _search_financials(company: str, year: str) -> str:
    return FINANCIALS.get((company, str(year)), f"未找到 {company} {year} 年财报数据，请勿推测。")


def _search_industry(industry: str, metric: str, year: str) -> str:
    return INDUSTRY.get(
        (industry, metric, str(year)),
        f"未找到 {industry} 行业 {year} 年 {metric} 数据，请勿推测。",
    )


AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_financials",
            "description": "查询指定公司指定年度的财报数据（营收、增速、净利润）",
            "parameters": {
                "type": "object",
                "properties": {
                    "company": {"type": "string", "description": "公司名称，如 XX科技"},
                    "year": {"type": "string", "description": "报告年度，如 2024"},
                },
                "required": ["company", "year"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_industry",
            "description": "查询行业指标，用于与公司数据做横向对比",
            "parameters": {
                "type": "object",
                "properties": {
                    "industry": {"type": "string", "description": "行业名称，如 半导体"},
                    "metric": {"type": "string", "description": "指标，如 revenue_growth"},
                    "year": {"type": "string", "description": "年度，如 2024"},
                },
                "required": ["industry", "metric", "year"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "精确计算一个数学表达式，例如 (128.6/108.8-1)*100",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string", "description": "只含数字与 + - * / // % ** 的表达式"}},
                "required": ["expression"],
            },
        },
    },
]


def _run_tool(name: str, args: dict[str, Any]) -> str:
    if name == "search_financials":
        return _search_financials(str(args.get("company", "")), str(args.get("year", "")))
    if name == "search_industry":
        return _search_industry(
            str(args.get("industry", "")), str(args.get("metric", "")), str(args.get("year", ""))
        )
    if name == "calculator":
        return _safe_calc(str(args.get("expression", "")))
    return f"未知工具：{name}"


def run_agent(question: str, max_steps: int = 6) -> dict[str, Any]:
    started = time.time()
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "你是严谨的投研助手。需要数据时必须调用工具，不得编造数字；"
                "最终回答要标注数据来源，并明确写出计算过程；不得给出买入/卖出等投资建议。"
            ),
        },
        {"role": "user", "content": question},
    ]
    trace: list[dict[str, Any]] = []

    for step in range(1, max_steps + 1):
        resp = deepseek_chat(
            {"messages": messages, "tools": AGENT_TOOLS, "tool_choice": "auto", "temperature": 0.2, "max_tokens": 800}
        )
        msg = (resp.get("choices") or [{}])[0].get("message") or {}
        calls = msg.get("tool_calls") or []
        thought = (msg.get("content") or "").strip()

        if not calls:
            answer = thought or "（模型未返回内容）"
            trace.append({"step": step, "thought": thought, "final": answer})
            return {
                "question": question,
                "steps": trace,
                "answer": answer,
                "model": resp.get("model", DEFAULT_MODEL),
                "elapsed_ms": int((time.time() - started) * 1000),
            }

        messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
        for call in calls:
            fn = call.get("function") or {}
            name = fn.get("name", "")
            raw_args = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw_args)
            except Exception:
                args = {}
            try:
                observation = _run_tool(name, args)
            except DemoError as exc:
                observation = f"工具执行失败：{exc}"
            args_text = json.dumps(args, ensure_ascii=False)
            trace.append(
                {"step": step, "thought": thought, "tool": name, "args": args_text, "observation": observation}
            )
            messages.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": observation})

    answer = f"已达到最大步数 {max_steps}，未能收敛。请把问题拆小一些再试。"
    trace.append({"step": max_steps, "final": answer})
    return {
        "question": question,
        "steps": trace,
        "answer": answer,
        "model": DEFAULT_MODEL,
        "elapsed_ms": int((time.time() - started) * 1000),
    }


# ------------------------------------------------------------- 概率采样演示 --

def run_logprobs(prompt: str, top_k: int = 8) -> dict[str, Any]:
    resp = deepseek_chat(
        {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 1.0,
            "max_tokens": 1,
            "logprobs": True,
            "top_logprobs": max(1, min(top_k, 20)),
        }
    )
    choices = resp.get("choices") or []
    if not choices:
        raise DemoError("DeepSeek 返回为空，请稍后重试")
    content = ((choices[0].get("logprobs") or {}).get("content")) or []
    if not content:
        raise DemoError("该模型未返回 logprobs，无法展示真实概率")
    first = content[0]
    alts = first.get("top_logprobs") or [{"token": first.get("token", ""), "logprob": first.get("logprob", 0.0)}]
    return {
        "prompt": prompt,
        "token": first.get("token", ""),
        "alternatives": [{"token": a.get("token", ""), "logprob": float(a.get("logprob", 0.0))} for a in alts],
        "model": resp.get("model", DEFAULT_MODEL),
    }


# ------------------------------------------------------------------ HTTP 层 --

class DemoHandler(SimpleHTTPRequestHandler):
    """静态文件 + 同源 API。静态目录由 functools.partial 注入。"""

    server_version = "AiDemoServer/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:  # 静默常规访问日志
        if os.environ.get("AI_DEMO_VERBOSE"):
            super().log_message(fmt, *args)

    def end_headers(self) -> None:
        if self.path.endswith(".html") or self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _send_json(self, obj: Any, status: int = 200) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            raise DemoError("请求体不是合法 JSON") from None

    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?")[0] == "/api/status":
            self._send_json(
                {
                    "ok": True,
                    "demo": self.server.demo_label,  # type: ignore[attr-defined]
                    "key_configured": bool(api_key()),
                    "model": DEFAULT_MODEL,
                    "endpoints": ["/api/chat", "/api/logprobs", "/api/rag", "/api/agent"],
                }
            )
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        try:
            body = self._read_json()
            if path == "/api/chat":
                messages = body.get("messages") or []
                if not isinstance(messages, list) or not messages:
                    raise DemoError("messages 不能为空")
                temperature = float(body.get("temperature", 0.7))
                max_tokens = int(body.get("max_tokens", 600))
                resp = deepseek_chat(
                    {
                        "messages": messages,
                        "temperature": max(0.0, min(temperature, 2.0)),
                        "max_tokens": max(1, min(max_tokens, 2048)),
                    }
                )
                self._send_json(
                    {
                        "content": _content_of(resp).strip(),
                        "model": resp.get("model", DEFAULT_MODEL),
                        "usage": resp.get("usage") or {},
                    }
                )
                return
            if path == "/api/logprobs":
                prompt = str(body.get("prompt") or "").strip()
                if not prompt:
                    raise DemoError("prompt 不能为空")
                self._send_json(run_logprobs(prompt, int(body.get("top_k", 8))))
                return
            if path == "/api/rag":
                question = str(body.get("question") or "").strip()
                if not question:
                    raise DemoError("question 不能为空")
                self._send_json(run_rag(question))
                return
            if path == "/api/agent":
                question = str(body.get("question") or "").strip()
                if not question:
                    raise DemoError("question 不能为空")
                self._send_json(run_agent(question))
                return
            self._send_json({"error": "接口不存在"}, status=404)
        except DemoError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except Exception as exc:  # 兜底：不泄露堆栈中的敏感信息
            self._send_json({"error": f"服务异常：{type(exc).__name__}"}, status=500)


def _free_port(start: int) -> int:
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise DemoError(f"{start}~{start + 49} 端口都被占用，请用 --port 指定其它端口")


def run(demo_dir: Path, page: str = "index.html", chapter: str | None = None, port: int = DEFAULT_PORT, label: str = "") -> None:
    """启动本地服务并在浏览器打开演示页。"""
    demo_dir = Path(demo_dir).resolve()
    if not (demo_dir / page).is_file():
        print(f"找不到演示页: {demo_dir / page}", file=sys.stderr)
        sys.exit(1)

    actual_port = _free_port(port)
    handler = functools.partial(DemoHandler, directory=str(demo_dir))
    server = ThreadingHTTPServer(("127.0.0.1", actual_port), handler)
    server.demo_label = label or demo_dir.parent.name  # type: ignore[attr-defined]

    query = f"?c={chapter}" if chapter else ""
    url = f"http://127.0.0.1:{actual_port}/{page}{query}"

    print("==> 本地演示服务已启动")
    print(f"    {url}")
    if api_key():
        print(f"    DeepSeek: 已连接（{DEFAULT_MODEL}），页面上的「真实调用」按钮可用")
    else:
        print("    DeepSeek: 未检测到 DEEPSEEK_API_KEY，仅可离线浏览（真实调用会给出提示）")
    print("    Ctrl+C 停止服务")

    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n==> 已停止本地演示服务")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":  # 便于单独调试
    import argparse

    parser = argparse.ArgumentParser(description="AI 主题演示本地服务")
    parser.add_argument("demo_dir", type=Path, help="演示页所在目录")
    parser.add_argument("--page", default="index.html")
    parser.add_argument("--chapter")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    ns = parser.parse_args()
    run(ns.demo_dir, ns.page, ns.chapter, ns.port)
