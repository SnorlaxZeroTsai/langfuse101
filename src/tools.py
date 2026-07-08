"""Agent 可呼叫的工具 (Stage 2+)。

每個工具函式用 @observe(as_type="tool") 裝飾 → 被呼叫時會在 trace 上
自動變成一個 "tool" 型別的 observation,input/output 自動記錄。

TOOL_SCHEMAS 是給 OpenAI function-calling 用的宣告;TOOL_REGISTRY 讓 agent
用名字 dispatch 到實際函式。真實場景(如你的 MCP Gateway)裡,這層 dispatch
就是把 model 想呼叫的工具名對應到後端實作的地方。
"""

import ast
import json
import operator
from datetime import datetime, timezone

from langfuse import observe


# --- 安全的算式求值:只允許數字與四則/次方,不用 eval 以免任意程式執行 ---
_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
}


def _safe_eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("只支援數字與 + - * / % ** 運算")


@observe(as_type="tool")
def calculator(expression: str) -> str:
    """計算一個算術表達式,例如 '23 * 19'。"""
    result = _safe_eval(ast.parse(expression, mode="eval").body)
    return str(result)


@observe(as_type="tool")
def get_current_time() -> str:
    """回傳目前的 UTC 時間 (ISO 8601)。"""
    return datetime.now(timezone.utc).isoformat()


# mock 搜尋:回傳寫死的結果,避免依賴外部 API。之後可替換成真的搜尋或 MCP 呼叫。
_FAKE_INDEX = {
    "langfuse": "Langfuse 是一個開源的 LLM observability 平台,提供 tracing、評估、prompt 管理與 cost 追蹤。",
    "opentelemetry": "OpenTelemetry (OTel) 是可觀測性資料 (traces/metrics/logs) 的開放標準與工具集。",
    "mcp": "Model Context Protocol (MCP) 是讓 LLM 應用以標準化方式連接工具與資料來源的開放協定。",
}


@observe(as_type="tool")
def search_web(query: str) -> str:
    """(mock) 依關鍵字回傳一段預先寫好的說明文字。"""
    q = query.lower()
    for key, text in _FAKE_INDEX.items():
        if key in q:
            return text
    return f"(mock 搜尋) 找不到關於 '{query}' 的結果。已知主題:{', '.join(_FAKE_INDEX)}。"


# --- 給 OpenAI function-calling 的工具宣告 ---
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "計算一個算術表達式,支援 + - * / % ** 與括號。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "要計算的算式,例如 '23 * 19'"}
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "取得目前的 UTC 時間。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "依關鍵字搜尋網路資訊(此為示範用的 mock)。",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "搜尋關鍵字"}},
                "required": ["query"],
            },
        },
    },
]

# 名稱 → 實作,供 agent loop dispatch。
TOOL_REGISTRY = {
    "calculator": calculator,
    "get_current_time": get_current_time,
    "search_web": search_web,
}


def dispatch(name: str, arguments_json: str) -> str:
    """依 model 給的工具名與 JSON 參數呼叫對應工具,回傳字串結果。"""
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        return f"錯誤:未知的工具 '{name}'"
    try:
        kwargs = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError:
        return f"錯誤:工具參數不是合法 JSON: {arguments_json!r}"
    try:
        return str(fn(**kwargs))
    except Exception as exc:  # noqa: BLE001 — 把工具錯誤回饋給 model,而非中斷整個 loop
        return f"工具執行錯誤: {exc}"


# 給 system prompt 用的工具說明字串(Stage 5 會改由 Langfuse prompt 帶入)。
TOOLS_DESC = "\n".join(
    f"- {s['function']['name']}: {s['function']['description']}" for s in TOOL_SCHEMAS
)
