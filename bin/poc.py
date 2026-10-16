import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from muse_todo.poc import backup, inspect_poc, quarantine
from muse_todo.service import TodoError
from muse_todo.i18n import LOCALES, LocalizedParser, exception_message, option_value, translate


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    selected = option_value(None, '--locale', 'en-US')
    locale = selected if selected in LOCALES else 'en-US'
    p = LocalizedParser(locale=locale, allow_abbrev=False,
                        description=translate('Explicit old-PoC backup and reversible quarantine; never removes cron', locale))
    p.add_argument('--locale', choices=LOCALES, default='en-US', help=translate('Language for this invocation (en-US, es, pt)', locale))
    sub = p.add_subparsers(dest='action', required=True)
    inspect = sub.add_parser('inspect', locale=locale)
    inspect.add_argument('--workspace', required=True)
    save = sub.add_parser('backup', locale=locale)
    save.add_argument('--workspace', required=True)
    save.add_argument('--destination', required=True)
    isolate = sub.add_parser('quarantine', locale=locale)
    isolate.add_argument('--manifest', required=True)
    isolate.add_argument('--quiesced', action='store_true', help=translate('Assert old runners and identified PoC cron have stopped', locale))
    a = p.parse_args()
    try:
        if a.action == 'inspect':
            result = inspect_poc(a.workspace)
        elif a.action == 'backup':
            result = {'manifest': str(backup(a.workspace, a.destination))}
        else:
            result = quarantine(a.manifest, quiesced=a.quiesced)
            result['note'] = translate(result['note'], locale)
        print(json.dumps(dict(ok=True, result=result), ensure_ascii=False))
        return 0
    except (TodoError, OSError, sqlite3.Error, ValueError, KeyError) as exc:
        print(json.dumps(dict(ok=False, error=exception_message(exc, locale)), ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
