# JSON 指令與業務規則

## Installation language

Supported locales: `en-US` (default), `es`, `pt`. `init` accepts optional
`locale` and returns it alongside the existing installation information.
Existing V1 databases without that setting use English without migration.

```json
{"command":"init","timezone":"UTC","locale":"en-US"}
{"command":"settings.get"}
{"command":"settings.set","locale":"es"}
```

Run each object separately. `settings.get/set` return `{"locale":"es"}` for
the selected language. `settings.set` accepts only `command` and `locale`,
rejects unsupported or non-text values atomically, and changes no todo version,
request replay, operation or delivery claim. Repeated `init` preserves the
saved locale; specifying a different locale there is rejected.

Skill replies, CLI help/errors, reminder prefixes and explanatory `reason/next`
strings follow the setting. Never branch on human message text. JSON keys,
error class names, command names, status values, IDs and markers stay stable;
user titles and supplied diagnostic/evidence content are never translated.
After switching language, run normal sync to refresh future payloads; delivery
uses the current selected language. See [language design](../docs/DESIGN_LANGUAGES.md).

入口：`python3 <skill>/bin/todo.py --db <db> --input <file>`；也可由 stdin 提供一個 JSON object。全為 UTF-8。成功 stdout `{"ok":true,"result":...}`、exit 0；資料／I/O／SQLite 錯誤 `{"ok":false,"error":...,"message":...}`、exit 2。無 HTTP、無 cron 連線、無外部依賴。`--help` 顯示入口參數。

## 初始化

```json
{"command":"init","timezone":"UTC"}
```

僅首次執行，保存 installation UUID 與顯示時區。重複相同設定安全；既有不同 schema 的 DB 拒絕覆蓋。正式資料必須用新路徑，不使用舊 `data/todo/todos.db`。UTC 無外部時區依賴；其他 IANA 時區需要系統 zoneinfo 或 Python tzdata。

## Add

```json
{"command":"add","request_id":"native-message-123:0","title":"寄合約","due_at":"2030-01-02T18:00:00+08:00","reminder":{"mode":"custom","times":["2030-01-02T17:30:00+08:00"]}}
```

日期只是格式範例，真實操作必須用未來時間。title 必填、非空、最長 255 字；request_id 必填、最長 200 字。同一 ID 的完整指令必須一致；重送回傳首次事務結果，可能已不是最新版本，需要 get 再確認現況。

due_at 可省略或 null。提醒模式：

| 模式 | 規則 |
|---|---|
| 省略 reminder／default | 有截止時間則建立前一小時及截止時兩個一次性提醒；已過時間略過。無截止則無提醒 |
| custom | times 必須為 1–10 個含時區的未來時間；去重排序，取代預設。可無截止時間 |
| none | 明確不提醒；之後只改截止時間不會恢復提醒 |

明確輸入過去提醒會拒絕整筆操作；過去截止可保存為逾期任務，不自動建立過去提醒。每個時刻皆保存 UTC。時區或夏令時間歧義由 Agent 在轉換前釐清。

## Read

```json
{"command":"list"}
{"command":"list","status":"all","query":"合約","include_deleted":false}
{"command":"get","id":"真實 Todo UUID"}
{"command":"sync.status"}
```

每行為獨立指令。list 預設 pending，排除刪除資料；可篩選 pending/completed/canceled/all、標題子字串、已刪除資料。按截止時間、建立時間、ID 排序，無截止排後。get 含 version、狀態、due_at/due_local、提醒關聯 remote_id、投遞狀態及本版本 Outbox 狀態。Read 不讀 cron；remote_id 代表最近觀測，不能代替即時排程存在的證明。逾期是衍生屬性，不是另一種業務狀態。

## Update 與 Delete

```json
{"command":"update","request_id":"native-message-124:0","id":"真實 Todo UUID","expected_version":1,"changes":{"title":"寄正式合約","due_at":"2030-01-03T18:00:00+08:00"}}
{"command":"update","request_id":"native-message-125:0","id":"真實 Todo UUID","expected_version":2,"changes":{"reminder":{"mode":"none"}}}
{"command":"update","request_id":"native-message-126:0","id":"真實 Todo UUID","expected_version":3,"changes":{"status":"completed"}}
{"command":"delete","request_id":"native-message-127:0","id":"真實 Todo UUID","expected_version":4}
```

changes 支援 title、due_at、reminder、status；未知欄位拒絕。未出現的欄位不變；due_at:null 清除截止時間。reminder 不能為 null，取消使用 mode:none，恢復預設使用 mode:default。custom 是絕對時間，只改截止時間不平移提醒；需移動提醒時同時指定新的 times。

狀態為 pending/completed/canceled。完成或取消會使所有提醒失效並同步刪除原生工作；重新設 pending 只恢復未來的原模式提醒。Delete 保存 tombstone、提醒標記與操作歷史，待取消同步完成；預設查詢隱藏。已刪除任務拒絕新變更；相同刪除請求重送返回原結果。

修改或刪除必須使用讀到的 version；每次成功變更遞增，過時操作拒絕。Todo、提醒期望狀態、Outbox、請求去重結果在同一 SQLite 事務提交。

## 同步與投遞指令

```json
{"command":"sync.next","snapshot":{"complete":true,"observed_at":"2030-01-01T10:00:00Z","barrier":null,"jobs":[]}}
{"command":"reconcile","snapshot":{"complete":true,"observed_at":"2030-01-01T10:00:00Z","barrier":null,"jobs":[]}}
{"command":"sync.ack","operation_id":"真實 operation UUID","remote_id":"真實 cron ID"}
{"command":"sync.fail","operation_id":"真實 operation UUID","outcome":"unknown","error":"原生工具超時，結果未知"}
{"command":"sync.recover","operation_id":"真實 operation UUID","quiesced":true,"evidence":"已確認原工具呼叫停止的具體證據"}
{"command":"delivery.check","reminder_id":"真實 reminder UUID","version":1,"at":"2030-01-01T12:00:00Z"}
{"command":"delivery.ack","reminder_id":"真實 reminder UUID","token":"check 回傳的 token","receipt":"真實投遞 message ID 或原生執行成功記錄"}
```

詳細協定、重試條件及正常化規則見 [CRON_BRIDGE.md](CRON_BRIDGE.md)。以上快照中的時間、barrier、ID 不可照抄到正式環境。
