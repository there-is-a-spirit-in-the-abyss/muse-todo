# Muse Todo · Conversational tasks and reminders

English | [简体中文](README.zh-CN.md)

## Features

**Tell Muse what you need to do. Let it keep the task and remind you at the right time.**

- **Manage tasks through conversation:** add, find, edit, complete or delete todos in natural language.
- **Schedule native reminders:** set a reminder time and keep it in sync when you reschedule, finish or cancel a task.
- **Keep a lasting task record:** tasks are stored in a local SQLite database in your Muse environment, ready for later conversations.
- **No separate server:** runs inside your Muse environment without Feishu or a separate web service.

### Example: a meeting at 21:00

Ask Muse to remind you about a meeting at 21:00. It confirms the time and records the meeting in your task list.
These supplied screenshots show the request and the confirmation in Chinese:

<img src="docs/images/muse-reminder-request.jpg" alt="A request asking Muse for a meeting reminder at 21:00" width="640">

<img src="docs/images/muse-reminder-confirmation.jpg" alt="Muse confirms the reminder and records the meeting in the todo list" width="640">

The screenshots illustrate the conversation; actual reminder delivery must pass acceptance in your own Muse environment.
The plugin defaults to English and supports Spanish and Portuguese. The Chinese conversation shown here does not establish Chinese plugin support.

## Download

**[Download the complete Muse Todo ZIP](https://github.com/there-is-a-spirit-in-the-abyss/muse-todo/archive/refs/heads/main.zip)**

[GitHub repository](https://github.com/there-is-a-spirit-in-the-abyss/muse-todo). This is the complete project archive; no desktop installer selection is needed.
The repository is currently private, so access and downloads require an authorized GitHub account.
You can attach the downloaded ZIP directly to Muse.

## Installation and deployment

**Send Muse this one instruction with the repository URL:**

```text
Get the complete project from https://github.com/there-is-a-spirit-in-the-abyss/muse-todo, read and execute MUSE_PROMPT.md at the project root, and complete installation, Skill loading and live native-reminder acceptance. Back up any existing installation and preserve its task data.
```

If Muse cannot access the private repository, attach the complete ZIP above and send:

```text
Extract the complete Muse Todo project archive attached to this message, read and execute MUSE_PROMPT.md at the project root, and complete installation, Skill loading and live native-reminder acceptance. Back up any existing installation and preserve its task data.
```

Muse follows the supplied procedure to check its environment, load the Skill, connect native scheduling and notifications, and report acceptance results.
Its runtime needs Python 3.11+, SQLite, and Muse tools with Python execution, scheduling and notification access.
No separate server or Feishu credentials are required.

[Full deployment prompt](MUSE_PROMPT.md) · [Installation, upgrades and rollback](docs/DEPLOYMENT.md) · [Deployment handoff](docs/MUSE_HANDOFF.md)

<details>
<summary>View the supplied deployment conversation</summary>

This screenshot shows an earlier handoff instruction. Use the instructions above and the current repository documents for installation.

<img src="docs/images/muse-deployment-example.jpg" alt="Sending the complete Muse Todo archive and deployment instructions to Muse" width="420">

</details>

<details>
<summary>Technical details, languages and local verification</summary>

### How it works

Personal todos for Muse Agent, with a Skill, Python 3.11+ standard library,
SQLite and native cron. English (`en-US`) is the default; Spanish (`es`) and
Portuguese (`pt`) are selectable. Includes CRUD, a transactional outbox,
idempotent requests, version checks, durable synchronization, reconciliation,
gated reminder delivery, and reversible old-PoC backup tools.

### Language selection

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

In Muse, explicitly ask to use English, Spanish, or Portuguese.
Titles stay in the language you wrote them.
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

### Run locally

```sh
python -m unittest discover -s tests -v
python bin/todo.py --db /absolute/path/to/new-v1.db --input init.json
```

Use `{"command":"init","timezone":"UTC"}` in `init.json`. See the
[JSON command reference](references/COMMANDS.md) for other operations. No pip
installation, server or Feishu credentials are required. The program accepts
stdin and uses UTF-8 for Unicode input and output.

### Included files

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

### Verification limits

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

</details>
