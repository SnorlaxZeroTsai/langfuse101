# 決策筆記:什麼情境用 Langfuse 的哪個功能

> 這是 Stage 6 的能力驗收物。**建議你完成專案後,用自己的話重寫一遍**,
> 下面是骨架與參考答案——能不看文件講清楚每一項,才算真的學會。

## 核心資料模型:Trace vs Observation(Span / Generation)

| 概念 | 是什麼 | 什麼時候建立 |
|------|--------|--------------|
| **Trace** | 一次完整的執行(一次請求 / 一次 agent 提問) | 通常對應最外層 `@observe` 函式 |
| **Observation** | trace 底下的一個步驟,分幾種型別: | |
| └ **Span** | 一段有起訖的工作(一個函式、一個子流程) | `@observe()` 或 `start_as_current_observation(as_type="span")` |
| └ **Generation** | 一次 LLM 呼叫(特別記 model/token/cost) | `langfuse.openai` wrapper 自動,或手動 `as_type="generation"` |
| └ **Tool** | 一次工具呼叫 | `@observe(as_type="tool")` |

一句話:**Trace 是一棵樹,Observation 是樹上的節點;Generation / Tool 是特化的 Observation。**

## 何時用 Session

- **用 session**:需要把「多次執行」串成同一段脈絡——chatbot 多輪對話、
  一個使用者的一連串 agent 互動。你要能回答「這整段對話發生什麼事」。
- **一條 trace 就夠**:單次、無狀態的呼叫——一次分類、一次摘要、一次批次任務裡的一筆。

## 三種 Score 的時機

| 來源 | 成本 | 時機 | 代表什麼 |
|------|------|------|----------|
| **使用者手動回饋** (👍/👎) | 低,但要有使用者 | 線上即時 | 真實滿意度,最可信但量少 |
| **程式規則** (格式/長度/schema 檢查) | 極低 | 線上即時 或 離線批次 | 硬性正確性,能大量跑 |
| **LLM-as-judge** (另叫 LLM 評分) | 較高(多一次呼叫) | 多半離線批次 | 語意品質(相關性/正確性),可規模化但需驗證 judge 本身 |

判斷法:**能用規則就別用 LLM(便宜);要語意判斷才用 LLM-judge;
最終真相看使用者回饋。** 三者互補,不是三選一。

## Prompt Management 解決什麼

- 把 prompt 從 code 抽出 → **改 prompt 不用改 code、不用重新部署**。
- **版本化 + label**(production/latest)→ 安全灰度、可回滾。
- **generation 連結 prompt 版本** → 配合 score 能分析「哪一版 prompt 表現較好」。
- 情境:prompt 會頻繁調整、由非工程師(PM/內容)維護、需要 A/B 或版本比較時最有價值。

## Cost / Usage Tracking 看什麼

- Generation 自動帶 token usage;OpenAI 等主流 model 有內建價目 → 自動換算 cost。
- 自訂 / self-host model 沒內建價目時,要在 Langfuse 設定 model price(才算得出 cost)。
- Dashboard 看:總 cost 趨勢、每 trace / 每 session 的 token、latency 分佈 → 抓貴的、慢的請求。

## 對應「未來在內部 agent 平台導入」的建議順序

1. 先上 **tracing**(wrapper + 少量手動 span)——最低成本拿到可觀測性。
2. 加 **session/user**——把 agent 對話串起來、能按使用者查問題。
3. 加 **score**(先程式規則,再 LLM-judge,最後接使用者回饋)。
4. 導入 **prompt management**——當 prompt 需要版本控管 / 多人協作時。
5. 用 **cost dashboard** 做容量規劃與多雲 model 成本比較(貼近你的多雲評估工作)。
