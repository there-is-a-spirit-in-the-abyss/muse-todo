import json
import sqlite3
import sys
from pathlib import Path

from .service import TodoError, TodoService
from .i18n import LocalizedParser, exception_message, option_value, saved_locale, translate


def object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise TodoError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def reject_constant(value):
    raise TodoError(f'invalid JSON constant: {value}')


def main(argv=None):
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    db_path = option_value(argv, '--db')
    locale = saved_locale(db_path) if db_path else 'en-US'
    parser = LocalizedParser(locale=locale, allow_abbrev=False,
                             description=translate('Muse Todo JSON command runner; never calls cron', locale))
    parser.add_argument('--db', required=True, help=translate('Explicit SQLite path; use a new V1 path', locale))
    parser.add_argument('--input', help=translate('UTF-8 JSON file; default stdin', locale))
    args = parser.parse_args(argv)
    try:
        raw = Path(args.input).read_text(encoding='utf-8-sig') if args.input else sys.stdin.read()
        cmd = json.loads(raw, object_pairs_hook=object_pairs, parse_constant=reject_constant)
        result = TodoService(args.db).execute(cmd)
        print(json.dumps({'ok': True, 'result': result}, ensure_ascii=False, allow_nan=False))
        return 0
    except (TodoError, json.JSONDecodeError, UnicodeError, OSError, sqlite3.Error) as exc:
        print(json.dumps({'ok': False, 'error': type(exc).__name__, 'message': exception_message(exc, locale)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
