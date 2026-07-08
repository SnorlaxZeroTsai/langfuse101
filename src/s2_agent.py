"""Stage 2 — 手刻 Tool-Calling Agent + 巢狀 Span(核心)。

一次 agent 執行 = 一棵有結構的 trace:
    agent-run (root span, @observe)
    ├── generation  (LLM 決定要呼叫哪個工具)   ← langfuse.openai wrapper 自動記錄
    ├── tool        (實際執行工具)             ← tools.py 的 @observe(as_type="tool")
    ├── generation  (LLM 看到工具結果後再決策)
    └── ...          直到 LLM 給出最終答案(沒有 tool_calls)

學習重點 — 自動 vs 手動埋點:
  * 自動:generation(wrapper)、tool span(工具的 decorator)都不用手寫。
  * 手動:整體 input/output、loop 輪數等 metadata,用 update_current_span 補上。
    → 在真實 MCP agent 上,你會想手動記錄:使用者原始意圖、選路決策、重試次數等。

執行:  python src/s2_agent.py
試問需要用到工具的問題,例如:「現在幾點?另外幫我算 23*19」

Socratic:如果不用 wrapper,純手動要怎麼建一個 generation?
  → 用 `with langfuse.start_as_current_observation(as_type="generation", name=..., model=...) as gen:`
    呼叫 LLM 後 `gen.update(output=..., usage_details=...)`。wrapper 就是幫你做了這些。
"""

import json

from langfuse import observe

from config import MODEL, get_langfuse
from langfuse.openai import openai
from tools import TOOL_SCHEMAS, TOOLS_DESC, dispatch

MAX_TURNS = 6  # 防止 model 無限呼叫工具的保險絲

SYSTEM_PROMPT = (
    "你是一個研究助理 agent。可以使用以下工具來回答問題,"
    "需要時才呼叫工具,取得資料後用繁體中文簡潔回答。\n"
    f"可用工具:\n{TOOLS_DESC}"
)


@observe(name="agent-run")  # root span:包住整個 loop
def agent_run(question: str) -> str:
    langfuse = get_langfuse()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    final_answer = ""
    for turn in range(1, MAX_TURNS + 1):
        # 每次 create 都是 root span 底下的一個 generation(wrapper 自動記錄)。
        resp = openai.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
        )
        msg = resp.choices[0].message
        messages.append(msg)  # 把 assistant 的回覆(含 tool_calls)加回對話

        if not msg.tool_calls:
            # 沒有要呼叫工具 → 這就是最終答案,結束 loop。
            final_answer = msg.content or ""
            break

        # model 想呼叫一個以上的工具:逐一執行,結果 append 回 messages 供下一輪參考。
        for call in msg.tool_calls:
            result = dispatch(call.function.name, call.function.arguments)  # tool span 自動產生
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result,
                }
            )
    else:
        # for-else:跑滿 MAX_TURNS 都沒收斂
        final_answer = "(達到最大輪數上限,未能得到最終答案)"
        turn = MAX_TURNS

    # 手動補上整體 in/out 與 metadata —— 這些 wrapper 不會自動幫你標在 root span 上。
    langfuse.update_current_span(
        input=question,
        output=final_answer,
        metadata={"turns": turn},
    )
    return final_answer


if __name__ == "__main__":
    q = "現在幾點(UTC)?另外幫我算 23*19,再簡單告訴我 Langfuse 是什麼。"
    print(f"Q: {q}\n")
    print(f"A: {agent_run(q)}")

    get_langfuse().flush()
    print("\n✔ 已送出 trace。到 Traces 頁展開 `agent-run`,看巢狀的 generation 與 tool span。")
