"""Stage 4 — Scores 與評估(品質量測)。

Score 掛在 trace(或 observation)上,用來量測回答品質、日後篩出爛回答。
三種來源、各有適用時機:

  (a) 使用者手動回饋:REPL 問 👍/👎。→ 線上即時、代表真實使用者滿意度。
  (b) 程式規則:格式/長度等可用程式判斷的檢查。→ 便宜、可即時或離線大量跑。
  (c) LLM-as-judge:另叫一次 LLM 評「有沒有回答到問題」。→ 較貴、常離線批次跑。

取得目前 trace_id:在 @observe context 內用 langfuse.get_current_trace_id()。
我們用 score_current_trace()(context 內)與 create_score(trace_id=...)(context 外)兩種都示範。

執行:  python src/s4_scores.py
每輪回答後會請你打 👍/👎,並自動附上 format-ok 與 relevance 兩個 score。
到 UI 的 trace 上看三個 score;也可在 Traces 頁用 score 篩選 / 排序找低分 trace。
"""

from langfuse import observe

from config import MODEL, get_langfuse
from langfuse.openai import openai
from s2_agent import agent_run


@observe(name="llm-judge")
def judge_relevance(question: str, answer: str) -> float:
    """LLM-as-judge:回傳 0~1,答案是否有回答到問題。"""
    resp = openai.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": "你是嚴格的評審。判斷答案是否有回答到問題。只輸出 0 到 1 之間的一個數字。",
            },
            {"role": "user", "content": f"問題:{question}\n答案:{answer}\n相關度(0-1):"},
        ],
    )
    raw = (resp.choices[0].message.content or "").strip()
    try:
        return max(0.0, min(1.0, float(raw.split()[0])))
    except (ValueError, IndexError):
        return 0.0


@observe(name="answer-and-score")
def answer_and_score(question: str):  # -> (answer, trace_id)
    """跑 agent → 打三種 score。整個過程在同一條 trace 內。"""
    langfuse = get_langfuse()
    answer = agent_run(question)

    # (b) 程式規則 score:答案非空且夠長 → 1,否則 0。
    format_ok = 1.0 if answer and len(answer.strip()) >= 10 else 0.0
    langfuse.score_current_trace(
        name="format-ok", value=format_ok, data_type="NUMERIC",
        comment="規則:答案非空且長度>=10",
    )

    # (c) LLM-as-judge score。
    relevance = judge_relevance(question, answer)
    langfuse.score_current_trace(
        name="relevance", value=relevance, data_type="NUMERIC",
        comment="LLM-as-judge 評估答案相關度",
    )

    # 記下 trace_id,離開 context 後(例如取得使用者回饋)還能用 create_score 補打。
    trace_id = langfuse.get_current_trace_id()
    return answer, trace_id


def main():
    langfuse = get_langfuse()
    print("Stage 4:每次回答後請打 👍(y)/👎(n)。quit 離開。\n")

    while True:
        try:
            question = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question or question.lower() in {"quit", "exit", "q"}:
            if question.lower() in {"quit", "exit", "q"}:
                break
            continue

        answer, trace_id = answer_and_score(question)
        print(f"助理> {answer}")

        # (a) 使用者手動回饋:在 trace context 外,用 trace_id 補打 score。
        fb = input("這個回答有幫助嗎? (y/n)> ").strip().lower()
        if fb in {"y", "n"}:
            langfuse.create_score(
                name="user-feedback",
                value=1.0 if fb == "y" else 0.0,
                trace_id=trace_id,
                data_type="NUMERIC",
                comment="使用者 👍/👎",
            )
        print()

    langfuse.flush()
    print("\n✔ 到 UI 的 trace 上看 format-ok / relevance / user-feedback 三個 score。")


if __name__ == "__main__":
    main()
