# 飛書個人 Todo 業務參考

參考來源為使用者提供的 `C:\Users\渊中有灵\Desktop\huiyang_source` 原始檔及測試，只讀取、不修改、不移植程式／Schema。團隊網頁、群主權限、團隊分工、週報不納入 V1。

| 已閱讀來源（相對參考專案） | 觀察 | V1 採用方式 |
|---|---|---|
| src/huiyang/services/todos.py:78 | 有截止且未指定提醒時，前一小時及截止時各提醒一次；明確 times 取代預設 | default/custom/none 三種持久模式 |
| tests/test_todo_service.py:73 | 個人提醒走私聊，明確時間取代預設 | 綁定使用者原生目的地，由 Muse 實測 |
| src/huiyang/services/todos.py:127 | 完成／取消取消 pending reminders | 同事務寫 Outbox，原生 remove，delivery gate 檢查 |
| src/huiyang/services/todos.py:193 | 更新截止或提醒時先取消原提醒再生成 | 原生優先 update 穩定邏輯提醒；不複製先刪後增實作 |
| src/huiyang/services/todos.py:226 | 舊服務取消提醒後硬刪除 | V1 使用墓碑，保留跨系統恢復資訊 |
| src/huiyang/agent/structured_llm.py:80 | 明確命令執行；真歧義詢問；個人任務可無專案 | 不新增專案管理，無歧義便直接操作 |
| src/huiyang/agent/structured_llm.py:83 | 以 current_time/timezone 解讀，含時區 ISO8601 | Muse 使用者時區，不照搬 Codex 時區 |
| src/huiyang/agent/structured_llm.py:85 | update_fields 區分未改與清空；順序指代使用真實 task_id | changes key presence；前次展示順序作引用，衝突重讀 |
| src/huiyang/repositories/sqlalchemy.py:38 | 活躍列表排除終態，按截止及建立時間排序 | SQLite list 預設 pending，可查全部、終態及墓碑 |
| src/huiyang/domain/models.py:71 | 逾期由截止與非終態推導 | overdue 衍生欄位，無額外業務狀態 |
| src/huiyang/config.py:26 | 不啟用額外逾期重複通知 | 不引入逾期催辦／計劃系統 |

飛書目前也有 description、priority、進行中、阻塞等欄位；本輪以使用者要求的 CRUD、完成與提醒一致性為範圍，未擴充這些功能。也沒有驗證飛書生產環境運行狀態；上述為提供的原始碼與測試內容，不是本輪飛書實測結果。

特別修正的設計邊界：飛書更新截止會重建提醒，程式中的 null／空陣列語義不宜直接搬入新版本。V1 使用明確提醒模式，取消後只改截止不重新開啟；custom 絕對時間不因改截止而平移。過去預設時刻略過；過去明確提醒拒絕，避免積壓提醒立即噴送。
