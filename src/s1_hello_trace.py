"""Stage 1 — 第一條 Trace(最小可行)。

學習重點:
  1. @observe 讓一個 Python 函式自動變成一個 trace 的 root span
     (自動抓 input 參數、return 值、耗時、例外)。
  2. `from langfuse.openai import openai` 是 OpenAI SDK 的 drop-in 替代:
     只換 import,LLM 呼叫就自動變成 span 底下的一個 "generation",
     連 model、messages、輸出、token usage、latency、cost 都自動記錄。

執行:  python src/s1_hello_trace.py
然後到 http://localhost:3000 的 Traces 頁,找到名為 `ask` 的 trace 展開來看。

Socratic(邊做邊想):
  - 為什麼 generation 是 trace 底下的一個 observation,而不是 trace 本身?
  - 如果把兩個 openai 呼叫放進同一個 @observe 函式,UI 的樹會長怎樣?(自己試試看)
"""

from langfuse import observe

from config import MODEL, get_langfuse
from langfuse.openai import openai  # drop-in:不是 `import openai`


@observe()  # 這層函式 → trace 的 root span
def ask(question: str) -> str:
    resp = openai.chat.completions.create(  # 這個呼叫 → root span 底下的一個 generation
        model=MODEL,
        messages=[{"role": "user", "content": question}],
    )
    return resp.choices[0].message.content


if __name__ == "__main__":
    answer = ask("用一句話解釋什麼是 distributed tracing")
    print(answer)

    # 短命 CLI 程式:結束前務必 flush,把緩衝中的資料送到 Langfuse,否則可能來不及送出。
    get_langfuse().flush()
    print("\n✔ 已送出 trace,到 http://localhost:3000 的 Traces 頁查看 `ask`。")
