# Muse Todo V1 本機驗證結果

2026-10-16 language update: Python 3.11.9 on Windows. `python -X utf8 scripts/verify.py`
ran the full unittest suite: **64 passed, 0 failures, 0 skipped**; compileall also
passed. Original output is in python-tests.txt and environment/boundaries are
recorded in verification.json. The release checker verifies member hashes and
runs the tests from an extracted package; see release-check.txt.

Sixteen localization tests exercise persisted en-US/es/pt selection, old V1
fallback, malformed locale atomicity, localized CLI/service errors and help,
Unicode title preservation, reminders in all three languages, and language
switching without changing todo versions, request replays or delivery claims.
The new behavior was added after observing failing tests. Portuguese is general
`pt`, not a region-specific deployment. Real Muse natural-language handling and
notifications remain unverified; the Skill's language instructions require
the additional acceptance cases in docs/ACCEPTANCE.md.

The independent review below is historical 2026-10-14 evidence, not an
independent review of this language update. The official Skill format validator
was rerun successfully for the update with PyYAML in a disposable directory;
no global or product dependency was added (see skill-validation.txt).

| 驗收項 | 本機測試及結果 | Muse 真實端到端 |
|---|---|---|
| Add | 真 SQLite Todo+Outbox；模擬原生 add、快照確認後關聯 ID／synced；通過 | 未執行 |
| Read | 重開 Service 與 subprocess 讀取真實 SQLite；通過 | 未執行 |
| Update 時間／名稱 | 版本遞增，模擬原生 update 保留同 ID、同步新 payload；通過 | 未執行 |
| Update 完成／取消提醒 | 清除期望提醒，模擬 remove，舊 payload gate 拒絕；通過 | 未執行 |
| Delete | 墓碑與恢復資訊保留，模擬取消關聯工作，其他工作不動；通過 | 未執行 |
| Retry | 已知失敗退避；未知結果阻擋；成功丟失 ack 後快照收養，無重複新增；通過 | 未執行 |
| Reconcile | 模擬缺失／改壞／重複的外部狀態，真實協調程式發現並收斂；通過 | 未執行 |
| One-shot | 消失無 receipt 記 expired_unknown，不補建過期工作；到期仍待調度者保留 15 分鐘；通過 | 未執行 |
| Concurrent | 併發同 request 只有一件 Todo；8 同步者只有一筆 operation；8 投遞者只有一個領取成功；通過 | 未執行 |
| PoC 工具 | 暫存舊檔／DB、WAL 一致備份、雜湊、來源變更拒絕、未知檔案保護、Windows junction 拒絕；通過 | 真實拆除未執行 |

上述「模擬」只替代不可存取的外部 cron 邊界，SQLite、Service、同步演算法及 CLI 均為交付的真實程式。不是 Muse 工具實測，不代表原生提醒已部署。獨立代理額外完成 38 次 CLI Skill 流程，記錄見 independent-review.md；Skill 官方格式驗證見 skill-validation.txt。

## 尚待 Muse 完成

- 安全備份與隔離真實舊 PoC，保留不明資料／提醒。
- 載入 Skill、確認工具 schema、正規化全量清單、綁定使用者目的地。
- 確認原生工作能先經 SQLite gate 再通知，並取得真實送達證據。
- 建立唯一每分鐘維護工作，觀測至少一次真實自動重試／對帳執行。
- 按 docs/ACCEPTANCE.md 完成真實自然語言 CRUD、實際通知、取消與故障恢復驗收。

沒有完整清單／持久 marker 時不能安全恢復未知 add；沒有 Agent gate 時不能保證失效 payload 被抑制。未知工具執行權不自動接管；sending 不自動重發。已在途通知無法保證撤回。這些限制已寫入部署協定，不能將本機成功當作原生能力已確認。
