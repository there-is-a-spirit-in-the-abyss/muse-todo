# Muse Todo language design

The installation selects `en-US` (default), `es` (general Spanish), or `pt`
(general Portuguese, contemporary orthography and region-neutral wording where
possible; no implied Brazilian deployment). No OS-language inference is used.

Store `locale` in the existing SQLite `meta` settings. Old V1 databases with no
locale remain English without a schema migration. `init` accepts an optional
locale; `settings.get` reads it and `settings.set` changes only that setting.
Reject unsupported or malformed locale values before changing anything.

Keep JSON keys, commands, IDs, status values, ownership markers, timestamps,
versions, request replay, delivery claims and synchronization rules stable.
Translate human error messages, explanatory `reason`/`next` text, CLI help and
generated reminder prefixes. Preserve titles and other user/external content.
The final delivery gate uses the current locale even if the native job contains
an older prefix. Normal reconciliation repairs changed reminder text; changing
language never replays an operation or resets a delivery receipt.

The Skill reads installation settings before replying and uses the chosen
language for questions, results, failures and maintenance notifications.
Language switching is an explicit user request, not inferred from todo text.
PoC administrative tooling has no installation: its optional `--locale` selects
only that invocation's text. Low-level errors receive localized explanations;
raw diagnostic exception classes and all machine protocol fields remain stable.

Verification uses temporary SQLite databases and CLI subprocesses. No real
todo data, credentials or external Muse deployment is required or delivered.
