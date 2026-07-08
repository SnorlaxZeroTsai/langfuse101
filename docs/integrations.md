# Stage 7 — 框架與 Gateway 整合

> 接續 README 的 Stage 0~6。前面你手刻 agent、自己埋 `@observe`;這一章看的是
> **當 LLM 呼叫被別人的框架/gateway 包住時,tracing 要怎麼接進 Langfuse**。
> 對你的目標(內部 agent 平台、MCP Gateway、多雲評估)這才是真實情況——
> 你很少能改到每一行 LLM 呼叫,多半是「在邊界上掛一個 hook」。

涵蓋四個對象,刻意選成**四種不同的整合模式**,這樣你學到的是「模式」而非「某個套件的用法」:

| 對象 | 你為什麼會碰到 | 整合模式 |
|------|----------------|----------|
| **LiteLLM** | 多雲 model gateway(統一 OpenAI/Anthropic/Vertex) | OTel callback |
| **Google ADK** | Google 生態的 agent 框架 | 第三方 auto-instrument → OTel |
| **A2A** | 跨框架 agent 互相呼叫的協定 | ⚠️ 無官方整合,手動 OTel 傳播 |
| **LangChain** | 最普及的 agent 框架 | 框架原生 callback |

一個貫穿全章的心智模型:**Langfuse v4 本質是一個 OpenTelemetry backend**。
所以整合的問題永遠是同一個——「這個框架的 telemetry 怎麼變成 OTel span,送到 Langfuse 的 OTLP endpoint」。
四種模式只是「誰負責把它變成 OTel span」的差別。

---

## 7.0 一個前提:取代 vs 並存

導入時最先要回答的問題:**Langfuse 是取代既有的 observability,還是並存?**

- 如果框架/gateway 已經在發 **OTel**(LiteLLM proxy、Google ADK、多數 gateway 都是),
  那 Langfuse 是「**再多一個 OTel exporter/backend**」——**並存**,不是取代。
  你可以同時送 Jaeger(給 SRE 看系統延遲)+ Langfuse(給你看 LLM 語意層)。
- 如果框架有自己**專屬的 UI/後端**(LangChain→LangSmith),那 Langfuse 是**並存的第二個 callback**,
  兩邊都收得到,不衝突。
- 真正「取代」的情況很少;多數時候是**並存 + 各司其職**。這點對內部平台的說服力很重要:
  導入 Langfuse 不需要拔掉現有的 metrics/logs。

---

## 7.1 LiteLLM — OTel callback(多雲 gateway 情境)

### 原生機制與整合方式
LiteLLM 有自己的 **callback/logging 系統**(`litellm.callbacks`)。Langfuse 整合就是註冊一個 callback。
新版走 **OTel**:`litellm.callbacks = ["langfuse_otel"]`(舊版是 `["langfuse"]`,見下方坑)。
→ **並存**:LiteLLM 原本的 logging 不受影響,Langfuse 只是多接一個 sink。

**這是最貼近你多雲評估的一個**:LiteLLM Proxy(= 一個 gateway 程序)前面統一掛
OpenAI / Anthropic / Vertex,所有經過 gateway 的流量**不改任何 client 程式碼**就自動進 Langfuse。
這正是「在邊界掛 hook」的典型。

### 最小可跑範例
兩種用法,見 `src/integrations/s7_litellm_gateway.py`(SDK 直呼)與 `src/integrations/litellm_config.yaml`(Proxy)。

SDK 模式(單機驗證用):
```python
import litellm
litellm.callbacks = ["langfuse_otel"]           # 一行接上 Langfuse
resp = litellm.completion(model="gpt-4o-mini",
                          messages=[{"role": "user", "content": "hi"}])
```

Proxy 模式(真正的 gateway 情境,`litellm_config.yaml`):
```yaml
model_list:
  - model_name: gpt-4o-mini            # client 只看到這個統一名稱
    litellm_params: {model: openai/gpt-4o-mini}
  - model_name: claude                 # 同一個 gateway 背後接不同雲
    litellm_params: {model: anthropic/claude-sonnet-5}
litellm_settings:
  callbacks: ["langfuse_otel"]         # 整個 gateway 的流量都進 Langfuse
```
啟動 `litellm --config litellm_config.yaml`,然後把 client 的 base_url 指向這個 proxy,
在 Langfuse 就能**用同一個 dashboard 比較不同雲 model 的 cost / latency**——直接服務你的多雲評估。

### 已知坑
- **callback 名稱**:`langfuse_otel`(OTel 路徑,建議)vs 舊的 `langfuse`(舊 SDK 路徑)。
  照抄舊教學會接到 deprecated 路徑,拿不到 v4 的 OTel 好處。
- **環境變數**:OTel 路徑用 `LANGFUSE_HOST`(部分版本文件寫 `LANGFUSE_OTEL_HOST`/區域 host),
  self-host 要確認指到你的 `http://localhost:3000`。
- **cost 準確度**:LiteLLM 自己維護一份 model 價目表;非 OpenAI 或自訂 model 的 cost 可能落在
  metadata、或需要你在 Langfuse 補 model price(見 [advanced.md](advanced.md) 第 3 章)。

---

## 7.2 Google ADK — 第三方 auto-instrument → OTel

### 原生機制與整合方式
Google ADK(Agent Development Kit)**原生就會發 OpenTelemetry span**。
但 Langfuse **沒有** ADK 專屬 SDK;整合是靠 **OpenInference 的 `GoogleADKInstrumentor`**
把 ADK 的呼叫 auto-instrument 成 OTel span,再送到 Langfuse 的 OTLP endpoint。
→ **並存**:你可以把同一批 OTel span 同時送給 Google Cloud Trace 與 Langfuse。

這是和 7.1 不同的模式:**你沒有註冊 callback,而是「開一個 instrumentor 就自動包住整個框架」**。

### 範例(帶註解骨架)
見 `src/integrations/s7_google_adk_agent.py`。核心就三步:設環境變數 → `GoogleADKInstrumentor().instrument()`
→ 正常寫 ADK agent,span 自動流進 Langfuse。標成骨架是因為要 `google-adk` + Google API key。

### 已知坑
- **雜訊 span 計入用量**:auto-instrument 會把其他函式庫的 OTel span 也一起送進來,
  在 Langfuse 可能計入 billable units;需要做 span 過濾。
- **欄位落差**:ADK 的某些屬性只落在 metadata,不會對應到 Langfuse 的一級欄位(model/usage 等),
  導致 UI 上有些資訊要去 metadata 翻。
- **版本敏感**:ADK 與 OpenInference instrumentor 都在快速演進,版本要一起對。

---

## 7.3 A2A(Agent2Agent)— ⚠️ 無官方整合,手動 OTel context 傳播

### 現況(重要:先講清楚)
**Langfuse 沒有 A2A 的官方整合;A2A 協定本身的 spec 也沒有內建 observability。**
A2A 是「agent 之間互相呼叫」的開放協定(JSON-RPC over HTTP 為主)。
所以這一節不是「照文件接一個套件」,而是——**你要自己在協定邊界上做 OTel context 傳播**。

**為什麼這節對你最重要**:你的 MCP Gateway / 多 agent 部署,本質就是「一個 agent 呼叫另一個 agent/服務」。
跨程序、跨網路呼叫時,**trace 會斷鏈**——A 的 trace 和 B 的 trace 變成兩棵樹,你看不到端到端。
解法是分散式 tracing 的老招:把 **`traceparent`(W3C Trace Context)** 塞進呼叫的 header 帶過去,
B 端從 header 取出、接上同一條 trace。這招在 A2A、MCP、任何 RPC 都一樣通用——**遷移價值極高**。

### 範例(帶註解骨架)
見 `src/integrations/s7_a2a_tracing.py`:示範 caller 端把 `traceparent` 注入 A2A 的 JSON-RPC
請求 metadata,callee 端取出、用它當 parent context 開 span。重點在**跨邊界的那一步**,
不在 A2A SDK 的細節。

### 已知坑
- **斷鏈是預設行為**:不主動傳 context,兩端一定各自成獨立 trace。這是最常見的「怎麼看不到全貌」。
- **協定沒保留欄位**:A2A spec 沒有標準的 trace header 欄位,你得選一個 metadata 位置並兩端約定好;
  升級協定版本時要留意。
- **時鐘 / 取樣不一致**:跨服務若各自做 sampling,可能一端有、一端無(見 advanced.md 第 4 章)。

---

## 7.4 LangChain — 框架原生 callback

### 原生機制與整合方式
LangChain 有成熟的 **callback 系統**(它自己接 LangSmith 也是走這套)。
Langfuse 提供 `CallbackHandler`(`from langfuse.langchain import CallbackHandler`),
當成一個 callback 傳進 `invoke(config={"callbacks": [handler]})` 即可。
→ **並存**:可以同時掛 Langfuse handler 和 LangSmith,兩邊都收;彼此不衝突。

這是最「無痛」的模式:框架已經幫你切好每個 chain/tool/LLM 的邊界,handler 自動轉成巢狀 span。

### 最小可跑範例
見 `src/integrations/s7_langchain_agent.py`——**用 LangChain 重建 README Stage 2 的 tool-calling agent**,
好讓你**對照**:框架自動產生的 trace 樹 vs 你 Stage 2 手刻的樹,哪個資訊多、哪個可控。
```python
from langfuse.langchain import CallbackHandler
handler = CallbackHandler()
agent_executor.invoke({"input": question}, config={"callbacks": [handler]})
```

### 已知坑
- **serverless callback 背景化**:LangChain >0.3 在 JS/TS(以及某些 Python async)會把 callback 丟到背景執行,
  在 AWS Lambda / Cloud Functions 可能程序結束前沒送完——需要顯式 flush / 等待。
- **並發下的 `last_trace_id`**:重用同一個 handler 拿 trace_id 在並發環境會混;每次請求給新 handler 較安全。
- **AWS Bedrock**:某些情況要改用 OTel 設定,不能只靠 callback handler。
- **抽象洩漏**:框架自動 trace 很省事,但當你要標「自訂業務語意」(如選路決策)時,
  反而比手刻難插入——這也是為什麼 Stage 2 要你先手刻過一遍。

---

## 四者整合模式比較表

| 面向 | LiteLLM | Google ADK | A2A | LangChain |
|------|---------|-----------|-----|-----------|
| **整合機制** | OTel callback (`langfuse_otel`) | 第三方 auto-instrument (OpenInference) | 無官方;手動 OTel 傳播 | 框架原生 callback handler |
| **誰把它變 OTel span** | LiteLLM callback | OpenInference instrumentor | 你自己 | Langfuse handler |
| **取代 or 並存** | 並存(多一個 sink) | 並存(可多後端) | 不適用(自建) | 並存(可 + LangSmith) |
| **改多少 code** | 一行 / gateway config | 一個 instrument() 呼叫 | 要改協定邊界 | 傳一個 callback |
| **async 支援** | 支援(OTel 非阻塞) | 支援(OTel) | 看你怎麼寫 | 支援,但 serverless 有背景化坑 |
| **版本敏感度** | 中(callback 名稱換過) | 高(ADK+instrumentor 一起動) | —(自建,最穩也最累) | 中(>0.3 callback 行為變) |
| **最貼近你的情境** | 多雲 gateway 評估 | Google 生態 agent | MCP Gateway 跨 agent | 一般 agent 快速上手 |
| **主要坑** | callback 名稱 / cost 表 | 雜訊 span 計費 / 欄位落差 | 斷鏈 / 無標準 header | serverless flush / 並發 trace_id |

**一句話總結挑選邏輯**:能發 OTel 的(LiteLLM/ADK)就讓它發、Langfuse 當並存 backend;
框架有 callback 的(LangChain)就掛 handler;什麼都沒有的(A2A)就回到分散式 tracing 基本功,
自己傳 `traceparent`。**這三種情況你在內部平台一定都會遇到。**

---

## 執行方式

```bash
# 整合範例的額外依賴另外裝(不污染核心練習環境)
pip install -r requirements-integrations.txt

cd src/integrations
python s7_litellm_gateway.py      # 可跑(需 OPENAI_API_KEY)
python s7_langchain_agent.py      # 可跑(需 OPENAI_API_KEY)
# s7_google_adk_agent.py / s7_a2a_tracing.py 為帶註解骨架,見檔頭說明
```

延伸的進階概念見 [advanced.md](advanced.md)(Stage 8)。
