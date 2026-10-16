"""Durable intent protocol. The caller, never this module, invokes cron.*."""
import json
from datetime import timedelta
from uuid import uuid4

from .service import TodoError, dump, fields, iso, require_text, timestamp
from .i18n import read_locale, translate


def marker(service, db, rid):
    return f'muse-todo:{service.meta(db, "instance_id")}:{rid}'


def desired(service, db, todo, reminder, now):
    if (todo['deleted_at'] or todo['status'] != 'pending' or not reminder['active']
            or timestamp(reminder['at']) <= now or reminder['delivery_state'] in {'sending', 'delivered'}):
        return None
    return spec_for(todo, reminder, read_locale(db))


def spec_for(todo, reminder, locale='en-US'):
    return dict(todo_id=todo['id'], reminder_id=reminder['id'], version=todo['version'],
                at=reminder['at'], title=todo['title'], enabled=True,
                text=translate('Reminder: {title}', locale, title=todo['title']), delivery='sqlite-gated-agent')


def snapshot_jobs(snapshot, now):
    if not isinstance(snapshot, dict) or snapshot.get('complete') is not True:
        raise TodoError('a complete native cron snapshot is required; partial lists are unsafe')
    fields(snapshot, {'complete', 'observed_at', 'jobs', 'barrier'})
    age = (now - timestamp(snapshot.get('observed_at'))).total_seconds()
    if not -5 <= age <= 60:
        raise TodoError('cron snapshot must be from the last 60 seconds')
    jobs = snapshot.get('jobs')
    if not isinstance(jobs, list):
        raise TodoError('snapshot jobs must be an array')
    ids = set()
    for job in jobs:
        if not isinstance(job, dict):
            raise TodoError('job must be an object')
        jid = require_text(job.get('id'), 'remote job id', 500)
        if jid in ids:
            raise TodoError('snapshot contains duplicate job ids')
        ids.add(jid)
        if not isinstance(job.get('marker', ''), str):
            raise TodoError('job marker must be text')
    return jobs


def scan(service, db, jobs, now):
    """Compare every known reminder, including tombstones; preserve unknown jobs."""
    prefix = f'muse-todo:{service.meta(db, "instance_id")}:'
    known = {marker(service, db, r['id']) for r in db.execute('SELECT id FROM reminders')}
    warnings = [dict(kind='unknown_owned_marker', id=j['id'], marker=j['marker']) for j in jobs
                if j.get('marker', '').startswith(prefix) and j.get('marker') not in known]
    by_marker = {}
    for job in jobs:
        by_marker.setdefault(job.get('marker', ''), []).append(job)
    drift = []
    for row in db.execute('SELECT * FROM todos ORDER BY created_at,id').fetchall():
        t = dict(row)
        todo_drift = []
        todo_wait = False
        for rr in db.execute('SELECT * FROM reminders WHERE todo_id=? ORDER BY slot', (t['id'],)).fetchall():
            r = dict(rr)
            tag = marker(service, db, r['id'])
            matching = sorted(by_marker.get(tag, []), key=lambda x: x['id'])
            want = desired(service, db, t, r, now)
            keep = next((j for j in matching if j['id'] == r['remote_id']), matching[0] if matching else None)
            # Recover an add whose native success wasn't written back to SQLite.
            db.execute('UPDATE reminders SET remote_id=? WHERE id=?', (keep['id'] if keep else None, r['id']))
            if timestamp(r['at']) <= now and r['active'] and not matching and r['delivery_state'] == 'pending':
                db.execute("UPDATE reminders SET delivery_state='expired_unknown' WHERE id=?", (r['id'],))
            base = dict(todo_id=t['id'], version=t['version'], reminder_id=r['id'], marker=tag)
            delay = (now - timestamp(r['at'])).total_seconds()
            if (matching and r['active'] and not t['deleted_at'] and t['status'] == 'pending'
                    and 0 <= delay <= 900 and r['delivery_state'] != 'delivered'):
                # A due one-shot can still be waiting for native dispatch. Do not
                # cancel it or reschedule it into the past during that window.
                todo_wait = True
                warnings.append(dict(kind='native_dispatch_wait', todo_id=t['id'], reminder_id=r['id'],
                                     stale_payload=any(j.get('spec') != spec_for(t, r, read_locale(db)) for j in matching)))
                continue
            if want is None:
                todo_drift.extend(dict(base, kind='remove', remote_id=j['id'], spec=None) for j in matching)
            elif keep is None:
                todo_drift.append(dict(base, kind='add', remote_id=None, spec=want))
            else:
                # Remove duplicates before repairing the survivor.
                todo_drift.extend(dict(base, kind='remove', remote_id=j['id'], spec=None) for j in matching if j['id'] != keep['id'])
                if keep.get('spec') != want:
                    todo_drift.append(dict(base, kind='update', remote_id=keep['id'], spec=want))
        if todo_drift or todo_wait:
            db.execute("UPDATE outbox SET state='pending' WHERE todo_id=? AND version=?", (t['id'], t['version']))
        else:
            db.execute("UPDATE outbox SET state='synced',error=NULL,retry_at=NULL WHERE todo_id=? AND version=?", (t['id'], t['version']))
        drift.extend(todo_drift)
    return drift, warnings


def execute(service, db, c, now):
    name = c['command']
    if name.startswith('delivery.'):
        return delivery(service, db, c, now)
    if name == 'sync.status':
        fields(c, {'command'})
        return dict(service.info(db), snapshot_barrier=barrier(db),
                    outbox=[dict(r) for r in db.execute("SELECT * FROM outbox WHERE state='pending' ORDER BY created_at,id")],
                    blocked=[dict(r) for r in db.execute("SELECT * FROM operations WHERE state IN ('inflight','uncertain')")],
                    delivery_issues=[dict(r) for r in db.execute("SELECT id,todo_id,at,delivery_state FROM reminders WHERE delivery_state IN ('sending','expired_unknown')")])
    if name in {'sync.ack', 'sync.fail', 'sync.recover'}:
        return finish_operation(service, db, c, now)
    if name not in {'sync.next', 'reconcile'}:
        raise TodoError('unknown sync command')
    fields(c, {'command', 'snapshot'})
    jobs = snapshot_jobs(c.get('snapshot'), now)
    busy = db.execute("SELECT * FROM operations WHERE state IN ('inflight','uncertain')").fetchone()
    if busy:
        return dict(status='blocked', operation=None, operation_id=busy['id'],
                    reason=translate('external operation must finish or be explicitly recovered after quiescence', read_locale(db)),
                    expired=timestamp(busy['expires_at']) <= now)
    if c['snapshot'].get('barrier') != barrier(db):
        raise TodoError('snapshot predates an external operation; read sync.status then fetch native jobs again')
    drift, warnings = scan(service, db, jobs, now)
    if name == 'reconcile':
        return dict(drift=drift, warnings=warnings, status='drift' if drift else 'delivery_wait' if any(w['kind'] == 'native_dispatch_wait' for w in warnings) else 'idle')
    waiting = False
    for candidate in drift:
        queue = db.execute('SELECT * FROM outbox WHERE todo_id=? AND version=?', (candidate['todo_id'], candidate['version'])).fetchone()
        if queue['retry_at'] and timestamp(queue['retry_at']) > now:
            waiting = True
            continue
        op = dict(candidate, id=str(uuid4()), expires_at=iso(now + timedelta(minutes=5)))
        db.execute('INSERT INTO operations(id,todo_id,version,reminder_id,kind,remote_id,spec,state,created_at,expires_at) VALUES (?,?,?,?,?,?,?,\'inflight\',?,?)',
                   (op['id'], op['todo_id'], op['version'], op['reminder_id'], op['kind'], op['remote_id'], dump(op['spec']), iso(now), op['expires_at']))
        db.execute('UPDATE outbox SET attempts=attempts+1 WHERE id=?', (queue['id'],))
        return dict(status='operation', operation=op, warnings=warnings)
    return dict(status='retry_wait' if waiting else 'delivery_wait' if any(w['kind'] == 'native_dispatch_wait' for w in warnings) else 'idle', operation=None, warnings=warnings)


def barrier(db):
    last = db.execute('SELECT id,state FROM operations ORDER BY rowid DESC LIMIT 1').fetchone()
    return f'{last["id"]}:{last["state"]}' if last else None


def finish_operation(service, db, c, now):
    name = c['command']
    allowed = {'command', 'operation_id'} | ({'remote_id'} if name == 'sync.ack' else
                                            {'outcome', 'error'} if name == 'sync.fail' else {'quiesced', 'evidence'})
    fields(c, allowed)
    oid = require_text(c.get('operation_id'), 'operation_id')
    row = db.execute('SELECT * FROM operations WHERE id=?', (oid,)).fetchone()
    if not row:
        raise TodoError('unknown operation')
    op = dict(row)
    if name == 'sync.ack':
        remote = require_text(c.get('remote_id'), 'remote_id', 500)
        if op['kind'] != 'add' and remote != op['remote_id']:
            raise TodoError('remote_id differs from reserved operation')
        if op['state'] == 'acked':
            if op['result'] != remote:
                raise TodoError('conflicting ack')
            return {'acknowledged': True}
        if op['state'] not in {'inflight', 'uncertain'}:
            raise TodoError('operation is already closed; take a new snapshot')
        db.execute("UPDATE operations SET state='acked',result=? WHERE id=?", (remote, oid))
        # This only records observed identity; it never writes Todo fields or marks newer versions synced.
        if op['kind'] != 'remove':
            db.execute('UPDATE reminders SET remote_id=? WHERE id=?', (remote, op['reminder_id']))
        else:
            db.execute('UPDATE reminders SET remote_id=NULL WHERE id=? AND remote_id=?', (op['reminder_id'], remote))
        return {'acknowledged': True}
    if name == 'sync.recover':
        if c.get('quiesced') is not True:
            raise TodoError('ensure the previous native invocation has stopped before recovery')
        evidence = require_text(c.get('evidence'), 'evidence', 2000)
        if op['state'] == 'recovered':
            return {'recovered': True}
        if op['state'] not in {'inflight', 'uncertain'}:
            raise TodoError('operation cannot be recovered in current state')
        db.execute("UPDATE operations SET state='recovered',result=? WHERE id=?", (evidence, oid))
        return {'recovered': True, 'next': translate('fetch a new complete native snapshot; never replay the old intent', read_locale(db))}
    error = require_text(c.get('error'), 'error', 2000)
    outcome = c.get('outcome')
    if not isinstance(outcome, str) or outcome not in {'not_applied', 'unknown'}:
        raise TodoError('outcome must be not_applied or unknown')
    if op['state'] in {'failed', 'uncertain'} and op['error'] == error:
        return {'recorded': True, 'state': op['state']}
    if op['state'] != 'inflight':
        raise TodoError('operation already closed or uncertain')
    state = 'failed' if outcome == 'not_applied' else 'uncertain'
    db.execute('UPDATE operations SET state=?,error=? WHERE id=?', (state, error, oid))
    queue = db.execute('SELECT attempts FROM outbox WHERE todo_id=? AND version=?', (op['todo_id'], op['version'])).fetchone()
    seconds = min(3600, 30 * 2 ** min(queue['attempts'] - 1, 7))
    db.execute('UPDATE outbox SET error=?,retry_at=? WHERE todo_id=? AND version=?',
               (error, iso(now + timedelta(seconds=seconds)), op['todo_id'], op['version']))
    return {'recorded': True, 'state': state}


def delivery(service, db, c, now):
    name = c['command']
    if name not in {'delivery.check', 'delivery.ack'}:
        raise TodoError('unknown delivery command')
    fields(c, {'command', 'reminder_id', 'version', 'at'} if name == 'delivery.check' else {'command', 'reminder_id', 'token', 'receipt'})
    rid = require_text(c.get('reminder_id'), 'reminder_id')
    row = db.execute('SELECT * FROM reminders WHERE id=?', (rid,)).fetchone()
    if not row:
        raise TodoError('unknown reminder')
    r = dict(row)
    t = service.row(db, r['todo_id'])
    if name == 'delivery.ack':
        token = require_text(c.get('token'), 'delivery token')
        receipt = require_text(c.get('receipt'), 'receipt', 2000)
        if token != r['delivery_token']:
            raise TodoError('stale delivery token')
        if r['delivery_state'] == 'delivered' and r['receipt'] != receipt:
            raise TodoError('conflicting delivery receipt')
        db.execute("UPDATE reminders SET delivery_state='delivered',receipt=? WHERE id=?", (receipt, rid))
        return {'acknowledged': True}
    if type(c.get('version')) is not int or not isinstance(c.get('at'), str):
        raise TodoError('delivery requires version and at from native payload')
    if (c['version'] != t['version'] or c['at'] != r['at'] or not r['active']
            or t['deleted_at'] or t['status'] != 'pending'):
        return {'deliver': False, 'reason': translate('stale or inactive reminder', read_locale(db))}
    delay = (now - timestamp(r['at'])).total_seconds()
    if delay < 0 or delay > 900:
        return {'deliver': False, 'reason': translate('outside delivery time window (0..900 seconds late)', read_locale(db))}
    if r['delivery_state'] in {'sending', 'delivered'}:
        return {'deliver': False, 'reason': translate('delivery already claimed or delivered', read_locale(db))}
    token = str(uuid4())
    db.execute("UPDATE reminders SET delivery_state='sending',delivery_token=? WHERE id=?", (token, rid))
    return dict(deliver=True, token=token, text=translate('Reminder: {title}', read_locale(db), title=t['title']), todo_id=t['id'], reminder_id=rid)
