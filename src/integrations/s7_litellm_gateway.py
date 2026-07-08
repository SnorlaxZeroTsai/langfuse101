"""Stage 7.1 — LiteLLM 整合(多雲 gateway 情境)。可跑範例。

整合模式:OTel callback。一行 `litellm.callbacks = ["langfuse_otel"]` 就把
LiteLLM 所有請求的 telemetry 以 OpenTelemetry span 送進 Langfuse(並存,不取代)。

這支示範「SDK 直呼」模式(單機驗證用)。真正的 gateway 情境見同目錄
litellm_config.yaml —— 那才對應你的多雲評估:一個 proxy 前面統一掛多家雲,
client 不改 code,流量全進 Langfuse,用同一個 dashboard 比 cost/latency。

前置:
  pip install -r requirements-integrations.txt
  .env 需有 LANGFUSE_* 與 OPENAI_API_KEY(沿用專案根目錄的 .env)

執行:  cd src/integrations && python s7_litellm_gateway.py

已知坑:
  - callback 名稱用 `langfuse_otel`(OTel 路徑),不是舊的 `langfuse`。
  - self-host 要確認 LANGFUSE_HOST 指到你的實例(此處沿用專案 .env)。
  - 非 OpenAI / 自訂 model 的 cost 可能要在 Langfuse 補 model price。
"""

import os
import sys

# 讓範例能沿用專案根目錄的 config(.env 載入、健檢邏輯)。
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import get_langfuse  # noqa: E402  (先調整 sys.path)

import litellm  # noqa: E402


def main():
    # 一行接上 Langfuse(OTel callback)。LiteLLM 原本的 logging 不受影響 → 並存。
    litellm.callbacks = ["langfuse_otel"]

    # 模擬「多雲」:同一支程式輪流打不同 provider 的 model。
    # 實務上這會由 proxy 統一,client 只看到統一 model_name(見 litellm_config.yaml)。
    prompts = [
        ("gpt-4o-mini", "用一句話說明什麼是 API gateway"),
        # 想試多雲就取消下一行註解(需 ANTHROPIC_API_KEY):
        # ("anthropic/claude-sonnet-5", "用一句話說明什麼是 API gateway"),
    ]

    for model, question in prompts:
        resp = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": question}],
            # metadata 可帶 langfuse 專屬欄位,方便在 UI 分組比較不同雲。
            metadata={
                "generation_name": "gateway-eval",
                "tags": ["stage7", "litellm", model.split("/")[0]],
            },
        )
        print(f"[{model}] {resp.choices[0].message.content}")

    get_langfuse().flush()
    print("\n✔ 到 Langfuse Traces 頁看 LiteLLM 送進來的 generation(含 cost/token)。")
    print("  多雲比較:在 dashboard 用 tag/model 分組,比不同雲的 cost 與 latency。")


if __name__ == "__main__":
    main()
