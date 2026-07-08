# Langfuse 101 — 動手學 LLM Observability

透過「從最小 trace 逐步長成一個手刻 tool-calling agent」的過程,實際練過 Langfuse 的核心功能:
**tracing → sessions → scores → prompt management → cost tracking**。

- **LLM**:OpenAI(用 `langfuse.openai` drop-in wrapper,自動 trace + cost)
- **Langfuse**:self-host,官方 docker compose(貼近內部平台導入情境)
- **Agent**:手刻 tool-calling loop(最能理解 tracing 對 agent 的意義)

> **SDK 版本**:本專案使用 **Langfuse Python SDK v4(OpenTelemetry-based)**。
> 網路上大量舊範例用的 `langfuse.trace()` / `StatefulClient` 已 deprecated,不要照抄。
> 本專案一律用:`get_client()`、`@observe`、`start_as_current_observation`、
> `propagate_attributes()`、`create_score()` / `score_current_trace()`。

## 專案結構

```
langfuse101/
├── docker-compose.yml       # Stage 0 從 langfuse repo 取得(見下)
├── .env.example → .env      # OpenAI + Langfuse self-host 認證
├── requirements.txt
├── src/
│   ├── config.py            # 共用設定 + 連線健檢
│   ├── s1_hello_trace.py    # Stage 1:第一條 trace
│   ├── tools.py             # agent 的工具(calc / time / mock search)
│   ├── s2_agent.py          # Stage 2:手刻 tool-calling agent + 巢狀 span
│   ├── s3_sessions.py       # Stage 3:多輪 REPL + session/user
│   ├── s4_scores.py         # Stage 4:三種 score
│   ├── s5_prompts.py        # Stage 5:版本化 prompt(從 Langfuse 拉)
│   └── s6_capstone.py       # Stage 6:全套整合的 agent CLI
└── notes/when-to-use-what.md  # 決策筆記(能力驗收)
```

## Stage 0 — 環境設定(一次性)

**1. 啟動 self-host Langfuse**(需要 Docker):

```bash
# 取得官方 docker-compose(放到專案外或子目錄皆可)
git clone https://github.com/langfuse/langfuse.git .langfuse-src
cd .langfuse-src
docker compose up -d           # 等 langfuse-web-1 log 出現 "Ready"(約 2~3 分鐘)
```

開 <http://localhost:3000> → 註冊本機帳號 → 建 Organization → 建 Project →
Project Settings 產生 API keys。

**2. 設定 Python 環境與認證:**

```bash
cd langfuse101
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env           # 填入 Langfuse keys + OPENAI_API_KEY
```

**3. 健檢:**

```bash
python src/config.py           # 應印出「✅ Langfuse 認證成功」
```

## 各階段執行

> 所有 stage 都從 `src/` 目錄跑(彼此用相對 import):`cd src` 後 `python sN_*.py`,
> 或 `PYTHONPATH=src python src/sN_*.py`。

```bash
cd src
python s1_hello_trace.py       # Stage 1
python s2_agent.py             # Stage 2
python s3_sessions.py          # Stage 3(多輪 REPL)
python s4_scores.py            # Stage 4(會請你打 👍/👎)
python s5_prompts.py --seed    # Stage 5:先建立 prompt(一次)
python s5_prompts.py           # Stage 5:跑 agent(從 Langfuse 拉 prompt)
python s6_capstone.py          # Stage 6:全套整合(先確認做過 --seed)
```

每跑完一個 stage,到 <http://localhost:3000> 對照下面的驗收清單。

## 驗收清單(自我檢核)

**Stage 1** — 最小 trace
- [ ] Traces 頁看到 `ask` trace,展開有一個 generation
- [ ] generation 上有 model / input / output / token usage / latency
- [ ] 能解釋 `@observe` 產生的 span 與底下 generation 的父子關係

**Stage 2** — agent + 巢狀 span
- [ ] 需要用工具的問題產生「多輪 generation + 對應 tool span」的樹
- [ ] 樹狀結構反映「LLM 決策 → 呼叫工具 → 再決策」順序
- [ ] 能說出不用 wrapper 時如何手動建 generation

**Stage 3** — session / user
- [ ] Sessions 頁看到多輪對話串在同一個 session
- [ ] trace 帶 user_id 與 tags,能在 UI 篩選
- [ ] 能說出何時用 session、何時一條 trace 就夠

**Stage 4** — scores
- [ ] 一條 trace 同時掛到 format-ok / relevance / user-feedback
- [ ] 能用 score 篩選 / 排序找出低分 trace
- [ ] 能判斷哪種 score 適合線上即時、哪種適合離線批次

**Stage 5** — prompt management
- [ ] code 不再 hardcode system prompt,改從 Langfuse 拉
- [ ] 在 UI 改 prompt 存新版後,不改 code 重跑行為改變
- [ ] generation 顯示連結到的 prompt 名稱與版本

**Stage 6** — capstone
- [ ] Dashboard 看到跨 trace 的 cost / token / latency 匯總
- [ ] 一次對話在 UI 呈現完整:session → traces → spans/generations → scores → prompt link → cost
- [ ] 完成 `notes/when-to-use-what.md`(用自己的話)

## 收工 / 清理

```bash
cd .langfuse-src && docker compose down        # 停止 Langfuse(保留資料)
# docker compose down -v                       # 連同資料一起清掉
```

## 選配延伸(貼近你的工作)

- **框架整合對照**:用 LangChain + Langfuse `CallbackHandler` 跑等價 agent,
  對比「框架自動 trace」與「手刻 trace」的差異。
- **MCP 情境**:把 `tools.py` 的 mock 工具換成走真實 MCP 呼叫的工具,觀察 trace 如何跨 MCP 邊界。
