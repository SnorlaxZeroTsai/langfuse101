# Stage 8 — 進階概念:哪些值得你深入,為什麼

> 這一章不是 Langfuse 功能清單。這是**我(agent)從「你要導入內部 agent 平台做 observability」
> 這個目標出發**,篩選並排序出值得你深入的主題,並對每個說明「為什麼值得學」。
> 官方文件寫得不夠深、或社群還有爭議的地方,我會明講並給我的判斷。

排序準則(三軸):
- **平台影響力**:對「內部 agent 平台導入」的實際成敗影響。
- **遷移價值**:學會後能不能套到其他 observability 工具(不被 Langfuse 綁死)。
- **成熟度**:業界最佳實踐是否還在演變(越在演變、越需要你自己有判斷)。

| # | 主題 | 平台影響力 | 遷移價值 | 成熟度 |
|---|------|-----------|---------|--------|
| 1 | OTel 資料模型 + 跨邊界 context 傳播 | ★★★ | ★★★ | 穩定 |
| 2 | 多 agent 的 trace 拓樸 + session 模糊地帶 | ★★★ | ★★ | 演變中(有爭議) |
| 3 | Cost tracking 的準確度真相 | ★★ | ★★ | 有爭議 |
| 4 | Sampling + PII masking + self-host 規模化 | ★★★ | ★★★ | 穩定但少人教 |
| 5 | Evaluation / dataset / LLM-judge pipeline | ★★ | ★★ | 快速演變中 |

---

## 1. OpenTelemetry 資料模型 + 跨邊界 context 傳播 ★最該先學

**為什麼值得學(不是怎麼操作)**:
Langfuse v4 **本質就是一個 OpenTelemetry backend**——trace/observation 對應 OTel 的 trace/span,
`propagate_attributes` 底層是 OTel baggage,Stage 7.3 的 traceparent 是 W3C Trace Context。
這代表:**你學的其實是 OTel,Langfuse 只是其中一個 backend。**

這是遷移價值最高的一項。你今天把概念學透,明天要換 Jaeger、Grafana Tempo、Google Cloud Trace,
或「Langfuse 看 LLM 語意層 + Tempo 看系統延遲」並存,底層模型完全一樣。
對一個**要為整個內部平台選型/長期維護**的平台工程師,這比記 Langfuse API 重要得多。

**該深入的點**:
- trace / span / span link 的關係(link 用在「一個 span 關聯到多個 parent」,如 batch/fan-in)。
- context 傳播的三種載體:process 內(context var)、跨執行緒/async、跨程序(traceparent header)。
- 為什麼 async agent 最容易掉 context——這是實務上「trace 莫名斷掉」的頭號原因。

**我的判斷**:先花時間在這,其餘全部是它的應用。若只能學一章,學這章。

---

## 2. 多 agent 場景的 trace 拓樸 + session 定義的模糊地帶 ★你點名的爭議

**為什麼值得學**:
單 agent 時 session/trace/observation 三層很清楚(README Stage 3)。
但你的世界是**多 agent**(MCP Gateway 後面一堆 agent、agent 呼叫 agent)。這時三層定義會崩解,
而**官方文件基本沒好好處理這塊**——它預設你是單一 chatbot。

**模糊地帶具體長怎樣**:
- 一個使用者請求 → orchestrator agent → 呼叫 3 個 sub-agent。這是**一條 trace(含巢狀 span)**,
  還是 **4 條 trace(用 span link 關聯)**?
- 「session」到底綁**使用者對話**,還是綁**一個 agent 的生命週期**,還是綁**一個工作任務**?
  多 agent 下這三者不再重合。
- sub-agent 是獨立部署的服務時,它「應該」自己開 trace(它有自己的維運關注),
  但你又想從 orchestrator 看到端到端。

**我的判斷(官方沒明說,這是我的建議)**:
- **trace 邊界 = 一個「可獨立失敗/重試」的工作單位**。orchestrator 一次完整處理 = 一條 trace;
  跨服務的 sub-agent 用 **traceparent 接成同一條 trace**(Stage 7.3 那招),而不是拆成多條再事後關聯。
  → 除非 sub-agent 是被多方共用的獨立服務,才讓它自成 trace + 用 **span link** 關聯回來。
- **session = 使用者可感知的一段連續互動**(對話/任務串),**不要**綁 agent 生命週期。
  agent 生命週期是「實作細節」,不該洩漏到 session 這個「使用者維度」的概念。
- 一句話:**trace 回答「這次請求發生什麼」,session 回答「這個使用者/任務的脈絡」。
  多 agent 只是讓 trace 變深,不該讓 session 變複雜。**

這章遷移價值中等(session 是 Langfuse 概念,但 trace 拓樸是 OTel 通用),平台影響力極高。

---

## 3. Cost tracking 的準確度真相 ★你點名的爭議

**為什麼值得學**:
你在做**多雲成本評估**,一定會想用 Langfuse 的 cost 數字做決策。
但**必須先知道它是「估算」不是「帳單」**,否則會拿錯數字下結論。

**準確度會失真的地方(官方文件輕描淡寫)**:
- **價目表對不上**:Langfuse 用內建 model price 表 × token 數估算。表可能落後於供應商調價;
  self-host / 自訂 / 非主流 model 根本沒有內建價目,cost 會是 0 或要你手動設 model price。
- **cached token**:prompt caching 的計費和一般 input token 不同價,估算常沒反映 → 高估。
- **streaming**:串流回應的 usage 有時要靠 SDK 補算,少數情況拿不到精確 token。
- **非 OpenAI provider**:token 計法(tokenizer)不同,估出來的 token 數本身就可能有偏差。
- **gateway 疊加**:經過 LiteLLM proxy 時,cost 由誰算(proxy 還是 Langfuse)要搞清楚,否則會重複或落差。

**我的判斷**:
- Langfuse cost **適合看「相對趨勢」與「量級比較」**(這個 agent 比那個貴一個數量級)——這對你多雲評估**夠用且好用**。
- **不適合當對帳/計費依據**。要精確帳單,以**供應商帳單**為準,Langfuse 當「歸因工具」(哪個 trace/agent 花掉的)。
- 多雲評估的正確用法:**在 Langfuse 比相對成本結構,用供應商帳單校準絕對值。**
- 自訂/self-host model 一定要去 Langfuse 補 **model price 定義**,否則 cost 一片空白。

---

## 4. Sampling + PII masking + self-host 規模化 ★上線生死線,卻最少人教

**為什麼值得學**:
前面幾章讓 trace「能看」;這章決定 trace「能不能真的上線」。這是教學最少、但**內部平台導入的成敗關鍵**。

**三個必須處理的問題**:
- **PII / 機敏資料**:trace 會原封不動記 prompt/response,裡面可能有使用者個資、內部機密、API key。
  裸送進 observability 後端在很多公司是**合規紅線**。Langfuse SDK 支援 **masking**(送出前遮罩),
  你必須在導入第一天就設好,而不是事後。
- **Sampling**:高流量下把每一條 trace 都留會爆成本(儲存 + Langfuse billable units)。
  要用 OTel sampler 決定「留多少、怎麼留」(head sampling 便宜但盲、tail sampling 準但貴)。
- **self-host 規模化**:README 用的單機 docker compose **不是生產架構**。
  真上線要處理 ClickHouse(trace 儲存)、worker 水平擴展、備份、保留期(retention)。

**為什麼遷移價值高**:masking / sampling / retention 是**所有** observability 系統的共同課題,
不是 Langfuse 特有。你在這學到的直接套用到任何 tracing 平台。

**我的判斷**:對「內部平台導入」這個目標,**這章的實務重要性其實不輸第 1 章**——
技術再漂亮,過不了合規與成本就上不了線。只是它不「有趣」,所以文件和教學都輕輕帶過。
建議你把「masking 策略 + sampling 策略 + retention 策略」當成導入的**驗收項**,而非選配。

---

## 5. Evaluation / dataset / LLM-judge pipeline ★高價值但還在快速演變

**為什麼值得學**:
Stage 4 打過即時 score;這章是把它**系統化**——維護 dataset(測試集)、
對新版 prompt/model 跑離線批次評估、用 LLM-as-judge 做規模化品質把關。
對「持續改進 agent 品質」很有價值,也是 observability 從「看問題」進到「防問題」的關鍵。

**為什麼我把它排在最後(且標成演變中)**:
- 這塊**業界最佳實踐還在劇烈變動**:LLM-judge 的可靠度、判準怎麼校準、
  offline eval 和 online monitoring 怎麼接,大家還在摸索,半年前的做法可能就過時。
- 它比較偏**應用層 / 資料科學**,離你「平台 observability 地基」的核心目標稍遠——
  平台要**提供**評估能力,但評估方法本身多半由使用平台的團隊決定。

**我的判斷 / 爭議點**:
- **別過度信任 LLM-judge**。judge 本身就是個會錯的 LLM;沒有校準過的 judge score 只是「另一個要驗證的數字」。
  務實做法:用 judge 做**大量粗篩**,人工抽樣校準 judge 的準確度,關鍵決策仍要人看。
- 平台角度:先確保 **score API + dataset 儲存**這些**基礎設施**穩,把「用什麼判準」的選擇權留給業務團隊。
  不要在平台層寫死一套評估邏輯——因為它一定會變。

---

## 給你的導入順序建議(把上面串起來)

1. **第 1 章(OTel 地基)** — 先把 tracing/context 傳播打穩,這是一切的底。
2. **第 4 章(masking/sampling/retention)** — 和第 1 章幾乎同時做,否則上不了線。
3. **第 2 章(多 agent 拓樸/session)** — 你的平台是多 agent,早點定義清楚避免積技術債。
4. **第 3 章(cost 真相)** — 服務你的多雲評估,但清楚它是估算。
5. **第 5 章(evaluation)** — 平台提供能力,判準交給業務團隊,且保持彈性因為它會變。

回到整合章節見 [integrations.md](integrations.md)(Stage 7)。核心練習見專案 [README](../README.md)。
