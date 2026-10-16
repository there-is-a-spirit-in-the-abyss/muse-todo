# Muse 真實驗收

## Language acceptance (requires the real Muse Agent)

Start without a locale and confirm English replies and “Reminder:” text. Ask
to switch to Spanish, then Portuguese, and restart the Agent between checks to
confirm persistence. In each language exercise add/list/update/complete/delete,
an ambiguous-time question, an invalid command, pending-sync explanation and a
real reminder. Expect “Recordatorio:” / “Lembrete:” with the original title.
Switch while a future reminder is scheduled: normal sync updates it without a
duplicate, and delivery uses the latest selection. An unsupported language
must leave settings intact. Keep machine JSON keys/statuses and ownership
markers unchanged. These Agent/notification checks remain `not_run` until real
Muse evidence is captured; local SQLite/subprocess tests cover only code paths.

目前此表是待執行清單。Codex 不具備 Muse 執行環境；本機測試不能填作原生通過。時間由 Muse 執行當刻計算，測試名稱含唯一 run ID，所有測試任務與 cron 都與正常資料分開辨識。

## 測試分級

| 層級 | 執行方式 | 能證明的事 |
|---|---|---|
| Python 自動化 | `python3 -m unittest discover -s tests -v` | 真 SQLite、事務、CLI、重試／對帳演算法；外部 cron 為明確測試替身 |
| Muse Agent 真實工具 | Agent 實際呼叫原生 cron 並保存原始輸入輸出 | schema、權限、排程／更新／刪除工具可用 |
| 完整端到端 | 真實自然語言訊息 → Skill → Python → SQLite → 原生 cron → 真實通知或取消 | 使用者可實際使用；需全鏈路證據 |

## 必做案例

| 案例 | 自然語言與操作 | 必須觀測 |
|---|---|---|
| Add | 「新增驗收〈run〉買書，20 分鐘後截止，10 分鐘後提醒我」 | 真實入站訊息觸發新 Skill；SQLite 任務及 Outbox 原子保存；只有一個 custom 提醒；原生 ID 寫回；新快照後 synced |
| Read | 「列出我的任務，再查看驗收〈run〉買書的提醒同步狀態」 | 回覆與 DB get/list 相同，含真實 ID、version、時間、關聯；一般 Read 無 cron 清單呼叫 |
| Rename | 「把驗收〈run〉買書改名為買技術書」 | DB 版本增一；原生 payload 標題及版本更新，未增加多餘工作 |
| Update time | 「把它的截止改成 30 分鐘後，提醒改成 15 分鐘後」 | 真實 cron.update 呼叫原 ID；DB 與原生排定時間一致，舊時刻不產生通知 |
| Cancel reminder | 「取消提醒，但保留任務」；再「把截止改成 40 分鐘後」 | cron.remove；任務保留；mode:none 持久存在，改截止不偷偷恢復提醒 |
| Add reminder | 「5 分鐘後提醒我這件事」 | cron.add；只存在本次需要的一個工作 |
| Complete | 「這件事完成了」 | 狀態 completed，關聯原生工作移除；等待原定時間後無失效通知，舊 payload gate 拒絕 |
| Delete | 另建帶提醒的驗收任務，再說「刪除驗收〈run〉刪除測試」 | 預設查詢消失、DB tombstone/Outbox 保留；原生工作取消；原定時刻無通知 |
| Delivery | 新建「2 分鐘後提醒我驗收〈run〉通知測試」 | 使用者確實收到一次通知；原生執行記錄、delivery gate、receipt；工作到期消失後不重建 |
| Known failure retry | 對專用測試任務的保留 operation，在真正呼叫前注入 not_applied，再解除故障等待退避 | SQLite 保留 attempts/error；後續真實 add 成功，全量清單只有一個工作 |
| Lost ack retry | 對專用任務真實 cron.add 成功後刻意不 ack，記下 ID，結束該呼叫；依證據 recover | 後續全量清單以 marker 收養原 ID，沒有第二次 add；SQLite 最終 synced |
| Reconcile missing | 先完成同步，透過真實 cron.remove 刪除一個仍在未來的驗收提醒，保留 Todo | reconcile 發現 drift；維護工作重新建立一次；DB 與新 ID 一致 |
| Reconcile wrong | 將專用驗收提醒的真實時間或 payload 改錯 | 正規化反映實際差異；sync 以 cron.update 修復，不能只讀內嵌期望 spec |
| One-shot unknown | 專用一次性工作到期後觀測清單消失，且無 receipt | expired_unknown，無過期重建；不能說已送達 |
| Periodic | 測試任務留 pending，等待原生每分鐘維護執行 | 不靠使用者再次聊天即可驅動同步；保存真實週期執行記錄及最終對齊證據 |
| Isolation | 驗收前後比較非 Todo 正常 cron 清單 | 其他工作 ID／排程／啟用狀態不變；只清理可證明是本輪驗收的資料與工作 |

注入故障只對可識別的測試任務進行，不用破壞正式 DB、不撤銷全域權限。Lost ack 必須是**真實 add 成功**後遺漏回寫，單純 mock 失敗不算本項通過。

## 證據格式

每項 case 至少保存：run_id、Muse 使用者時區、原始自然語言／入站訊息 ID、選中的 Skill 路徑、指令 JSON、SQLite get/list/sync.status 輸出、實際 cron 工具參數與回傳、完整清單前後差異、操作／工作 ID、觀測時間、預期與實際、pass/fail/blocked/not_run。敏感 Token 與其他使用者內容去除。

Complete/Delete 的「不再通知」需要等到原定時間及平台正常調度延遲後檢查通知／執行記錄；僅 remove 回覆成功不足以證明。若訊息已在完成前通過 gate 並在途，記錄平台競態限制，不能偽稱撤回成功。

## 最終報告格式

1. 舊 PoC 備份與隔離狀態；保留了哪些不明資料／提醒。
2. 安裝位置、資料庫、instance_id、真實工具能力與維護工作 ID。
3. Add/Delete/Update/Read 的逐項實測結果與證據。
4. 真實通知與取消是否生效。
5. Outbox、故障恢復、定期對帳是否真實運行。
6. 未解決的平台限制及未跑案例。

全部真實案例通過之前，狀態標為「程式已交付，原生驗收未完成」。
