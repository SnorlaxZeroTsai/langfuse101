"""共用設定與連線健檢 (Stage 0)。

每個 stage 都 `from config import ...` 取得已設定好的 Langfuse client 與模型名稱。
直接執行本檔 (`python src/config.py`) 會做一次連線健檢,確認 .env 與 self-host 都 OK。

三把認證資訊各自的角色(這也是 Stage 0 的驗收問題):
  - LANGFUSE_PUBLIC_KEY  → 識別「哪個 project」,會附在每筆送出的資料上。
  - LANGFUSE_SECRET_KEY  → 證明「有權寫入該 project」,等同密碼。
  - LANGFUSE_HOST        → 資料送到哪個 Langfuse 實例(self-host = localhost:3000)。
SDK 從環境變數自動讀取這三者,所以只要 load_dotenv() 後 get_client() 就能用。
"""

import os
import sys

from dotenv import load_dotenv

# 先載入 .env,SDK 與 OpenAI 都靠環境變數認證,務必在 import/建立 client 前呼叫。
load_dotenv()

from langfuse import get_client  # noqa: E402  (需在 load_dotenv 之後)

# 練習全程共用的模型名稱;改 .env 的 OPENAI_MODEL 就能整包換模型。
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def get_langfuse():
    """回傳設定好的 Langfuse client(單例,SDK 內部會 cache)。"""
    return get_client()


def healthcheck() -> bool:
    """驗證認證與連線;成功回 True。"""
    missing = [
        k
        for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST", "OPENAI_API_KEY")
        if not os.getenv(k)
    ]
    if missing:
        print(f"❌ .env 缺少這些變數: {', '.join(missing)}")
        print("   請 `cp .env.example .env` 後填入實際值。")
        return False

    client = get_langfuse()
    print(f"→ 連線目標 (LANGFUSE_HOST): {os.getenv('LANGFUSE_HOST')}")
    # auth_check() 會實際打 API 驗證 keys;失敗回 False。
    if client.auth_check():
        print("✅ Langfuse 認證成功,連線正常。")
        print(f"✅ 使用模型: {MODEL}")
        return True

    print("❌ Langfuse 認證失敗:檢查 keys 是否正確、docker compose 是否已啟動。")
    return False


if __name__ == "__main__":
    ok = healthcheck()
    sys.exit(0 if ok else 1)
