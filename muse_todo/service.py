import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .store import SCHEMA, transaction
from .i18n import LOCALES, read_locale, saved_locale, translate


class TodoError(ValueError):
    """Invalid command or a conflict requiring Agent attention."""


def timestamp(value):
    if not isinstance(value, str):
        raise TodoError('time must be an ISO8601 string with timezone')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise TodoError('invalid ISO8601 time') from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise TodoError('time must include timezone')
    return result.astimezone(timezone.utc)


def iso(value):
    return value.astimezone(timezone.utc).isoformat(timespec='microseconds').replace('.000000', '').replace('+00:00', 'Z')


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def display_zone(name):
    return timezone.utc if name == 'UTC' else ZoneInfo(name)


def require_text(value, field, maximum=255):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise TodoError(f'{field} must be nonempty text, at most {maximum} characters')
    return value.strip()


def fields(command, allowed):
    unknown = set(command) - set(allowed)
    if unknown:
        raise TodoError(f'unknown fields: {sorted(unknown)}')


class TodoService:
    def __init__(self, path, clock=None):
        self.path = Path(path).expanduser().resolve()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def execute(self, command):
        locale = saved_locale(self.path)
        if (not self.path.is_file() and isinstance(command, dict) and command.get('command') == 'init'
                and isinstance(command.get('locale'), str) and command['locale'] in LOCALES):
            locale = command['locale']
        try:
            return self._execute(command)
        except TodoError as exc:
            raise TodoError(translate(str(exc), locale)) from exc

    def _execute(self, command):
        if not isinstance(command, dict):
            raise TodoError('command must be an object')
        name = command.get('command')
        if not isinstance(name, str):
            raise TodoError('command must be text')
        if name == 'init':
            return self._init(command)
        if not self.path.is_file():
            raise TodoError('database missing; run init explicitly')
        with transaction(self.path) as db:
            if db.execute('PRAGMA user_version').fetchone()[0] != 1:
                raise TodoError('unsupported database schema')
            now = self.clock()
            if name in {'settings.get', 'settings.set'}:
                fields(command, {'command'} if name == 'settings.get' else {'command', 'locale'})
                if name == 'settings.set':
                    locale = self.validate_locale(command.get('locale'))
                    db.execute("INSERT INTO meta(key,value) VALUES ('locale',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (locale,))
                return {'locale': read_locale(db)}
            if name in {'add', 'update', 'delete'}:
                return self._mutate(db, command, now)
            if name == 'get':
                fields(command, {'command', 'id'})
                return self.view(db, command.get('id'), now)
            if name == 'list':
                return self._list(db, command, now)
            if isinstance(name, str) and (name.startswith('sync.') or name.startswith('delivery.') or name == 'reconcile'):
                from .sync import execute
                return execute(self, db, command, now)
            raise TodoError('unknown command')

    def _init(self, c):
        fields(c, {'command', 'timezone', 'locale'})
        locale = self.validate_locale(c.get('locale', 'en-US'))
        tz = c.get('timezone', 'UTC')
        try:
            display_zone(tz)
        except (ValueError, TypeError, ZoneInfoNotFoundError) as exc:
            raise TodoError('IANA timezone unavailable; use UTC or install system tzdata') from exc
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Never apply the new schema over an old PoC database.
        with transaction(self.path) as db:
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if tables:
                if 'meta' not in tables or db.execute('PRAGMA user_version').fetchone()[0] != 1:
                    raise TodoError('existing database is not Muse Todo V1; preserve it')
                if self.meta(db, 'timezone') != tz:
                    raise TodoError('timezone differs from initialized configuration')
                if 'locale' in c and read_locale(db) != locale:
                    raise TodoError('locale differs from initialized configuration; use settings.set')
                return self.info(db)
            # executescript commits implicitly, so execute statements individually.
            for statement in SCHEMA.split(';'):
                if statement.strip():
                    db.execute(statement)
            db.executemany('INSERT INTO meta VALUES (?,?)', [('instance_id', str(uuid4())), ('timezone', tz), ('locale', locale)])
            return self.info(db)

    @staticmethod
    def validate_locale(locale):
        if not isinstance(locale, str) or locale not in LOCALES:
            raise TodoError('unsupported locale; choose en-US, es, or pt')
        return locale

    @staticmethod
    def meta(db, key):
        return db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()[0]

    def info(self, db):
        return {'schema': 1, 'instance_id': self.meta(db, 'instance_id'), 'timezone': self.meta(db, 'timezone'), 'locale': read_locale(db)}

    def row(self, db, tid):
        if not isinstance(tid, str):
            raise TodoError('id required')
        row = db.execute('SELECT * FROM todos WHERE id=?', (tid,)).fetchone()
        if row is None:
            raise TodoError('todo not found')
        return dict(row)

    def view(self, db, tid, now):
        t = self.row(db, tid)
        t['overdue'] = bool(t['due_at'] and timestamp(t['due_at']) < now and t['status'] == 'pending' and not t['deleted_at'])
        t['timezone'] = self.meta(db, 'timezone')
        t['due_local'] = timestamp(t['due_at']).astimezone(display_zone(t['timezone'])).isoformat() if t['due_at'] else None
        t['reminder_times'] = json.loads(t['reminder_times'])
        t['reminders'] = [dict(r) for r in db.execute('SELECT * FROM reminders WHERE todo_id=? AND active=1 ORDER BY slot', (tid,))]
        last = db.execute('SELECT state,attempts,error,retry_at FROM outbox WHERE todo_id=? AND version=?', (tid, t['version'])).fetchone()
        t['sync'] = dict(last) if last else None
        return t

    def _list(self, db, c, now):
        fields(c, {'command', 'status', 'include_deleted', 'query'})
        if 'include_deleted' in c and type(c['include_deleted']) is not bool:
            raise TodoError('include_deleted must be boolean')
        status = c.get('status', 'pending')
        if not isinstance(status, str) or status not in {'pending', 'completed', 'canceled', 'all'}:
            raise TodoError('invalid status filter')
        query = c.get('query', '')
        if not isinstance(query, str):
            raise TodoError('query must be text')
        rows = db.execute('SELECT id FROM todos ORDER BY due_at IS NULL,julianday(due_at),julianday(created_at),id').fetchall()
        todos = [self.view(db, r['id'], now) for r in rows]
        return {'todos': [t for t in todos if (c.get('include_deleted') or not t['deleted_at'])
                          and (status == 'all' or t['status'] == status) and query.casefold() in t['title'].casefold()]}

    def _mutate(self, db, c, now):
        name = c['command']
        allowed = {'command', 'request_id', 'title', 'due_at', 'reminder'} if name == 'add' else {'command', 'request_id', 'id', 'expected_version'} | ({'changes'} if name == 'update' else set())
        fields(c, allowed)
        key = require_text(c.get('request_id'), 'request_id', 200)
        body = dump(c)
        replay = db.execute('SELECT * FROM requests WHERE id=?', (key,)).fetchone()
        if replay:
            if replay['body'] != body:
                raise TodoError('request_id reused with different content')
            return json.loads(replay['result'])
        if name == 'add':
            t = dict(id=str(uuid4()), title=require_text(c.get('title'), 'title'), due_at=None,
                     status='pending', reminder_mode='default', reminder_times='[]', version=1,
                     created_at=iso(now), updated_at=iso(now), deleted_at=None)
            changes = {k: v for k, v in c.items() if k in {'due_at', 'reminder'}}
        else:
            t = self.row(db, c.get('id'))
            if type(c.get('expected_version')) is not int or c['expected_version'] != t['version']:
                raise TodoError('version conflict; reread todo before changing it')
            if t['deleted_at']:
                raise TodoError('todo is deleted')
            t['version'] += 1
            t['updated_at'] = iso(now)
            changes = c.get('changes') if name == 'update' else {}
            if name == 'delete':
                t['deleted_at'] = iso(now)
        if not isinstance(changes, dict) or (name == 'update' and not changes):
            raise TodoError('changes must be a nonempty object')
        fields(changes, {'title', 'due_at', 'status', 'reminder'})
        if 'title' in changes:
            t['title'] = require_text(changes['title'], 'title')
        if 'due_at' in changes:
            t['due_at'] = None if changes['due_at'] is None else iso(timestamp(changes['due_at']))
        if 'status' in changes:
            if not isinstance(changes['status'], str) or changes['status'] not in {'pending', 'completed', 'canceled'}:
                raise TodoError('invalid status')
            t['status'] = changes['status']
        if 'reminder' in changes:
            r = changes['reminder']
            if not isinstance(r, dict):
                raise TodoError('reminder must be an object')
            fields(r, {'mode', 'times'})
            mode = r.get('mode')
            if not isinstance(mode, str) or mode not in {'default', 'custom', 'none'}:
                raise TodoError('invalid reminder mode')
            times = r.get('times', [])
            if mode != 'custom' and 'times' in r:
                raise TodoError('times only permitted for custom reminders')
            if mode == 'custom':
                if not isinstance(times, list) or not 1 <= len(times) <= 10:
                    raise TodoError('custom reminders require 1..10 times')
                times = sorted({iso(timestamp(x)) for x in times}, key=timestamp)
                if any(timestamp(x) <= now for x in times):
                    raise TodoError('explicit reminders must be in the future')
            t['reminder_mode'], t['reminder_times'] = mode, dump(times)
        if name == 'add':
            db.execute('INSERT INTO todos VALUES (:id,:title,:due_at,:status,:reminder_mode,:reminder_times,:version,:created_at,:updated_at,:deleted_at)', t)
        else:
            db.execute('UPDATE todos SET title=:title,due_at=:due_at,status=:status,reminder_mode=:reminder_mode,reminder_times=:reminder_times,version=:version,updated_at=:updated_at,deleted_at=:deleted_at WHERE id=:id', t)
        times = []
        if t['status'] == 'pending' and not t['deleted_at']:
            if t['reminder_mode'] == 'custom':
                times = json.loads(t['reminder_times'])
            elif t['reminder_mode'] == 'default' and t['due_at']:
                due = timestamp(t['due_at'])
                times = [iso(due - timedelta(hours=1)), iso(due)]
        self._set_reminders(db, t['id'], times, now)
        db.execute("UPDATE outbox SET state='superseded' WHERE todo_id=? AND state='pending'", (t['id'],))
        db.execute("INSERT INTO outbox(id,todo_id,version,state,created_at) VALUES (?,?,?,'pending',?)", (str(uuid4()), t['id'], t['version'], iso(now)))
        result = self.view(db, t['id'], now)
        db.execute('INSERT INTO requests VALUES (?,?,?)', (key, body, dump(result)))
        return result

    @staticmethod
    def _set_reminders(db, tid, times, now):
        previous = {r['slot']: dict(r) for r in db.execute('SELECT * FROM reminders WHERE todo_id=?', (tid,))}
        db.execute('UPDATE reminders SET active=0 WHERE todo_id=?', (tid,))
        for slot, at in enumerate(times):
            old = previous.get(slot)
            active = int(timestamp(at) > now or bool(old and old['at'] == at and old['active']))
            if old:
                # A new time is a new delivery; title-only edits preserve delivery receipts.
                if old['at'] == at:
                    db.execute('UPDATE reminders SET active=? WHERE id=?', (active, old['id']))
                else:
                    db.execute("UPDATE reminders SET at=?,active=?,delivery_state='pending',delivery_token=NULL,receipt=NULL WHERE id=?", (at, active, old['id']))
            else:
                db.execute('INSERT INTO reminders(id,todo_id,slot,at,active) VALUES (?,?,?,?,?)', (str(uuid4()), tid, slot, at, active))
