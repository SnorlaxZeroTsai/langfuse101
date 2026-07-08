"""Stage 7.3 — A2A(Agent2Agent)跨邊界 tracing。★ 帶註解骨架 ★

★ 最貼近你 MCP Gateway / 多 agent 部署的一節 ★

現況(先講清楚):
  Langfuse 沒有 A2A 官方整合;A2A 協定(JSON-RPC over HTTP)spec 本身也沒有內建 observability。
  所以這不是「接一個套件」,而是回到分散式 tracing 的基本功——**自己在協定邊界傳 trace context**。

問題:agent A 透過 A2A 呼叫 agent B(跨程序/跨網路)。若不做任何事,
  A 的 trace 和 B 的 trace 會是**兩棵獨立的樹**,你看不到端到端。這叫「斷鏈」,是預設行為。

解法(通用招式,A2A / MCP / 任何 RPC 都一樣):
  1. caller 端:從目前 span 取出 W3C `traceparent`,塞進呼叫的 metadata/header 帶過去。
  2. callee 端:從 metadata 取出 traceparent,用它當 parent context 開 span。
  → 兩端於是接成同一條 trace。學會這招,換任何 OTel-based 工具都通用(遷移價值極高)。

前置(有環境時):pip install a2a-sdk(或你實際用的 A2A 實作)
本檔用「函式呼叫」模擬跨邊界,把「要傳什麼、在哪端接」講清楚,不綁特定 A2A SDK 版本。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import get_langfuse  # noqa: E402

from opentelemetry import trace  # noqa: E402  (Langfuse v4 底層就是 OTel,已隨 langfuse 裝好)
from opentelemetry.propagate import extract, inject  # noqa: E402


def caller_side(question: str) -> dict:
    """Agent A:把目前 trace context 注入要送給 B 的 A2A 請求。"""
    langfuse = get_langfuse()
    # 用 Langfuse 開一個 span 當「呼叫 B」這段工作。
    with langfuse.start_as_current_observation(as_type="span", name="a2a-call-to-B") as span:
        span.update(input=question)

        # 關鍵:把 W3C traceparent 注入一個 carrier(dict),它會被放進 A2A 請求的 metadata。
        carrier: dict = {}
        inject(carrier)  # OTel 會把目前 context 的 traceparent 寫進 carrier

        # 真實情況:這個 carrier 會塞進 A2A JSON-RPC 請求,例如:
        #   request = {"jsonrpc": "2.0", "method": "tasks/send",
        #              "params": {"message": question, "metadata": carrier}}
        #   response = a2a_client.send(request)   # ← 送到 agent B
        # 這裡直接呼叫 callee 模擬「送過去」。
        a2a_request = {"message": question, "metadata": carrier}
        response = callee_side(a2a_request)

        span.update(output=response)
        return response


def callee_side(a2a_request: dict) -> dict:
    """Agent B:從收到的 A2A 請求取出 traceparent,接上同一條 trace 再開 span。"""
    langfuse = get_langfuse()

    # 關鍵:從請求 metadata 取出 traceparent,還原成 parent context。
    carrier = a2a_request.get("metadata", {})
    parent_ctx = extract(carrier)  # 沒有 traceparent 時會是空 context → 就會斷鏈(這正是坑)

    # 用 parent context 開 span → B 的工作接在 A 的 trace 底下,而非另起一棵樹。
    tracer = trace.get_tracer("a2a-agent-b")
    with tracer.start_as_current_span("a2a-agent-B-work", context=parent_ctx):
        # ... B 在這裡做事(可能又呼叫 LLM / 再呼叫 agent C,同樣方式往下傳)...
        result = {"answer": f"B 處理了:{a2a_request['message']}"}
        return result


def main():
    print("模擬 A2A 跨邊界 tracing:A 呼叫 B,traceparent 透過請求 metadata 傳遞。")
    resp = caller_side("查詢多雲 gateway 的健康狀態")
    print("回應:", resp)

    get_langfuse().flush()
    print(
        "\n✔ 到 Langfuse 看:a2a-call-to-B 與 a2a-agent-B-work 應在**同一條 trace**(未斷鏈)。"
        "\n  對照實驗:把 callee_side 裡的 extract(carrier) 換成不帶 context,"
        "\n  兩段就會變成兩棵獨立 trace——這就是不傳 traceparent 的後果。"
    )
    print(
        "\n已知坑:A2A spec 無標準 trace header 欄位,兩端要約定 metadata 位置;"
        "\n升級協定版本、或各端獨立 sampling 時都可能再度斷鏈。"
    )


if __name__ == "__main__":
    main()
