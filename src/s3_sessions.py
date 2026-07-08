"""Stage 3 — Sessions 與 Users(對話維度)。

三層關係:
    Session   = 一串相關的對話(整個 REPL 這次的多輪問答)
      └ Trace     = session 裡的一次執行(每問一句 = 一條 agent-run trace)
          └ Observation = trace 裡的一個步驟(generation / tool span)

propagate_attributes(session_id=..., user_id=..., tags=...) 會把這些屬性
下傳到 context 內建立的所有 observation,所以整段對話會被 Langfuse 串在同一個
session 底下,也能用 user_id / tag 篩選。

執行:  python src/s3_sessions.py
輸入多句問題(quit 離開),然後到 UI 的 Sessions 頁看它們串在同一個 session。

Socratic:什麼情境該用 session、什麼情境一條 trace 就夠?
  → 需要跨多次請求追同一個使用者的對話脈絡(chatbot、多輪 agent)→ session;
    單次、無狀態的呼叫(一次分類 / 一次摘要)→ 一條 trace 即可。
"""

import uuid

from langfuse import propagate_attributes

from config import get_langfuse
from s2_agent import agent_run  # 重用 Stage 2 的 agent loop

USER_ID = "engineer-01"


def main():
    # 整個 REPL 共用一個 session_id;每一輪提問是這個 session 下的一條 trace。
    session_id = str(uuid.uuid4())
    print(f"Session 開始 (session_id={session_id})。輸入問題,quit 離開。\n")

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

        # 把 session/user/tag 下傳到這一輪 agent_run 內建立的所有 observation。
        with propagate_attributes(
            session_id=session_id,
            user_id=USER_ID,
            tags=["stage3", "repl"],
        ):
            answer = agent_run(question)
        print(f"助理> {answer}\n")

    get_langfuse().flush()
    print(f"\n✔ Session 結束。到 UI 的 Sessions 頁找 {session_id},看多條 trace 串在一起。")


if __name__ == "__main__":
    main()
