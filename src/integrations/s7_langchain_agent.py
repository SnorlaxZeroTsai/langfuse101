"""Stage 7.4 — LangChain 整合。可跑範例。

整合模式:框架原生 callback。把 Langfuse 的 CallbackHandler 當一個 callback
傳進 invoke(config={"callbacks": [handler]}),LangChain 每個 chain/tool/LLM 步驟
就自動轉成巢狀 span 送進 Langfuse(並存:可同時掛 LangSmith)。

刻意用 LangChain 重建 README Stage 2 的 tool-calling agent(同樣三個工具),
好讓你**對照**:框架自動產生的 trace 樹 vs 你 Stage 2 手刻的樹。
  - 自動:省事、邊界切得細,但要標自訂業務語意較難插入。
  - 手刻:麻煩,但完全可控。→ 這就是為什麼 Stage 2 要先手刻過一遍。

前置:  pip install -r requirements-integrations.txt(含 langchain / langchain-openai)
執行:  cd src/integrations && python s7_langchain_agent.py

已知坑:
  - LangChain >0.3 在 async/serverless 會把 callback 背景化;程序結束前要 flush/等待。
  - 並發下重用同一個 handler 拿 last_trace_id 會混;每請求給新 handler 較安全。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import MODEL, get_langfuse  # noqa: E402

from langchain.agents import AgentExecutor, create_tool_calling_agent  # noqa: E402
from langchain_core.prompts import ChatPromptTemplate  # noqa: E402
from langchain_core.tools import tool  # noqa: E402
from langchain_openai import ChatOpenAI  # noqa: E402
from langfuse.langchain import CallbackHandler  # noqa: E402


# 對應 Stage 2 的三個工具(這裡用 LangChain 的 @tool 宣告)。
@tool
def calculator(expression: str) -> str:
    """計算一個算術表達式,例如 '23 * 19'。"""
    import ast
    import operator

    ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
           ast.USub: operator.neg}

    def ev(n):
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, ast.BinOp):
            return ops[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp):
            return ops[type(n.op)](ev(n.operand))
        raise ValueError("只支援數字與四則運算")

    return str(ev(ast.parse(expression, mode="eval").body))


@tool
def get_current_time() -> str:
    """回傳目前的 UTC 時間 (ISO 8601)。"""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


@tool
def search_web(query: str) -> str:
    """(mock) 依關鍵字回傳預先寫好的說明。"""
    idx = {
        "langfuse": "Langfuse 是開源 LLM observability 平台。",
        "mcp": "MCP 是讓 LLM 應用標準化連接工具/資料的開放協定。",
    }
    for k, v in idx.items():
        if k in query.lower():
            return v
    return f"(mock) 找不到 '{query}'。"


def main():
    llm = ChatOpenAI(model=MODEL, temperature=0)
    tools = [calculator, get_current_time, search_web]
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "你是研究助理 agent,需要時才呼叫工具,用繁體中文簡潔回答。"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),  # tool-calling agent 需要的暫存區
        ]
    )
    agent = create_tool_calling_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools)

    # 關鍵一行:把 Langfuse handler 當 callback 傳進去,整棵 trace 自動產生。
    handler = CallbackHandler()
    question = "現在幾點(UTC)?再幫我算 23*19,並簡述 MCP 是什麼。"
    result = executor.invoke({"input": question}, config={"callbacks": [handler]})

    print(f"Q: {question}\nA: {result['output']}")
    get_langfuse().flush()
    print(
        "\n✔ 到 Langfuse 看 LangChain 自動產生的 trace 樹。"
        "\n  對照練習:和 README Stage 2 手刻的 `agent-run` 樹比一比,哪個資訊多、哪個好標自訂語意。"
    )


if __name__ == "__main__":
    main()
