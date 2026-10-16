# Muse Todo V1 Implementation Plan

> **For agentic workers:** 使用 superpowers:executing-plans 在本次對話逐項實作；使用者已要求完整程式，不另設重複審批。

**Goal:** 交付可部署的個人 Todo CRUD、原生 cron 協調協定、測試與部署文件。

**Architecture:** SQLite + transactional Outbox；Python 產生同步意圖，Muse Agent 呼叫 cron 並回寫。完整快照支援重試與對帳。

**Tech Stack:** Python 3.11+ 標準庫、SQLite、unittest。

**Spec:** [DESIGN.md](DESIGN.md)

## Global Constraints

- 不修改飛書專案，不接入 Muse，不繼承 PoC 程式。
- 不宣稱原生工具或端到端測試已完成。
- 使用者指定空目錄作獨立工作區；無現有 Git 儲存庫，不建立其他目錄或修改全域設定。

## Review Focus

- add 成功後丟失 ack：重讀快照收養既有工作。
- 操作中更新／完成 Todo：舊 ack 不覆寫新版本。
- 相同請求併發與 SQLite 原子回滾。
- 一次性工作已消失但送達未知：不重建過期工作。
- 舊 PoC 混雜不明檔案、WAL 與備份後變更：保留並拒絕不安全隔離。

## Tasks

1. `tests/test_crud.py` → `muse_todo/store.py`, `service.py`：先寫失敗測試，再實作 CRUD、提醒模式、版本與請求冪等。介面 `TodoService.execute(command: dict) -> dict`。
2. `tests/test_sync.py` → `sync.py`：先測 add/update/remove、失敗、未知結果、舊版本及到期消失，再實作單一持久操作、快照對帳與 delivery gate。
3. `tests/test_poc.py`, `test_cli.py` → `poc.py`, `cli.py`, `bin/todo.py`：先測備份隔離與 subprocess JSON 指令，再實作安全工具及無安裝啟動入口。
4. `SKILL.md`, `references/`, `docs/DEPLOYMENT.md`, `docs/ACCEPTANCE.md`：提供真實平台適配、自然語言流程、定期工作與驗收步驟。獨立評閱 Skill 與程式，修正重要問題。
5. 執行 `python -m unittest discover -s tests -v`、編譯檢查及打包驗證，保存真實輸出至 `evidence/`，交付壓縮包。

每項流程：先執行測試觀察失敗 → 實作 → 全套測試 → 在 PROGRESS.md 記錄結果。文件不以文字匹配測試代替代理行為驗證。
