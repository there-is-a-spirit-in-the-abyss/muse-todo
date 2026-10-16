# Muse Todo V1

**Personal tasks and native reminders, managed through conversation in Muse.**

Muse Todo is a Skill-based plugin with a local SQLite database. Add a task,
change its deadline, complete it, or cancel its reminder using natural language.
English is the default; Spanish and Portuguese are supported.

## Deploy with Muse

Attach the complete project archive to Muse and send this instruction:

> Extract this package, read and execute MUSE_PROMPT.md at the project root, and start installation, Skill loading, and reminder acceptance testing now.

Equivalent instruction in Chinese:

> 請解壓這個套件，閱讀並執行套件根目錄的 MUSE_PROMPT.md，直接開始安裝、載入 Skill，並完成提醒功能驗收。

You can also provide the full English deployment prompt directly:

1. Give Muse the complete repository or the current `muse-todo-v1.tar.gz` release
   archive. A private repository requires authorized access; an attached archive
   works without sharing GitHub credentials.
2. Open **[MUSE_PROMPT.md](MUSE_PROMPT.md)** and copy its complete English contents
   into Muse.
3. Muse follows the supplied deployment procedure, loads the Skill, connects
   native cron and notifications, and runs live acceptance. Its final report
   identifies readiness, evidence, and any platform blockers.

Try these after deployment:

```text
Add a task to buy groceries tomorrow at 6 PM and remind me 30 minutes before.
Show my open tasks.
Move the grocery task to Friday at 7 PM.
Mark the grocery task as complete.
Use Spanish.
```

Muse uses your confirmed timezone and asks when a time is ambiguous. Existing
installation data is preserved on repeat deployment. The plugin requires Python
3.11+, SQLite support, and Muse tools that can schedule an Agent with Python and
notification access. Live reminder readiness is established during deployment.

## How it works

Personal todos for Muse Agent, with a Skill, Python 3.11+ standard library,
SQLite and native cron. English (`en-US`) is the default; Spanish (`es`) and
Portuguese (`pt`) are selectable. Includes CRUD, a transactional outbox,
idempotent requests, version checks, durable synchronization, reconciliation,
gated reminder delivery, and reversible old-PoC backup tools.

## Language selection

Initialize with `{"command":"init","timezone":"UTC"}`. Optionally include
`"locale":"es"` or `"locale":"pt"`. On an existing installation send either
JSON command through the normal CLI:

```json
{"command":"settings.get"}
{"command":"settings.set","locale":"es"}
```

Each line is a separate command. Save a command in a UTF-8 file and run
`python bin/todo.py --db /absolute/path/to/todos.db --input language.json`.
Use `en-US` to restore English or `pt` for Portuguese. The setting persists in
that database and governs Skill responses, CLI messages/help and reminder text.
Old V1 installations without a setting default to English. Unsupported locale
values are rejected without changes. Repeating `init` never changes a saved
language; use `settings.set`.

In Muse, explicitly ask “Use Spanish”, “Cambia el idioma a portugués”, or
“Muda o idioma para inglês”. Titles stay in the language you wrote them.
Spanish uses general wording; Portuguese uses contemporary orthography and
region-neutral wording where possible under `pt`. Language selection does not
change timezone or date parsing. JSON keys, status values, markers and IDs
remain unchanged.

After a language change, the Skill runs normal reconciliation to update future
native reminder text. The delivery gate uses the current language even before
that update completes. Operation recovery and delivery claims retain their
existing safeguards. PoC administration has no installation database; put
`--locale es` or `--locale pt` before its subcommand, for example
`python bin/poc.py --locale pt inspect --workspace /absolute/path/to/workspace`.
See [language design](docs/DESIGN_LANGUAGES.md) and
[implementation plan](docs/PLAN_LANGUAGES.md).

## Run locally

```sh
python -m unittest discover -s tests -v
python bin/todo.py --db /absolute/path/to/new-v1.db --input init.json
```

Use `{"command":"init","timezone":"UTC"}` in `init.json`. See the
[JSON command reference](references/COMMANDS.md) for other operations. No pip
installation, server or Feishu credentials are required. The program accepts
stdin and uses UTF-8 for Unicode input and output.

## Included files

| Path | Purpose |
|---|---|
| MUSE_PROMPT.md | Copy-and-paste English prompt that starts Muse deployment |
| SKILL.md | Natural language operations and tool coordination in Muse |
| muse_todo/service.py, store.py | Validation, CRUD, transactions and schema |
| muse_todo/sync.py | Outbox coordination, recovery, reconciliation and delivery gate |
| bin/todo.py | JSON CLI independent of the current working directory |
| bin/poc.py, muse_todo/poc.py | Old PoC backups, hash verification and reversible quarantine |
| tests/ | Real SQLite, CLI subprocess and simulated external scheduling tests |
| docs/DEPLOYMENT.md | Muse installation, old-version removal and rollback |
| docs/ACCEPTANCE.md | Live natural language, cron and notification acceptance |
| references/CRON_BRIDGE.md | Agent protocol for native cron tools |
| evidence/ | Local verification output and test classifications |

## Verification limits

Local tests verify Python, SQLite and the coordination protocol. Native tools
come from a separate Muse environment. No SSH access or modification of the
existing Muse installation is involved. Before live use, the Muse Agent must
confirm native tool schemas, bind execution and notification destinations,
create the single maintenance job and complete actual end-to-end acceptance.
Local simulations do not establish that those steps passed.

Unknown native results remain recorded and block retries until the previous
invocation has stopped and a new snapshot supports recovery. Synchronization is
eventually consistent; it does not promise exactly-once execution across SQLite,
cron and message delivery.

Give Muse the complete release package and the [handoff instructions](docs/MUSE_HANDOFF.md).
See the [language verification report](docs/LANGUAGES_VERIFICATION.md) for the
current results and the [original test report](evidence/TEST_REPORT.md) for
historical checks. Source releases contain no installed database or real tasks.
The repository is initially private. Only users granted access can view it;
public promotion can follow a later visibility change.
