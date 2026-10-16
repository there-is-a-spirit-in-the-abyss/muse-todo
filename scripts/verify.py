"""Run the real local suite and save evidence without claiming Muse access."""
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / 'evidence'
    output.mkdir(exist_ok=True)
    run = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                         cwd=ROOT, capture_output=True, encoding='utf-8')
    log = run.stdout + run.stderr
    (output / 'python-tests.txt').write_text(log, encoding='utf-8')
    compiled = subprocess.run([sys.executable, '-m', 'compileall', '-q', 'muse_todo', 'bin', 'scripts', 'tests'],
                              cwd=ROOT, capture_output=True, encoding='utf-8')
    (output / 'compile.txt').write_text(compiled.stdout + compiled.stderr or 'compileall: passed\n', encoding='utf-8')
    record = dict(recorded_at=datetime.now(timezone.utc).isoformat(), python=sys.version,
                  platform=platform.platform(), command='python -m unittest discover -s tests -v',
                  python_tests=dict(status='passed' if run.returncode == 0 else 'failed', exit_code=run.returncode,
                                    evidence='python-tests.txt', external_cron='simulated test boundary only'),
                  compileall=dict(exit_code=compiled.returncode),
                  muse_agent_tools=dict(status='not_run', reason='No Muse runtime access; deployment Agent must test'),
                  native_end_to_end=dict(status='not_run', reason='Requires real natural language, cron and delivery'),
                  old_poc_removal=dict(status='not_run', reason='Only backup/quarantine tools tested in disposable fixtures'),
                  periodic_maintenance=dict(status='not_deployed', reason='Requires Muse native periodic Agent job'))
    (output / 'verification.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print(log)
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return int(run.returncode != 0 or compiled.returncode != 0)


if __name__ == '__main__':
    raise SystemExit(main())
