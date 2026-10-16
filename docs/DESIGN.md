# Muse Todo V1 設計

交付完整離線程式與測試，由 Muse Agent 在自身環境部署。飛書專案唯讀，舊 PoC 不作程式基礎。本機不操作 Muse，不將本機測試當作原生驗收。

## 不變約束

- Python 3.11+，僅使用標準庫；SQLite 主資料與 Outbox 同一事務。
- 單一個人工作區、單一使用者；不含團隊權限、飛書同步或專案系統。
- Agent 將自然語言轉為 JSON，Python 校驗並執行；Python 不連接 cron。
- 預設有截止時間時提前一小時及截止時提醒；明確時間替代預設，取消提醒持久保存。明確時間為絕對時間，改截止不自動平移。過去的預設提醒略過；過去的明確提醒拒絕。
- 截止時間與提醒分開；時間須含時區，內部 UTC，顯示使用設定的 IANA 時區。
- 軟刪除保留清理資訊。修改帶 expected_version；每個變更帶唯一 request_id，重送返回原結果，相同 ID 不同內容拒絕。

## 同步協定

Agent 取得完整且新鮮的原生 cron 清單，正規化為 snapshot，交給 Python。Python 每次只保留一個持久化外部操作，返回 add/update/remove 意圖。Agent 呼叫真實工具，再 ack/fail；每次操作後重新取得清單，不能重播整批舊指令。

每個提醒具有 installation UUID 與 reminder UUID 組成的持久標記，寫入原生工作名稱或 payload。完整清單可找回成功但未回寫的 add，移除重複標記、更新舊版本並清理已完成／刪除任務的提醒。未識別為本安裝已知提醒的工作一律保留並報告。

未知結果或過期執行權不自動接管。先確保舊工具呼叫已停止，再 recover，重新讀取完整清單後決定下一步。這避免在無原生冪等鍵／fencing 的平台上虛構 exactly-once 保證；若無完整清單或持久標記，阻止新增並報告能力不足。

一次性提醒的執行必須先經 SQLite delivery gate，檢查版本、狀態與時間，再由 Agent 發送。到期後消失且無送達證據的工作記為 expired_unknown，不重建過期提醒，也不聲稱已送達。送出成功後回寫 receipt；送出結果不明時保留不確定狀態，不自動重發。

## 拆除與驗收

備份工具只處理指定舊 Skill、執行器與 SQLite，使用 SQLite backup API，產生雜湊清單。停用前必須由 Muse 停止舊執行及明確識別的測試 cron；不明資料與提醒保留。工具拒絕包含未知檔案的 Skill 隔離。

測試分三類：Python 真 SQLite 自動化；Muse 真實工具呼叫；自然語言到 SQLite 到原生 cron 到實際通知的端到端。後兩類只能由 Muse 執行並留下證據。
