# 獨立審查記錄

2026-10-14，獨立代理只讀審查新專案、在 tempfile 執行程式；沒有接觸 Muse、SSH 或修改飛書。以下為審查代理回報的觀測，不是原生 cron 驗收。

- 原始全套 41 tests 通過，5.866 秒。
- 依 SKILL.md 使用 UTF-8 JSON 檔、無關 cwd 實際執行 38 次 CLI subprocess：初始化、新增兩提醒、模擬外部同步、改標題與版本、取消提醒、查詢，成功。
- 8 個並發 sync.next，只有 1 個保留外部操作，7 個 blocked。
- 8 個並發 delivery.check，僅一個取得投遞權。
- unknown → recover 後，舊 operation 的延遲 ack 被拒絕。

## 發現與修正

1. 到期但尚未原生調度的工作可能被提前移除。主代理新增失敗回歸案例，觀察 remove 被錯誤產生；修正為在 15 分鐘投遞窗口保留有效既有工作，過期缺失工作不補建、終態仍取消。已加入待調度保留、窗口結束清理、過時 payload 報告等測試，並更新 Skill／協定。
2. Windows Python 3.11 缺少 Path.is_junction，可能讓工作區內部 junction 指向的無關檔案被隔離。主代理以真實 tempfile junction 重現測試失敗；修正為檢查 lstat 的 FILE_ATTRIBUTE_REPARSE_POINT，測試通過。Linux 對此 Windows 專用測試會 skip，其他備份測試仍執行。
3. Skill 的「提醒變更後同步」可能被狹義理解。已改為所有變更（含只改標題、截止、狀態與刪除）都執行同步。

最後全套及發行包驗證結果以 python-tests.txt、verification.json、release-check.txt 為準。原生工具 schema、目的地、gate／receipt 能力與週期工作仍需 Muse 自身確認。
