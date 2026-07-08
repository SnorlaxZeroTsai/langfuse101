"""Stage 7.2 — Google ADK 整合。★ 帶註解骨架(非完整可跑)★

為什麼是骨架:需要 `google-adk` + `openinference-instrumentation-google-adk`,
且要 Google API key(Gemini)。這裡把「整合模式」講清楚,你有環境時填 model 名即可跑。

整合模式:第三方 auto-instrument → OTel(和 7.1 的 callback、7.4 的 handler 都不同)。
  Langfuse 沒有 ADK 專屬 SDK。ADK 原生就發 OpenTelemetry span,
  我們用 OpenInference 的 GoogleADKInstrumentor 把 ADK 呼叫 auto-instrument 成 OTel span,
  送到 Langfuse 的 OTLP endpoint。→ 並存:同一批 span 也可同時送 Google Cloud Trace。

前置(有環境時):
  pip install google-adk openinference-instrumentation-google-adk
  export GOOGLE_API_KEY=...           # 以及沿用專案的 LANGFUSE_*

已知坑:
  - 雜訊 span:auto-instrument 會把其他函式庫的 OTel span 也送進來,可能計入 Langfuse
    的 billable units → 需要做 span 過濾(用 OTel 的 sampler / span processor 篩)。
  - 欄位落差:ADK 某些屬性只落在 metadata,不會對應到 Langfuse 一級欄位(model/usage)。
  - 版本敏感:ADK 與 instrumentor 要版本一起對,升級任一邊都可能對不上。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def main():
    # --- 步驟 1:環境變數(沿用專案 .env 的 LANGFUSE_*,另加 Google key)---
    #   Langfuse 的 OTLP endpoint 由 SDK 依 LANGFUSE_HOST 自動推導。
    #   self-host 記得 LANGFUSE_HOST=http://localhost:3000。
    #   os.environ["GOOGLE_API_KEY"] = "..."   # ← 你的 key

    # --- 步驟 2:開啟 auto-instrumentation(整個 ADK 就被包住)---
    # from openinference.instrumentation.google_adk import GoogleADKInstrumentor
    # GoogleADKInstrumentor().instrument()
    #
    # 這一步等同「掛一個 OTel span processor 到 ADK」。之後所有 ADK 的
    # agent/tool/LLM 呼叫都自動變成 span → 流進 Langfuse。你不用寫任何 @observe。

    # --- 步驟 3:照常寫 ADK agent(對應你 Google 生態的 agent 部署)---
    # from google.adk.agents import Agent
    # from google.adk.runners import InMemoryRunner
    #
    # def get_deploy_status(service: str) -> dict:
    #     """(示範工具)查一個內部服務的部署狀態——貼近你的平台工程情境。"""
    #     return {"service": service, "status": "healthy", "replicas": 3}
    #
    # agent = Agent(
    #     name="ops_assistant",
    #     model="gemini-2.0-flash",          # ← 填你有權限的 Gemini model
    #     instruction="你是平台維運助理,需要時查詢服務狀態。",
    #     tools=[get_deploy_status],
    # )
    # runner = InMemoryRunner(agent=agent)
    # # ... runner.run(...) 跑一輪對話 ...

    # --- 步驟 4:flush ---
    # from config import get_langfuse
    # get_langfuse().flush()

    print(
        "這是帶註解骨架。安裝 google-adk + openinference instrumentor、填入 Gemini model "
        "與 GOOGLE_API_KEY 後,取消上面註解即可跑。\n"
        "重點:整合靠 GoogleADKInstrumentor().instrument() 一行,ADK 的 OTel span 自動進 Langfuse。"
    )


if __name__ == "__main__":
    main()
