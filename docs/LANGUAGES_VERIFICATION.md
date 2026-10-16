# Language verification — 2026-10-16

Run from `C:\Users\渊中有灵\Desktop\Muse_todo` on Python 3.11.9 / Windows.

| Command or check | Result |
|---|---|
| `python -X utf8 -m unittest discover -s tests -p test_languages.py -v` before implementation | Expected missing-settings/localization failures observed; later targeted red tests exposed untranslated CLI choice text, early argparse errors and two human validation labels |
| `python -X utf8 scripts/verify.py` | Exit 0; full suite 64 passed, 0 failed, 0 skipped; compileall exit 0 |
| `python -X utf8 scripts/build_release.py` | Exit 0; allowlisted source/test/documentation archive rebuilt; current SHA256 in dist/SHA256SUMS.txt |
| `python -X utf8 scripts/check_release.py` | Exit 0; extracted member hashes passed, packaged full suite 64 passed |
| `python -X utf8 C:/Users/渊中有灵/.codex/skills/.system/skill-creator/scripts/quick_validate.py C:/Users/渊中有灵/Desktop/Muse_todo` | `Skill is valid!`, exit 0 with PyYAML installed only in a disposable temporary directory and exposed through that subprocess's PYTHONPATH |
| AST audit of literal `TodoError` messages | All literal messages have Spanish and Portuguese catalog entries; interpolated field/key/file errors use catalog patterns |
| Chinese source-text audit | No Chinese lines in service, store, sync, CLI, PoC module or PoC CLI |
| Reminder-path audit | Scheduled specs and final delivery both call the locale-aware translator; no alternative hardcoded prefix path |
| Runtime-data audit | No database, SQLite sidecar or runtime log files found in the source workspace |

The 16 language tests exercise English defaults, existing V1 fallback, persisted
settings, malformed settings without mutations, localized service/CLI messages
and help, reminders in all three languages, Unicode titles, pending external
operations, request replay and delivery-claim preservation. Protocol field names,
status values, ownership markers and business transitions remain unchanged.

Logs: `evidence/python-tests.txt`, `compile.txt`, `verification.json`,
`release-check.txt` and `skill-validation.txt`. The first direct format-validator
attempt could not import PyYAML; temporary validation-only installation resolved
that tooling dependency. The product still needs only Python's standard library.

Existing evidence and release files are preserved. Only the newly rebuilt
`dist/muse-todo-v1.tar.gz` is the current language release; preexisting ZIP files
are historical. Dist, caches, runtime data and logs are ignored. Tests create
synthetic records only inside temporary directories.

Real Muse Agent language understanding, Skill selection, native cron, actual
notifications, deployment and old-PoC removal were not executed. The additional
live-language cases in ACCEPTANCE.md remain required before claiming native
end-to-end acceptance. No credentials, external deployment or publication used.
