#!/usr/bin/env python3
"""金融 Agent 平台（教学版）：多租户 + Agent 上架 + MCP 注册 + 调试运行 + 审计。

运行方式：
- 模型：默认接入 DeepSeek（OpenAI 兼容接口），读取 DEEPSEEK_API_KEY；
  未配置 Key 或调用失败时自动降级为离线模拟，并在运行步骤里明确标注。
- 工具：内置工具（行情/财报/研报/合规/计算器）是真实执行逻辑，数据为演示数据集；
  自定义 MCP 工具会按 JSON-RPC 真实调用注册的 HTTP 端点。
- 存储：SQLite；生产替换点为 PostgreSQL（行级安全）。

启动：
    python3 demos/main.py                 # 默认 127.0.0.1:8787，自动打开控制台
    python3 demos/main.py --reset         # 清空演示数据后重建
    python3 demos/main.py --port 9000 --no-browser
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import operator
import os
import re
import sqlite3
import threading
import time
import uuid
import webbrowser
from contextlib import closing
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / ".data" / "platform.db"
VENDOR = ROOT / "vendor"

app = FastAPI(title="金融 Agent 平台（教学版）", docs_url="/api/docs")
app.mount("/vendor", StaticFiles(directory=VENDOR), name="vendor")


# ------------------------------------------------------------------ 存储 --

def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, industry TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, name TEXT NOT NULL,
  title TEXT NOT NULL, role TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mcp_servers (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, name TEXT NOT NULL,
  transport TEXT NOT NULL, endpoint TEXT NOT NULL, scope TEXT NOT NULL,
  tool_name TEXT NOT NULL, tool_label TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
  input_schema TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS agents (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '', system_prompt TEXT NOT NULL DEFAULT '',
  tools TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT 'draft',
  version INTEGER NOT NULL DEFAULT 1, created_by TEXT NOT NULL,
  reviewed_by TEXT, review_note TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, agent_id TEXT NOT NULL,
  agent_name TEXT NOT NULL, user_id TEXT NOT NULL, question TEXT NOT NULL,
  answer TEXT NOT NULL DEFAULT '', steps TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL, tokens INTEGER NOT NULL DEFAULT 0,
  latency_ms INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
  model TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT NOT NULL, actor TEXT NOT NULL,
  action TEXT NOT NULL, target TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
"""


MCP_SEED = [
    dict(id="mcp-sec-market", tenant_id="t-sec", name="行情数据服务", transport="http",
         endpoint="builtin://market", scope="market:read", tool_name="market_quote",
         tool_label="实时行情", description="查询 A 股个股最新价、涨跌幅、成交额与市盈率",
         input_schema={"type": "object", "properties": {
             "symbol": {"type": "string", "description": "6 位股票代码，如 300750"}},
             "required": ["symbol"]}),
    dict(id="mcp-sec-report", tenant_id="t-sec", name="研报检索服务", transport="sse",
         endpoint="builtin://report", scope="report:read", tool_name="report_search",
         tool_label="研报检索", description="检索内部研报库，返回标题、日期与观点摘要",
         input_schema={"type": "object", "properties": {
             "query": {"type": "string", "description": "检索关键词，如 宁德时代 海外产能"}},
             "required": ["query"]}),
    dict(id="mcp-sec-finance", tenant_id="t-sec", name="财报中心", transport="http",
         endpoint="builtin://finance", scope="finance:read", tool_name="financial_report",
         tool_label="财报指标", description="查询上市公司近三年营收、毛利率与经营现金流",
         input_schema={"type": "object", "properties": {
             "symbol": {"type": "string", "description": "6 位股票代码"},
             "years": {"type": "integer", "description": "返回年数，默认 3", "minimum": 1, "maximum": 5}},
             "required": ["symbol"]}),
    dict(id="mcp-sec-compliance", tenant_id="t-sec", name="合规规则库", transport="http",
         endpoint="builtin://compliance", scope="compliance:run", tool_name="compliance_check",
         tool_label="适当性审查", description="按适当性规则审查营销话术与投顾材料，返回命中条款",
         input_schema={"type": "object", "properties": {
             "text": {"type": "string", "description": "待审查的文本"}},
             "required": ["text"]}),
    dict(id="mcp-sec-calc", tenant_id="t-sec", name="指标计算器", transport="stdio",
         endpoint="builtin://calc", scope="calc:run", tool_name="calc",
         tool_label="指标计算", description="计算数学表达式，用于收益率、回撤、夏普等指标",
         input_schema={"type": "object", "properties": {
             "expression": {"type": "string", "description": "Python 数学表达式，如 (1.12**3)-1"}},
             "required": ["expression"]}),
    dict(id="mcp-am-bond", tenant_id="t-am", name="固收行情服务", transport="http",
         endpoint="builtin://bond", scope="market:read", tool_name="bond_quote",
         tool_label="债券行情", description="查询国债与信用债收益率",
         input_schema={"type": "object", "properties": {
             "tenor": {"type": "string", "description": "期限，如 10Y / 5Y"}},
             "required": ["tenor"]}),
    dict(id="mcp-am-report", tenant_id="t-am", name="研报检索服务", transport="sse",
         endpoint="builtin://report", scope="report:read", tool_name="report_search",
         tool_label="研报检索", description="检索内部研报库，返回标题、日期与观点摘要",
         input_schema={"type": "object", "properties": {
             "query": {"type": "string", "description": "检索关键词"}},
             "required": ["query"]}),
]


def seed(conn: sqlite3.Connection) -> None:
    """写入两家租户的种子数据。真实平台由 SSO / 租户管理服务同步。"""
    tenants = [
        ("t-sec", "华东证券 · 研究所", "证券"),
        ("t-am", "鼎元资管 · 固收部", "资管"),
    ]
    users = [
        ("u-sec-admin", "t-sec", "张敏", "平台管理员", "admin"),
        ("u-sec-dev", "t-sec", "李想", "Agent 开发者", "developer"),
        ("u-sec-view", "t-sec", "王研", "研究员", "viewer"),
        ("u-am-admin", "t-am", "陈璐", "租户管理员", "admin"),
        ("u-am-dev", "t-am", "周凯", "Agent 开发者", "developer"),
    ]
    agents = [
        ("ag-sec-1", "t-sec", "投研问答助手", "面向研究员的个股速览：行情 + 研报观点，附引用。",
         "你是券商投研助手，只基于工具返回的事实回答，必须标注数据来源，不给出投资建议。",
         ["market_quote", "report_search"], "published", 3, "u-sec-admin", "u-sec-admin", "首发上线"),
        ("ag-sec-2", "t-sec", "财报对比助手", "对比多家公司营收、毛利率与现金流，输出结构化对比表。",
         "你是财报分析助手，数字必须来自工具，缺失数据要明确说明，不推测未披露指标。",
         ["financial_report", "calc"], "published", 2, "u-sec-dev", "u-sec-admin", "补充计算器工具"),
        ("ag-sec-3", "t-sec", "合规审查助手", "审查营销材料与投顾话术是否符合适当性要求。",
         "你是合规审查助手，逐条比对规则并输出命中条款，结论需人工复核。",
         ["compliance_check"], "pending", 1, "u-sec-dev", None, None),
        ("ag-am-1", "t-am", "固收日报助手", "汇总当日债市行情与研报观点，生成部门晨报草稿。",
         "你是固收研究助手，输出晨报草稿，行情数据必须来自工具。",
         ["bond_quote", "report_search"], "draft", 1, "u-am-dev", None, None),
    ]
    ts = now()
    conn.executemany("INSERT INTO tenants VALUES (?,?,?)", tenants)
    conn.executemany("INSERT INTO users VALUES (?,?,?,?,?)", users)
    conn.executemany(
        "INSERT INTO mcp_servers(id, tenant_id, name, transport, endpoint, scope, tool_name, "
        "tool_label, enabled, created_at, description, input_schema) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (m["id"], m["tenant_id"], m["name"], m["transport"], m["endpoint"], m["scope"],
             m["tool_name"], m["tool_label"], 1, ts, m["description"],
             json.dumps(m["input_schema"], ensure_ascii=False))
            for m in MCP_SEED
        ],
    )
    conn.executemany(
        "INSERT INTO agents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (a[0], a[1], a[2], a[3], a[4], json.dumps(a[5], ensure_ascii=False), a[6], a[7],
             a[8], a[9], a[10], ts, ts)
            for a in agents
        ],
    )
    conn.execute(
        "INSERT INTO audit(tenant_id,actor,action,target,detail,created_at) VALUES (?,?,?,?,?,?)",
        ("t-sec", "u-sec-admin", "agent.publish", "投研问答助手", "首发上线，版本 v3", ts),
    )


def ensure_columns(conn: sqlite3.Connection) -> None:
    """兼容旧演示数据：为已存在的库补齐新增字段。"""
    def columns(table: str) -> set[str]:
        return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}

    additions = {
        "mcp_servers": [
            ("description", "TEXT NOT NULL DEFAULT ''"),
            ("input_schema", "TEXT NOT NULL DEFAULT '{}'"),
        ],
        "runs": [("model", "TEXT NOT NULL DEFAULT ''")],
    }
    for table, items in additions.items():
        existing = columns(table)
        for name, ddl in items:
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def init_db(reset: bool = False) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if reset and DB_PATH.exists():
        DB_PATH.unlink()
    with closing(connect()) as conn:
        conn.executescript(SCHEMA)
        ensure_columns(conn)
        if conn.execute("SELECT COUNT(*) AS n FROM tenants").fetchone()["n"] == 0:
            seed(conn)
        else:
            # 旧演示库升级：补齐内置工具的 schema，并把网关地址换成内置执行器
            for spec in MCP_SEED:
                conn.execute(
                    "UPDATE mcp_servers SET description = ?, input_schema = ?, endpoint = ? "
                    "WHERE tool_name = ? AND tenant_id = ?",
                    (spec["description"], json.dumps(spec["input_schema"], ensure_ascii=False),
                     spec["endpoint"], spec["tool_name"], spec["tenant_id"]),
                )
        conn.commit()


# ------------------------------------------------------------------ 鉴权 --

ROLE_SCOPES: dict[str, set[str]] = {
    "admin": {"*"},
    "developer": {"market:read", "finance:read", "report:read", "calc:run"},
    "viewer": {"market:read", "report:read"},
}


def current_user(x_user_id: str | None = Header(default=None, alias="X-User-Id")) -> dict[str, Any]:
    """生产环境由 SSO/OAuth2 解析 token，这里用请求头模拟身份切换。"""
    uid = x_user_id or "u-sec-dev"
    with closing(connect()) as conn:
        row = conn.execute(
            "SELECT u.*, t.name AS tenant_name FROM users u JOIN tenants t ON t.id = u.tenant_id "
            "WHERE u.id = ?",
            (uid,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="未知用户，请重新选择演示身份")
    return dict(row)


def require_role(user: dict[str, Any], roles: set[str]) -> None:
    if user["role"] not in roles:
        raise HTTPException(status_code=403, detail=f"当前角色 {user['role']} 无权执行该操作")


def scopes_of(user: dict[str, Any]) -> set[str]:
    return ROLE_SCOPES.get(user["role"], set())


def allowed(user: dict[str, Any], scope: str) -> bool:
    scopes = scopes_of(user)
    return "*" in scopes or scope in scopes


def audit(conn: sqlite3.Connection, user: dict[str, Any], action: str, target: str, detail: str = "") -> None:
    conn.execute(
        "INSERT INTO audit(tenant_id,actor,action,target,detail,created_at) VALUES (?,?,?,?,?,?)",
        (user["tenant_id"], user["name"], action, target, detail, now()),
    )


def tenant_agent(conn: sqlite3.Connection, user: dict[str, Any], agent_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    if row["tenant_id"] != user["tenant_id"]:
        audit(conn, user, "security.cross_tenant_denied", agent_id, "尝试访问其他租户的 Agent")
        conn.commit()
        raise HTTPException(status_code=403, detail="跨租户访问已拦截并记录审计")
    return row


# ------------------------------------------------------------------ 模型 --


class AgentIn(BaseModel):
    name: str = Field(min_length=2, max_length=30)
    description: str = Field(default="", max_length=200)
    system_prompt: str = Field(default="", max_length=1000)
    tools: list[str] = Field(default_factory=list)


class ReviewIn(BaseModel):
    decision: str
    note: str = Field(default="", max_length=200)


class McpIn(BaseModel):
    name: str = Field(min_length=2, max_length=30)
    tool_name: str = Field(pattern=r"^[a-z][a-z0-9_]{2,30}$")
    tool_label: str = Field(default="", max_length=30)
    transport: str = Field(default="http", pattern=r"^(http|sse|stdio)$")
    endpoint: str = Field(min_length=4, max_length=200)
    scope: str = Field(default="custom:run", max_length=40)
    description: str = Field(default="", max_length=200)


class ToggleIn(BaseModel):
    enabled: bool = True


class RunIn(BaseModel):
    agent_id: str
    question: str = Field(min_length=2, max_length=500)


def tenant_tools(conn: sqlite3.Connection, tenant_id: str) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM mcp_servers WHERE tenant_id = ? AND enabled = 1", (tenant_id,)
    ).fetchall()
    tools: dict[str, dict[str, Any]] = {}
    for r in rows:
        try:
            schema = json.loads(r["input_schema"] or "{}")
        except json.JSONDecodeError:
            schema = {}
        tools[r["tool_name"]] = {
            "name": r["tool_name"],
            "label": r["tool_label"] or r["name"],
            "scope": r["scope"],
            "mcp": r["name"],
            "transport": r["transport"],
            "endpoint": r["endpoint"],
            "description": r["description"] or f"{r['name']} 提供的工具",
            "input_schema": schema or {"type": "object", "properties": {}},
        }
    return tools


INTENT_RULES: list[tuple[tuple[str, ...], list[str], str]] = [
    (("行情", "股价", "涨跌", "价格", "估值", "转债", "收益率"), ["market_quote", "bond_quote"],
     "标的近期走势偏强，量能温和放大，估值处于近三年中位数附近。"),
    (("财报", "营收", "毛利", "现金流", "利润", "对比"), ["financial_report"],
     "收入保持双位数增长，毛利率稳步抬升，现金流质量优于利润增速。"),
    (("研报", "报告", "观点", "评级", "目标价"), ["report_search"],
     "卖方观点整体偏正面，核心分歧集中在产能爬坡与需求持续性。"),
    (("合规", "违规", "风险揭示", "适当性", "审查"), ["compliance_check"],
     "流程层面未发现硬性违规，材料完整性存在一处待补。"),
    (("计算", "年化", "回撤", "夏普", "收益"), ["calc"],
     "按给定区间测算，风险收益比处于可接受区间。"),
]

# ------------------------------------------------------------ 工具执行 --

QUOTES: dict[str, dict[str, Any]] = {
    "300750": {"name": "宁德时代", "price": 182.40, "change": 1.86, "turnover": "42.7 亿", "pe": 21.3},
    "600519": {"name": "贵州茅台", "price": 1528.00, "change": -0.42, "turnover": "31.2 亿", "pe": 24.8},
    "000001": {"name": "平安银行", "price": 11.26, "change": 0.71, "turnover": "18.5 亿", "pe": 5.2},
}

FINANCIALS: dict[str, list[dict[str, Any]]] = {
    "300750": [
        {"year": 2022, "revenue": 3286, "margin": 20.2, "cash": 612},
        {"year": 2023, "revenue": 4009, "margin": 22.9, "cash": 928},
        {"year": 2024, "revenue": 3620, "margin": 26.1, "cash": 970},
    ],
    "600519": [
        {"year": 2022, "revenue": 1276, "margin": 91.8, "cash": 366},
        {"year": 2023, "revenue": 1477, "margin": 91.9, "cash": 666},
        {"year": 2024, "revenue": 1709, "margin": 92.1, "cash": 924},
    ],
}

BONDS: dict[str, dict[str, Any]] = {
    "1Y": {"yield": 1.62, "change": 0.8},
    "5Y": {"yield": 1.95, "change": -0.6},
    "10Y": {"yield": 2.18, "change": -1.2},
}

REPORTS: list[dict[str, Any]] = [
    {"title": "宁德时代：海外产能兑现，盈利拐点确认", "date": "2026-10-18",
     "summary": "德国工厂爬坡超预期，2027 年海外产能占比有望达 35%，维持买入评级。",
     "tags": ["宁德时代", "300750", "海外产能", "电池", "毛利率"]},
    {"title": "宁德时代 Q3 毛利率超预期，储能业务拆分测算", "date": "2026-10-25",
     "summary": "Q3 毛利率 27.4%，储能出货环比 +18%，拆分后估值仍有提升空间。",
     "tags": ["宁德时代", "300750", "储能", "毛利率", "季报"]},
    {"title": "贵州茅台：批价企稳，渠道库存回落至合理区间", "date": "2026-10-12",
     "summary": "中秋国庆双节动销平稳，直营占比提升带动吨价，维持增持。",
     "tags": ["贵州茅台", "600519", "白酒", "批价", "渠道"]},
    {"title": "银行 2026 三季报综述：息差压力趋缓，资产质量分化", "date": "2026-10-30",
     "summary": "净息差环比收窄 2BP，零售不良率小幅上行，优选高股息标的。",
     "tags": ["银行", "平安银行", "000001", "息差", "不良率"]},
]

COMPLIANCE_RULES: list[dict[str, Any]] = [
    {"clause": "《证券期货投资者适当性管理办法》第十二条",
     "keywords": ["保本", "稳赚", "保证收益", "零风险"], "advice": "不得承诺收益或暗示保本"},
    {"clause": "《适当性管理办法》第二十三条",
     "keywords": ["风险揭示", "签字", "测评", "风险等级"], "advice": "需完成风险测评并签署风险揭示书"},
    {"clause": "《广告法》第二十五条",
     "keywords": ["最佳", "第一", "排名第一", "国家级"], "advice": "不得使用绝对化用语"},
]

TOOL_OBSERVATIONS: dict[str, str] = {
    "market_quote": "最新价 182.40 元，涨跌幅 +1.86%，成交额 42.7 亿元，PE(TTM) 21.3（离线模拟）",
    "bond_quote": "10 年期国债活跃券收益率 2.18%，较昨日 -1.2BP（离线模拟）",
    "financial_report": "近三年营收 3286 / 4009 / 3620 亿元，毛利率 20.2% / 22.9% / 26.1%，经营性现金流 612 / 928 / 970 亿元（离线模拟）",
    "report_search": "命中 3 篇研报：《海外产能兑现，盈利拐点确认》《Q3 毛利率超预期》《储能业务拆分测算》（离线模拟）",
    "compliance_check": "比对 42 条适当性规则，未发现禁止性情形；提示需补充风险揭示书签署记录（离线模拟）",
    "calc": "年化收益 12.3%，最大回撤 -8.6%，夏普 1.42（离线模拟）",
}


class ToolError(Exception):
    """工具执行失败，可安全展示给调用方。"""


def _tool_market_quote(args: dict[str, Any]) -> str:
    symbol = str(args.get("symbol", "")).strip()
    quote = QUOTES.get(symbol)
    if not quote:
        return f"未收录标的「{symbol or '空'}」，演示库支持：300750、600519、000001"
    return (
        f"{symbol} {quote['name']}：最新价 {quote['price']} 元，涨跌幅 {quote['change']:+.2f}%，"
        f"成交额 {quote['turnover']}，PE(TTM) {quote['pe']}（演示行情，非实时）"
    )


def _tool_bond_quote(args: dict[str, Any]) -> str:
    tenor = str(args.get("tenor") or "10Y").upper().replace("年", "Y")
    bond = BONDS.get(tenor)
    if not bond:
        return f"未收录期限「{tenor}」，演示库支持：1Y、5Y、10Y"
    return f"国债 {tenor} 收益率 {bond['yield']}%，较昨日 {bond['change']:+.1f}BP（演示行情）"


def _tool_financial_report(args: dict[str, Any]) -> str:
    symbol = str(args.get("symbol", "")).strip()
    rows = FINANCIALS.get(symbol)
    if not rows:
        return f"未收录 {symbol or '空'} 的财报数据（演示库支持 300750、600519）"
    try:
        years = max(1, min(int(args.get("years") or len(rows)), len(rows)))
    except (TypeError, ValueError):
        years = len(rows)
    parts = [
        f"{r['year']} 年营收 {r['revenue']} 亿元、毛利率 {r['margin']}%、经营性现金流 {r['cash']} 亿元"
        for r in rows[-years:]
    ]
    return "；".join(parts) + "（演示财报数据）"


def _terms(text: str) -> set[str]:
    return set(re.findall(r"[\u4e00-\u9fa5]{2,4}", text)) | set(
        re.findall(r"[A-Za-z0-9]{2,}", text.lower())
    )


def _tool_report_search(args: dict[str, Any]) -> str:
    query = str(args.get("query") or "").strip()
    if not query:
        return "缺少检索词 query"
    terms = _terms(query)
    scored = []
    for doc in REPORTS:
        haystack = doc["title"] + doc["summary"] + " ".join(doc["tags"])
        score = sum(1 for term in terms if term in haystack)
        if score:
            scored.append((score, doc))
    scored.sort(key=lambda item: -item[0])
    if not scored:
        return f"未检索到与「{query}」相关的研报"
    lines = [f"命中 {min(3, len(scored))} 篇（演示研报库）："]
    lines += [f"- {doc['date']}《{doc['title']}》：{doc['summary']}" for _, doc in scored[:3]]
    return "\n".join(lines)


def _tool_compliance_check(args: dict[str, Any]) -> str:
    text = str(args.get("text") or "")
    if not text.strip():
        return "请提供待审查文本"
    hits = [rule for rule in COMPLIANCE_RULES if any(k in text for k in rule["keywords"])]
    if not hits:
        return "未命中演示规则库中的禁止性表述；仍需人工复核完整材料。"
    return f"命中 {len(hits)} 条：" + "；".join(
        f"{rule['clause']}（{rule['advice']}）" for rule in hits
    )


_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS = {"abs": abs, "min": min, "max": max, "round": round, "sqrt": math.sqrt}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS:
        return _FUNCS[node.func.id](*[_eval_node(arg) for arg in node.args])
    raise ToolError("表达式包含不支持的语法")


def _tool_calc(args: dict[str, Any]) -> str:
    expression = str(args.get("expression") or "").strip()
    if not expression:
        return "缺少 expression 参数"
    try:
        value = _eval_node(ast.parse(expression, mode="eval"))
    except (SyntaxError, ToolError, ZeroDivisionError, TypeError, ValueError) as exc:
        raise ToolError(f"计算失败：{exc}") from None
    return f"{expression} = {value:.6g}"


BUILTIN_EXECUTORS = {
    "market_quote": _tool_market_quote,
    "bond_quote": _tool_bond_quote,
    "financial_report": _tool_financial_report,
    "report_search": _tool_report_search,
    "compliance_check": _tool_compliance_check,
    "calc": _tool_calc,
}


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None,
               timeout: float = 8) -> tuple[dict[str, Any], dict[str, str]]:
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **(headers or {}),
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
            resp_headers = {k.lower(): v for k, v in response.headers.items()}
    except HTTPError as exc:
        raise ToolError(f"HTTP {exc.code}") from None
    except URLError as exc:
        raise ToolError(f"连接失败：{exc.reason}") from None
    if "text/event-stream" in resp_headers.get("content-type", ""):
        data_lines = [line[5:].strip() for line in raw.splitlines() if line.startswith("data:")]
        raw = data_lines[-1] if data_lines else ""
    if not raw:
        raise ToolError("服务返回空响应")
    try:
        return json.loads(raw), resp_headers
    except json.JSONDecodeError:
        raise ToolError("服务返回的不是 JSON") from None


def call_mcp_http(endpoint: str, tool_name: str, args: dict[str, Any]) -> str:
    """简化版 MCP 客户端：initialize（可选）+ tools/call，支持 JSON 与 SSE 响应。"""
    if not endpoint.startswith(("http://", "https://")):
        raise ToolError("该工具未配置可调用的 HTTP 端点")
    session: dict[str, str] = {}
    try:
        _, headers = _post_json(endpoint, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "agent-platform", "version": "0.1"}},
        }, timeout=5)
        if headers.get("mcp-session-id"):
            session["Mcp-Session-Id"] = headers["mcp-session-id"]
    except ToolError:
        pass  # 兼容不支持 initialize 的简化服务，直接尝试 tools/call
    response, _ = _post_json(endpoint, {
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": tool_name, "arguments": args},
    }, session, timeout=10)
    if "error" in response:
        error = response["error"]
        raise ToolError(str(error.get("message") if isinstance(error, dict) else error))
    result = response.get("result") or {}
    texts = [
        item.get("text", "") for item in result.get("content", [])
        if isinstance(item, dict) and item.get("type") == "text"
    ]
    return "\n".join(text for text in texts if text) or json.dumps(result, ensure_ascii=False)[:800]


def execute_tool(tool_name: str, args: dict[str, Any], meta: dict[str, Any]) -> str:
    if meta["endpoint"].startswith("builtin://"):
        executor = BUILTIN_EXECUTORS.get(tool_name)
        if not executor:
            raise ToolError(f"内置工具 {tool_name} 尚未实现")
        return executor(args)
    return call_mcp_http(meta["endpoint"], tool_name, args)


# ------------------------------------------------------------ 模型调用 --

LLM_BASE = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
LLM_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
MAX_STEPS = 6

DEFAULT_SYSTEM = (
    "你是企业内部 Agent 平台的智能体。只基于工具返回的事实回答，禁止编造数字与引用。"
    "输出结构固定为三段：结论 / 关键事实 / 口径与引用；末尾必须注明「本回答由 AI 生成，不构成投资建议」。"
    "工具不可用时明确说明缺什么数据，不要猜测。"
)


class LLMError(Exception):
    pass


def llm_available() -> bool:
    return bool(os.environ.get("DEEPSEEK_API_KEY", "").strip())


def llm_chat(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise LLMError("未配置 DEEPSEEK_API_KEY")
    body: dict[str, Any] = {
        "model": LLM_MODEL, "messages": messages, "temperature": 0.2, "max_tokens": 1000,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    try:
        response, _ = _post_json(
            f"{LLM_BASE}/chat/completions", body,
            {"Authorization": f"Bearer {key}"}, timeout=60,
        )
    except ToolError as exc:
        raise LLMError(str(exc)) from None
    if "error" in response:
        error = response["error"]
        raise LLMError(str(error.get("message") if isinstance(error, dict) else error))
    return response


def tool_schemas(agent_tools: list[str], catalog: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": catalog[name]["description"],
                "parameters": catalog[name]["input_schema"],
            },
        }
        for name in agent_tools
        if name in catalog
    ]


def execute_run_online(user: dict[str, Any], agent: sqlite3.Row, question: str,
                       catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
    agent_tools = [name for name in json.loads(agent["tools"]) if name in catalog]
    system_prompt = (agent["system_prompt"] or "").strip()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": f"{system_prompt}\n\n{DEFAULT_SYSTEM}".strip()},
        {"role": "user", "content": question},
    ]
    steps: list[dict[str, str]] = [{
        "type": "thought", "title": "加载 Agent",
        "detail": f"模型 {LLM_MODEL}；授权工具：{'、'.join(agent_tools) or '无'}",
    }]
    tokens = 0
    tool_failed = False
    planned: list[str] = []

    for step_no in range(1, MAX_STEPS + 1):
        response = llm_chat(messages, tool_schemas(agent_tools, catalog))
        tokens += int((response.get("usage") or {}).get("total_tokens") or 0)
        message = ((response.get("choices") or [{}])[0]).get("message") or {}
        content = (message.get("content") or "").strip()
        if content:
            steps.append({"type": "thought", "title": f"模型思考（第 {step_no} 步）",
                          "detail": content[:500]})
        calls = message.get("tool_calls") or []
        if not calls:
            answer = content or "模型没有返回内容，请重试。"
            if "不构成投资建议" not in answer:
                answer += "\n\n> 本回答由 AI 生成，不构成投资建议。"
            steps.append({"type": "final", "title": "生成答复",
                          "detail": f"共 {step_no} 步，模型 {LLM_MODEL}"})
            return {"status": "degraded" if tool_failed else "success", "steps": steps,
                    "answer": answer, "tokens": max(tokens, 1), "plan": planned, "model": LLM_MODEL}

        messages.append({"role": "assistant", "content": content, "tool_calls": calls})
        for call in calls:
            function = call.get("function") or {}
            name = function.get("name") or ""
            planned.append(name)
            try:
                args = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            meta = catalog.get(name)
            steps.append({"type": "action",
                          "title": f"调用 {meta['label'] if meta else name}",
                          "detail": f"MCP：{meta['mcp'] if meta else '未知'} · 参数 "
                                    f"{json.dumps(args, ensure_ascii=False)[:300]}"})
            if not meta:
                observation = f"工具 {name} 不在该 Agent 的授权范围内"
                tool_failed = True
            else:
                try:
                    observation = execute_tool(name, args, meta)
                except ToolError as exc:
                    observation = f"工具调用失败：{exc}"
                    tool_failed = True
            steps.append({"type": "observation", "title": "工具返回", "detail": observation[:800]})
            messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                             "content": observation[:2000]})

    steps.append({"type": "warning", "title": "达到最大步数",
                  "detail": f"已执行 {MAX_STEPS} 步，停止继续调用工具。"})
    return {"status": "degraded", "steps": steps,
            "answer": "已达到最大工具调用步数，请缩小问题范围后重试。", "tokens": max(tokens, 1),
            "plan": planned, "model": LLM_MODEL}


def execute_run_offline(user: dict[str, Any], agent: sqlite3.Row, question: str,
                        catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """无模型时的兜底：关键词规划 + 模拟工具结果，用于离线演示。"""
    agent_tools = json.loads(agent["tools"])
    steps: list[dict[str, str]] = [{
        "type": "thought", "title": "理解问题",
        "detail": f"离线模式：按关键词对照 Agent「{agent['name']}」的 {len(agent_tools)} 个工具做规划。",
    }]
    plan, summary = plan_tools(question, agent_tools, catalog)
    missing = [t for t in agent_tools if t not in catalog]
    if missing:
        steps.append({"type": "warning", "title": "工具不可用",
                      "detail": f"以下工具所属 MCP 已被禁用或删除：{', '.join(missing)}。"})

    observations, labels = [], []
    for tool in plan:
        meta = catalog[tool]
        args = {"keyword": re.sub(r"\s+", " ", question)[:24]}
        if tool in ("market_quote", "bond_quote", "financial_report"):
            codes = re.findall(r"\d{6}", question)
            args = {"symbol": codes[0] if codes else "300750"}
        steps.append({"type": "action", "title": f"调用 {meta['label']}",
                      "detail": f"MCP：{meta['mcp']}（{meta['transport']}）· 参数 {json.dumps(args, ensure_ascii=False)}"})
        observation = TOOL_OBSERVATIONS.get(tool, f"已调用 {meta['label']}（离线模拟）")
        steps.append({"type": "observation", "title": "工具返回", "detail": observation})
        observations.append(f"{meta['label']}：{observation}")
        labels.append(meta["label"])

    if not observations:
        steps.append({"type": "thought", "title": "无需工具", "detail": "未匹配到工具，直接基于模型知识回答。"})
    answer = (
        f"**结论**：{summary}\n\n**关键事实**\n"
        + ("\n".join(f"- {item}" for item in observations) if observations else "- 暂无工具事实。")
        + "\n\n**口径与引用**\n"
        + (f"- 数据源：{'、'.join(labels)}（离线模拟）" if labels else "- 未调用外部数据源")
        + "\n\n> 本回答由 AI 生成，不构成投资建议。"
    )
    steps.append({"type": "final", "title": "生成答复", "detail": "离线规则拼装，未调用在线模型。"})
    tokens = int(len(question) * 1.2 + sum(len(o) for o in observations) * 1.5 + len(answer) * 1.4)
    status = "success" if observations and not missing else "degraded"
    return {"status": status, "steps": steps, "answer": answer,
            "tokens": max(tokens, 1), "plan": plan, "model": "offline-mock"}


def execute_run(user: dict[str, Any], agent: sqlite3.Row, question: str,
                catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """入口：先做权限预检，再走在线模型，失败时降级到离线模拟。"""
    agent_tools = json.loads(agent["tools"])
    denied = [t for t in agent_tools
              if t in catalog and not allowed(user, catalog[t]["scope"])]
    if denied:
        detail = "、".join(f"{t}（需要 {catalog[t]['scope']}）" for t in denied)
        steps = [{
            "type": "blocked", "title": "权限拦截",
            "detail": f"当前角色 {user['role']} 缺少工具权限：{detail}。本次调用未触达工具网关。",
        }]
        return {"status": "denied", "steps": steps, "answer": "", "tokens": 0,
                "plan": [], "model": "-"}

    if llm_available():
        try:
            return execute_run_online(user, agent, question, catalog)
        except LLMError as exc:
            result = execute_run_offline(user, agent, question, catalog)
            result["status"] = "degraded"
            result["steps"].insert(1, {"type": "warning", "title": "模型降级",
                                       "detail": f"在线模型调用失败（{exc}），已降级为离线模拟。"})
            return result

    result = execute_run_offline(user, agent, question, catalog)
    result["steps"].insert(1, {"type": "warning", "title": "离线模式",
                               "detail": "未配置 DEEPSEEK_API_KEY，使用本地规则规划与模拟结果。"})
    return result


def plan_tools(question: str, agent_tools: list[str], catalog: dict[str, dict[str, Any]]) -> tuple[list[str], str]:
    """教学版「规划器」：关键词命中即选工具，未命中则用 Agent 的首个工具兜底。"""
    chosen: list[str] = []
    summary = "已基于可用工具返回结果汇总，详见下方事实与引用。"
    matched = False
    for keywords, tools, text in INTENT_RULES:
        if not any(k in question for k in keywords):
            continue
        hit = [t for t in tools if t in agent_tools and t in catalog]
        if hit:
            if not matched:
                summary = text
                matched = True
            chosen.extend(hit)
    if not chosen and agent_tools:
        chosen = [t for t in agent_tools if t in catalog][:1]
    return list(dict.fromkeys(chosen))[:3], summary


# ------------------------------------------------------------------ 接口 --


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "index.html")


@app.get("/api/bootstrap")
def bootstrap(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with closing(connect()) as conn:
        users = [
            dict(r)
            for r in conn.execute(
                "SELECT u.id, u.name, u.title, u.role, u.tenant_id, t.name AS tenant_name "
                "FROM users u JOIN tenants t ON t.id = u.tenant_id ORDER BY u.tenant_id, u.role DESC"
            )
        ]
    return {
        "me": {k: user[k] for k in ("id", "name", "title", "role", "tenant_id", "tenant_name")},
        "users": users,
        "scopes": sorted(scopes_of(user)),
        "role_scopes": {k: sorted(v) for k, v in ROLE_SCOPES.items()},
        "llm": {
            "online": llm_available(),
            "model": LLM_MODEL if llm_available() else "offline-mock",
            "max_steps": MAX_STEPS,
        },
    }


@app.get("/api/overview")
def overview(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    tenant = user["tenant_id"]
    with closing(connect()) as conn:
        agents = []
        for r in conn.execute("SELECT * FROM agents WHERE tenant_id = ? ORDER BY updated_at DESC", (tenant,)):
            item = dict(r)
            item["tools"] = json.loads(item["tools"])
            item["creator_name"] = user_name(conn, item["created_by"])
            agents.append(item)
        mcps = [dict(r) for r in conn.execute(
            "SELECT * FROM mcp_servers WHERE tenant_id = ? ORDER BY created_at DESC", (tenant,))]
        runs = []
        for r in conn.execute("SELECT * FROM runs WHERE tenant_id = ? ORDER BY created_at DESC LIMIT 8", (tenant,)):
            item = dict(r)
            item["steps"] = json.loads(item["steps"])
            runs.append(item)
        audit_rows = [dict(r) for r in conn.execute(
            "SELECT * FROM audit WHERE tenant_id = ? ORDER BY id DESC LIMIT 20", (tenant,))]
        tool_map = tenant_tools(conn, tenant)
        stats = dict(conn.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) AS published, "
            "SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending "
            "FROM agents WHERE tenant_id = ?", (tenant,)).fetchone())
        run_stats = conn.execute(
            "SELECT COUNT(*) AS runs, COALESCE(AVG(latency_ms), 0) AS avg_latency, "
            "SUM(CASE WHEN status = 'denied' THEN 1 ELSE 0 END) AS denied "
            "FROM runs WHERE tenant_id = ?", (tenant,)).fetchone()
    tools = [
        {**v, "allowed": allowed(user, v["scope"])}
        for v in tool_map.values()
    ]
    return {
        "agents": agents,
        "mcps": mcps,
        "tools": tools,
        "runs": runs,
        "audit": audit_rows,
        "stats": {
            "agents": stats["total"] or 0,
            "published": stats["published"] or 0,
            "pending": stats["pending"] or 0,
            "runs": run_stats["runs"] or 0,
            "avg_latency": int(run_stats["avg_latency"] or 0),
            "denied": run_stats["denied"] or 0,
            "mcps": len(mcps),
        },
    }


def user_name(conn: sqlite3.Connection, user_id: str) -> str:
    row = conn.execute("SELECT name FROM users WHERE id = ?", (user_id,)).fetchone()
    return row["name"] if row else user_id


@app.post("/api/agents")
def create_agent(payload: AgentIn, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, {"admin", "developer"})
    with closing(connect()) as conn:
        catalog = tenant_tools(conn, user["tenant_id"])
        unknown = [t for t in payload.tools if t not in catalog]
        if unknown:
            raise HTTPException(status_code=400, detail=f"工具未注册或已禁用：{', '.join(unknown)}")
        agent_id = f"ag-{uuid.uuid4().hex[:8]}"
        ts = now()
        conn.execute(
            "INSERT INTO agents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (agent_id, user["tenant_id"], payload.name.strip(), payload.description.strip(),
             payload.system_prompt.strip(), json.dumps(payload.tools, ensure_ascii=False),
             "draft", 1, user["id"], None, None, ts, ts),
        )
        audit(conn, user, "agent.create", payload.name, f"草稿，工具：{', '.join(payload.tools) or '无'}")
        conn.commit()
    return {"id": agent_id, "status": "draft"}


@app.post("/api/agents/{agent_id}/submit")
def submit_agent(agent_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, {"admin", "developer"})
    with closing(connect()) as conn:
        row = tenant_agent(conn, user, agent_id)
        if row["created_by"] != user["id"] and user["role"] != "admin":
            raise HTTPException(status_code=403, detail="只有创建人或租户管理员可以提交审核")
        if row["status"] not in ("draft", "rejected", "offline"):
            raise HTTPException(status_code=409, detail=f"当前状态 {row['status']} 不能提交审核")
        conn.execute("UPDATE agents SET status = 'pending', updated_at = ? WHERE id = ?", (now(), agent_id))
        audit(conn, user, "agent.submit", row["name"], "提交上架审核")
        conn.commit()
    return {"status": "pending"}


@app.post("/api/agents/{agent_id}/review")
def review_agent(agent_id: str, payload: ReviewIn, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, {"admin"})
    if payload.decision not in ("publish", "reject"):
        raise HTTPException(status_code=400, detail="decision 只能是 publish 或 reject")
    with closing(connect()) as conn:
        row = tenant_agent(conn, user, agent_id)
        if row["status"] != "pending":
            raise HTTPException(status_code=409, detail="只有待审核的 Agent 可以审批")
        if payload.decision == "publish":
            conn.execute(
                "UPDATE agents SET status = 'published', version = version + 1, reviewed_by = ?, "
                "review_note = ?, updated_at = ? WHERE id = ?",
                (user["id"], payload.note, now(), agent_id),
            )
            action, detail = "agent.publish", f"审核通过，版本 v{row['version'] + 1}"
        else:
            conn.execute(
                "UPDATE agents SET status = 'rejected', reviewed_by = ?, review_note = ?, updated_at = ? WHERE id = ?",
                (user["id"], payload.note, now(), agent_id),
            )
            action, detail = "agent.reject", f"驳回：{payload.note or '未填写原因'}"
        audit(conn, user, action, row["name"], detail)
        conn.commit()
    return {"status": "published" if payload.decision == "publish" else "rejected"}


@app.post("/api/agents/{agent_id}/offline")
def offline_agent(agent_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with closing(connect()) as conn:
        row = tenant_agent(conn, user, agent_id)
        if row["created_by"] != user["id"] and user["role"] != "admin":
            raise HTTPException(status_code=403, detail="只有创建人或租户管理员可以下线")
        if row["status"] != "published":
            raise HTTPException(status_code=409, detail="只有已上线的 Agent 可以下线")
        conn.execute("UPDATE agents SET status = 'offline', updated_at = ? WHERE id = ?", (now(), agent_id))
        audit(conn, user, "agent.offline", row["name"], "主动下线")
        conn.commit()
    return {"status": "offline"}


@app.post("/api/mcp")
def create_mcp(payload: McpIn, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, {"admin", "developer"})
    scope = payload.scope.strip()
    if user["role"] != "admin" and scope not in ROLE_SCOPES["developer"]:
        raise HTTPException(
            status_code=403,
            detail=f"scope「{scope}」超出开发者权限域，请由管理员注册或先申请授权",
        )
    with closing(connect()) as conn:
        exists = conn.execute(
            "SELECT 1 FROM mcp_servers WHERE tenant_id = ? AND tool_name = ?",
            (user["tenant_id"], payload.tool_name),
        ).fetchone()
        if exists:
            raise HTTPException(status_code=409, detail="该工具名已存在")
        mcp_id = f"mcp-{uuid.uuid4().hex[:8]}"
        schema = {
            "type": "object",
            "properties": {"query": {"type": "string", "description": f"{payload.name} 的查询参数"}},
            "required": ["query"],
        }
        conn.execute(
            "INSERT INTO mcp_servers(id, tenant_id, name, transport, endpoint, scope, tool_name, "
            "tool_label, enabled, created_at, description, input_schema) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (mcp_id, user["tenant_id"], payload.name.strip(), payload.transport, payload.endpoint.strip(),
             payload.scope.strip(), payload.tool_name, payload.tool_label.strip() or payload.name.strip(),
             1 if user["role"] == "admin" else 0, now(),
             payload.description.strip() or f"{payload.name.strip()}（自定义 MCP）",
             json.dumps(schema, ensure_ascii=False)),
        )
        audit(conn, user, "mcp.create", payload.name,
              f"{payload.transport} · {payload.tool_name} · {'已启用' if user['role'] == 'admin' else '待管理员启用'}")
        conn.commit()
    return {"id": mcp_id, "enabled": user["role"] == "admin"}


@app.post("/api/mcp/{mcp_id}/toggle")
def toggle_mcp(mcp_id: str, payload: ToggleIn, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, {"admin"})
    with closing(connect()) as conn:
        row = conn.execute("SELECT * FROM mcp_servers WHERE id = ?", (mcp_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="MCP 服务不存在")
        if row["tenant_id"] != user["tenant_id"]:
            audit(conn, user, "security.cross_tenant_denied", mcp_id, "尝试操作其他租户的 MCP")
            conn.commit()
            raise HTTPException(status_code=403, detail="跨租户访问已拦截并记录审计")
        conn.execute("UPDATE mcp_servers SET enabled = ? WHERE id = ?", (1 if payload.enabled else 0, mcp_id))
        audit(conn, user, "mcp.enable" if payload.enabled else "mcp.disable", row["name"], row["endpoint"])
        conn.commit()
    return {"enabled": payload.enabled}


@app.post("/api/runs")
def create_run(payload: RunIn, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with closing(connect()) as conn:
        row = tenant_agent(conn, user, payload.agent_id)
        if row["status"] != "published":
            raise HTTPException(status_code=409, detail="只有已上线的 Agent 可以被调用")
        catalog = tenant_tools(conn, user["tenant_id"])
        started = time.perf_counter()
        try:
            result = execute_run(user, row, payload.question.strip(), catalog)
        except ToolError as exc:
            raise HTTPException(status_code=502, detail=f"运行失败：{exc}") from None
        latency = int((time.perf_counter() - started) * 1000)
        run_id = f"run-{uuid.uuid4().hex[:8]}"
        conn.execute(
            "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, user["tenant_id"], row["id"], row["name"], user["id"], payload.question.strip(),
             result["answer"], json.dumps(result["steps"], ensure_ascii=False), result["status"],
             result["tokens"], latency, now(), result.get("model", "")),
        )
        if result["status"] == "denied":
            audit(conn, user, "run.denied", row["name"], "工具权限不足，运行时拦截")
        conn.commit()
    return {
        "id": run_id,
        "status": result["status"],
        "steps": result["steps"],
        "answer": result["answer"],
        "tokens": result["tokens"],
        "latency_ms": latency,
        "model": result.get("model", ""),
    }


# ------------------------------------------------------------------ 启动 --


def main() -> None:
    parser = argparse.ArgumentParser(description="金融 Agent 平台（教学版）")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--reset", action="store_true", help="清空演示数据后重建")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    init_db(reset=args.reset)
    if not DB_PATH.exists():
        init_db()
    url = f"http://127.0.0.1:{args.port}/"
    print(f"==> 金融 Agent 平台控制台：{url}")
    print("    演示身份：张敏（t-sec 管理员）/ 李想（开发者）/ 王研（研究员）/ 陈璐（t-am 管理员）")
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


init_db()

if __name__ == "__main__":
    main()
