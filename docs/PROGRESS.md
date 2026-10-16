# 執行記錄

- 2026-10-16 language update: added persisted en-US/es/pt installation settings,
  localized service/CLI/PoC CLI text and reminder prefixes, and explicit Skill
  response-language rules. TDD regressions cover old database fallback, invalid
  settings, Unicode titles, pending operations and delivery claims. Full local
  suite: 64 passed; compileall passed through scripts/verify.py. Existing
  independent review below predates these changes. Real Muse checks remain
  unrun; release validation is recorded in evidence/release-check.txt.

- 已完成飛書個人 Todo 唯讀參考，來源列於 BUSINESS_REFERENCE.md。
- 交付範圍：使用者選擇預先編寫完整程式、測試及部署說明；實際 Muse 拆除、部署與 cron 驗收不在本機執行。
- 工作區為使用者指定的空目錄，沒有 Git 儲存庫，直接在此實作。
- Task 1 complete：CRUD、模式、版本／請求冪等及真 SQLite 事務；14 項測試通過。初次測試確認尚缺套件；後續發現 Windows 無 IANA tzdata，UTC 改用標準庫 timezone.utc，非 UTC 缺資料時明確拒絕。
- Task 2 complete：持久操作、快照、回寫／恢復、退避、對帳、投遞 gate；補上 operation barrier 防止 ack 後重用先前快照。已驗證過期執行權不會自動接管。
- Task 3 complete：UTF-8 JSON CLI、重複 key 拒絕、指定路徑備份／隔離；WAL 快照、來源變更與不明檔案保護皆驗證。
- Task 4 complete：Skill、部署／驗收與 Muse 交接指令已建立。獨立代理完成程式審查及 38 次 Skill CLI 使用，發現的兩項重要問題已各以失敗回歸測試重現並修正；無已知未處理的重要審查問題。見 evidence/independent-review.md。
- 官方 quick_validate.py 首次因缺少 PyYAML 無法啟動；後於一次性暫存目錄安裝驗證依賴，未修改宿主全域 Python，正式 quick_validate 通過。執行時套件安裝輸出的 Windows 編碼曾使外層 subprocess reader 警告；validator 本身 exit 0、回傳 Skill is valid，結果存 evidence/skill-validation.txt。產品仍只依賴標準庫。
- Final：修正到期工作過早清理，新增三項等待窗口回歸測試；修正 Windows Python 3.11 junction 檢測，真實 junction 測試由失敗轉通過；納入並發同步、並發投遞、recover 後延遲 ack 測試。
- Task 5 complete（2026-10-14）：48 項全套測試通過，compileall 通過。發行包解壓、逐檔 SHA256 與包內測試見 evidence/release-check.txt。Muse 真實工具、E2E、拆除與週期工作均未執行／未部署。
