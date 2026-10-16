# Muse Agent 部署與舊版拆除

Language configuration: English (`en-US`) is the default. Initial JSON may
include `"locale":"es"` or `"locale":"pt"`; record the choice in the deployment
record. Existing installations switch using `settings.set`, then normal sync.
`settings.get` is the source for the Skill's response language. Never infer a
timezone from language, translate titles, or change an initialized locale with
`init`. PoC commands accept invocation-only `--locale` before the subcommand.

此文件交給 **Muse Agent 在自己的執行環境**執行。Codex 已提供程式，不透過 SSH 部署。不要在 Windows 參考專案中執行舊版拆除，也不要修改飛書機器人。

## 1 準備與只讀盤點

將發行包解壓至 Muse 的暫存目錄。確認 Python 3.11+；先在解壓目錄執行：

```sh
python3 -m unittest discover -s tests -v
```

確認 Muse Workspace 真實位置，只使用 Muse 已知的配置，不尋找連線憑證。下文 `<workspace>` 是 Muse 內部 Workspace 絕對路徑；`<package>` 為解壓位置；它們不能是飛書專案或 Codex 本機路徑。部署時可將實際路徑寫入專用 JSON 檔並透過 --input 傳入，避免 shell 插值。

```sh
python3 <package>/bin/poc.py inspect --workspace <workspace>
```

由 Agent 另外只讀盤點：舊 Skill 註冊／載入設定、Python 執行入口、週期與測試 cron、是否有正在執行的工作。原生全量 cron 清單需包含分頁及停用項目，保存原始清單與執行記錄；配置備份限相關檔案，不將 Secret 放進交付證據。

原生 cron 只有在工作 payload、執行路徑、舊 DB／Skill 指向與已知測試來源能明確證明是舊 PoC 時才列入停用清單。僅標題含 Todo、或看起來像測試，不足以刪除。無法區分的使用者提醒保持原狀，記錄 ID 與理由。

## 2 備份與隔離

先建立一次備份，再停止舊 runner 及明確屬於舊 PoC 的 cron／載入入口；保留恢復所需的原生定義。若停止過程可能產生新資料，停止後再做一份新備份，以新備份隔離。每次 destination 必須不存在，例如 `<workspace>/backups/todo-poc-<實際時間戳>`。

```sh
python3 <package>/bin/poc.py backup --workspace <workspace> --destination <new-backup-directory>
```

工具只處理已指定的舊路徑：

- `skills/todo/SKILL.md`
- `skills/todo/bin/todo.py`
- `data/todo/todos.db` 及存在的 WAL／SHM／journal

Skill 與執行器原樣複製；DB 以 SQLite backup API 產生一致快照，含已提交 WAL 資料，執行 integrity_check。manifest 保存來源雜湊及備份雜湊。未知 Skill 檔案會列出並保留，不盲目移動。工具不解析或修改共享配置，也不操作 cron。

**確認舊程式與相關 cron 已停止**、manifest.source_stable=true，核對備份可讀後：

```sh
python3 <package>/bin/poc.py quarantine --manifest <new-backup-directory>/manifest.json --quiesced
```

`--quiesced` 是 Agent 對事實的明確聲明，不是停止程序的替代功能。工具會先驗證全部來源與備份，再把已知檔案移至備份目錄內的 quarantine，保留操作清單；不刪除資料。來源變更、備份損壞、出現新檔案、未知 Skill 文件或 symlink 時拒絕隔離。若舊 Skill 有額外文件，先查清並另行備份、保留，不為通過檢查而刪除。

隔離過程中斷可重跑同一命令：每個檔案必須只在原位置或 quarantine 其中之一，且雜湊一致。完成後不要重建舊 SKILL.md；確認舊載入入口、外部 cron payload 與 runner 不再調用舊 todo.py／舊 DB。共享設定只修改明確屬於舊 PoC 的條目，修改前保留相關原檔與差異。

舊有效任務保存在備份中，V1 不自動轉入，也不套用舊 schema。若存在需要繼續追蹤的任務，記錄數量及使用者可讀摘要，在新版本可用後由使用者決定是否重新建立；原生舊提醒不能以「測試」名義誤刪。拆除報告列明「已隔離／保留未處理」，不能全部籠統記為成功。

## 3 安裝全新版本

建議目的地 `<workspace>/skills/muse-todo`，正式資料 `<workspace>/data/muse-todo-v1/todos.db`。若目的地已存在，先核對內容與備份，不能直接覆蓋。將發行包整體複製至新 Skill 目錄；保留 SKILL.md、bin、muse_todo、references、docs 及測試。不要複製舊 PoC 程式到新位置。

建立 UTF-8 `init.json`，時區採 Muse 使用者已確認的配置。UTC 範例：

```json
{"command":"init","timezone":"UTC"}
```

```sh
python3 <workspace>/skills/muse-todo/bin/todo.py --db <workspace>/data/muse-todo-v1/todos.db --input init.json
```

非 UTC 時區需要 IANA zoneinfo；Linux 系統通常提供。若缺少，可由環境管理者安裝系統時區資料或 Python tzdata，不能靜默當 UTC 解讀使用者時間。初始化後時區不可用 init 偷改。

記錄 init 回傳 instance_id。以 Muse 支援的方式重新載入此 Skill，確認自然語言新增、查詢、修改、刪除實際選中此 SKILL.md；不能只靠 Python 測試判定 Skill 已載入。

## 4 原生 cron 適配與維護工作

閱讀 [CRON_BRIDGE](../references/CRON_BRIDGE.md)，在 Muse 自己的工具 schema 上確認：

1. 真實清單工具、分頁方式、一次性時間表示、時區、啟用欄位。
2. add/update/remove 的參數與回傳工作 ID／不存在錯誤。
3. 可持久讀回 marker 和 gate payload；原生工作喚醒的 Agent 具有 Python 與通知權限。
4. 綁定哪個使用者、會話／目的地；原生自動公告與手動通知只選一條，避免雙重發送。
5. 可以取得哪種真實投遞證據；不能取得 receipt 時記錄 sending 的限制。
6. 原生週期工作能每分鐘喚醒有權限的協調 Agent。

在專用 `deployment-record.json` 記錄上述實際值、絕對 Skill／DB 路徑、instance_id、工具版本、維護工作 ID、部署時間及驗收證據位置。這是部署記錄，不是 Python 憑證配置；程式不需要 cron token。

先用可識別的測試任務驗證一次性原生提醒；不要改動正常任務。再建立唯一 `muse-todo-maintenance:<instance_id>` 週期工作，payload 按協定執行 sync 循環及故障報告。它同時負責 Outbox 重試與全量定期對帳。建立前查同標記工作；重裝不重複增加。首次運行後保存真實執行結果，確認 scheduled Agent 確實有 Python/cron 權限。若無法啟用，CRUD 仍可保存，但提醒自動恢復尚未就緒，必須報告。

## 5 真實驗收與交接

按照 [ACCEPTANCE.md](ACCEPTANCE.md) 執行自然語言 CRUD、真實工具及真正通知測試。將結果填入 `evidence/muse-e2e-results.json`（部署時新建），每項含 status、原生入站訊息、DB 查詢結果、工具呼叫／工作 ID 及觀測時間。沒有結果填 not_run／blocked，不能複製本機模擬結果。

上線需全部滿足：舊載入入口停用，新 Skill 真實觸發，正確 DB，Add/Read/Update/Complete/Delete 真實對齊，實際收到一次提醒，重試無重複、對帳能修復、維護工作實際運行。不滿足時報告具體缺口。

## 回復與維護

回復前先停止新維護工作、所有同步及通知 Agent。取得完整 cron 清單，按新安裝已知 marker 清理／停用工作，保留不明項；備份 V1 DB。不能在兩套執行器同時活動時直接交換 DB。

舊 PoC 可從 quarantine 恢復原檔；恢復舊 DB 以一致備份 `todos.db` 為準，不把快照和不同時間的舊 WAL 混用。恢復前保留目的地現有檔案，不盲目覆蓋。按保存的配置差異恢復載入入口；舊測試 cron 預設不恢復，確需恢復才使用原始定義。保留兩套資料和 manifest 以便核對。

一般維護查 sync.status。blocked 依協定確認舊執行停止後 recover；sending／expired_unknown 對照真實通知與執行記錄，不自動再次投遞。正常資料庫備份使用 SQLite backup API；還原後先隔離所有舊執行並對帳。不得清除 requests、operations 或提醒墓碑來「解決」重複問題。
