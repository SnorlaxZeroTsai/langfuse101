"""Stage 6 — Capstone:全套整合的研究助理 agent CLI。

把 Stage 2~5 全部串起來的完整 agent,一次執行同時帶上:
  * 巢狀 span/generation(Stage 2)——手刻 tool-calling loop
  * session + user + tags(Stage 3)——多輪 REPL 共用一個 session
  * 三種 score(Stage 4)——format-ok / relevance(LLM-judge)/ user-feedback(手動)
  * 從 Langfuse 拉的版本化 prompt(Stage 5)——generation 連結 prompt 版本
  * cost / token(自動)——langfuse.openai wrapper 依 OpenAI 內建價目自動算

執行前置:先建立 prompt 一次   python src/s5_prompts.py --seed
執行:                        python src/s6_capstone.py

驗收(端到端):做一次多輪對話後,到 UI 確認同一個 session 下能看到
  traces → 巢狀 spans/generations → 3 種 scores → prompt 版本連結 → cost 匯總。
再到 Dashboard 看跨多條 trace 的 cost / token / latency 匯總。
"""

import uuid

from langfuse import observe, propagate_attributes

from config import MODEL, get_langfuse
from langfuse.openai import openai
from tools import TOOL_SCHEMAS, TOOLS_DESC, dispatch

PROMPT_NAME = "agent-system"
USER_ID = "engineer-01"
MAX_TURNS = 6


@observe(name="llm-judge")
def judge_relevance(question: str, answer: str) -> float:
    resp = openai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "你是嚴格評審。只輸出 0 到 1 之間的一個數字。"},
            {"role": "user", "content": f"問題:{question}\n答案:{answer}\n相關度(0-1):"},
        ],
    )
    raw = (resp.choices[0].message.content or "").strip()
    try:
        return max(0.0, min(1.0, float(raw.split()[0])))
    except (ValueError, IndexError):
        return 0.0


@observe(name="agent-run")
def agent_run(question: str):
    """完整 agent:拉 prompt → tool-calling loop → 自動打 format-ok / relevance score。"""
    langfuse = get_langfuse()

    prompt = langfuse.get_prompt(PROMPT_NAME, label="production", type="chat")
    messages = list(prompt.compile(tools_desc=TOOLS_DESC)) + [
        {"role": "user", "content": question}
    ]

    final_answer = ""
    for turn in range(1, MAX_TURNS + 1):
        resp = openai.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            langfuse_prompt=prompt,
        )
        msg = resp.choices[0].message
        messages.append(msg)
        if not msg.tool_calls:
            final_answer = msg.content or ""
            break
        for call in msg.tool_calls:
            result = dispatch(call.function.name, call.function.arguments)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
    else:
        final_answer = "(達到最大輪數上限)"
        turn = MAX_TURNS

    langfuse.update_current_span(input=question, output=final_answer, metadata={"turns": turn})

    # 程式規則 score + LLM-judge score(都掛在這條 trace 上)。
    langfuse.score_current_trace(
        name="format-ok",
        value=1.0 if final_answer and len(final_answer.strip()) >= 10 else 0.0,
        data_type="NUMERIC",
    )
    langfuse.score_current_trace(
        name="relevance", value=judge_relevance(question, final_answer), data_type="NUMERIC"
    )

    return final_answer, langfuse.get_current_trace_id()


def main():
    langfuse = get_langfuse()
    session_id = str(uuid.uuid4())
    print(f"研究助理 agent(capstone)。session={session_id}。quit 離開。")
    print("提示:先確認已跑過 `python src/s5_prompts.py --seed` 建立 prompt。\n")

    while True:
        try:
            question = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            continue
        if question.lower() in {"quit", "exit", "q"}:
            break

        with propagate_attributes(
            session_id=session_id, user_id=USER_ID, tags=["capstone"]
        ):
            answer, trace_id = agent_run(question)
        print(f"助理> {answer}")

        fb = input("有幫助嗎? (y/n)> ").strip().lower()
        if fb in {"y", "n"}:
            langfuse.create_score(
                name="user-feedback",
                value=1.0 if fb == "y" else 0.0,
                trace_id=trace_id,
                data_type="NUMERIC",
            )
        print()

    langfuse.flush()
    print(
        f"\n✔ Session {session_id} 結束。到 UI:"
        "\n  1) Sessions 頁看這串對話;展開任一 trace 看巢狀 span/generation。"
        "\n  2) trace 上看 3 種 score 與 prompt 版本連結、generation 的 cost/token。"
        "\n  3) Dashboard 看跨 trace 的 cost / token / latency 匯總。"
    )


if __name__ == "__main__":
    main()
