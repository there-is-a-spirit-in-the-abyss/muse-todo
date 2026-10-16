# Muse Todo language implementation plan

Goal: selectable English, Spanish and Portuguese across the Skill, CLI and
generated reminders while preserving the existing durable protocol.

Design: [DESIGN_LANGUAGES.md](DESIGN_LANGUAGES.md). Python 3.11+ standard library;
no runtime dependencies. Implement inline in the assigned Muse workspace.

1. Add failing real SQLite/subprocess tests for English defaults, persisted
   language selection, invalid-value atomicity, old V1 fallback, localized
   validation and CLI input errors, reminder scheduling and delivery language.
   Verify with `python -m unittest discover -s tests -p test_languages.py -v`.
2. Add a centralized catalog and safe formatting helpers; add settings commands
   and service error localization. Keep all CRUD/sync state transitions intact.
   Pass the current installation locale into reminder text generation.
3. Localize CLI help/input failures, including explicit PoC invocation locale.
   Cover malformed input and CLI failures with subprocess tests before edits.
4. Update SKILL.md, README and command/deployment references with default,
   selection, natural-language behavior and unchanged protocol guarantees.
5. Run the full unittest suite, `scripts/verify.py`, release build and packaged
   test validation. Review the diff and delivery contents. Remove caches and
   obsolete build outputs; ignore runtime data/logs while retaining fixtures.

Review focus: existing databases missing locale; invalid/unhashable locale;
pending or uncertain operations during a switch; delivery after switching;
Unicode titles and errors before a database can be opened. No external Muse
end-to-end success will be claimed from local tests.
