"""Stage 5 — Prompt Management(版本化 prompt)。

把 system prompt 從 code 抽到 Langfuse 管理:
  * 版本化 + label(production / latest):改 prompt 不用改 code、不用重新部署。
  * trace ↔ prompt 連結:generation 記錄「用了哪個 prompt 的哪一版」,
    日後能分析「哪版 prompt 表現較好」(配合 Stage 4 的 score)。

用法:
  先建立 prompt(只需一次,或改版時):  python src/s5_prompts.py --seed
  跑 agent(從 Langfuse 拉 prompt):     python src/s5_prompts.py

改版練習:到 UI 的 Prompts → agent-system 編輯內容、存成新版並設 production label,
不改任何 code 再跑一次,觀察 agent 行為改變。

Socratic:為什麼 generation 要連到 prompt 版本,而不只是把文字塞進去就好?
  → 因為要能回答「v3 prompt 的平均 relevance 比 v2 高嗎?」這類問題,
    需要 prompt 版本這個維度來 group by。
"""

import sys

from langfuse import observe

from config import MODEL, get_langfuse
from langfuse.openai import openai
from tools import TOOL_SCHEMAS, TOOLS_DESC, dispatch

PROMPT_NAME = "agent-system"
MAX_TURNS = 6


def seed_prompt():
    """在 Langfuse 建立/更新 agent-system prompt(chat 型別,含 {{tools_desc}} 變數)。"""
    langfuse = get_langfuse()
    langfuse.create_prompt(
        name=PROMPT_NAME,
        type="chat",
        prompt=[
            {
                "role": "system",
                "content": (
                    "你是一個研究助理 agent。需要時才呼叫工具,取得資料後用繁體中文簡潔回答。\n"
                    "可用工具:\n{{tools_desc}}"
                ),
            }
        ],
        labels=["production"],  # 設為 production,get_prompt(label="production") 才拿得到
    )
    print(f"✔ 已建立/更新 prompt '{PROMPT_NAME}' 並標記 production。到 UI 的 Prompts 頁查看。")


@observe(name="agent-run-managed")
def agent_run(question: str) -> str:
    langfuse = get_langfuse()

    # 從 Langfuse 拉 production 版 prompt,compile 帶入工具說明變數。
    prompt = langfuse.get_prompt(PROMPT_NAME, label="production", type="chat")
    system_messages = prompt.compile(tools_desc=TOOLS_DESC)

    messages = list(system_messages) + [{"role": "user", "content": question}]

    final_answer = ""
    for turn in range(1, MAX_TURNS + 1):
        resp = openai.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            langfuse_prompt=prompt,  # 把 generation 連結到這個 prompt 版本
        )
        msg = resp.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            final_answer = msg.content or ""
            break
        for call in msg.tool_calls:
            result = dispatch(call.function.name, call.function.arguments)
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": result}
            )
    else:
        final_answer = "(達到最大輪數上限)"
        turn = MAX_TURNS

    langfuse.update_current_span(input=question, output=final_answer, metadata={"turns": turn})
    return final_answer


if __name__ == "__main__":
    if "--seed" in sys.argv:
        seed_prompt()
    else:
        q = "簡單告訴我 OpenTelemetry 是什麼,再算 12*12。"
        print(f"Q: {q}\n")
        print(f"A: {agent_run(q)}")
        print(
            "\n✔ 到 trace 展開 generation,看它連結到的 prompt 名稱與版本。"
            "\n  (若報錯找不到 prompt,先跑一次 `python src/s5_prompts.py --seed`)"
        )
    get_langfuse().flush()
