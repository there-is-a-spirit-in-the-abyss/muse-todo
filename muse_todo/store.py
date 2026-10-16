import sqlite3
from contextlib import contextmanager


SCHEMA = '''
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE todos(
 id TEXT PRIMARY KEY, title TEXT NOT NULL, due_at TEXT,
 status TEXT NOT NULL CHECK(status IN ('pending','completed','canceled')),
 reminder_mode TEXT NOT NULL CHECK(reminder_mode IN ('default','custom','none')),
 reminder_times TEXT NOT NULL, version INTEGER NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT);
CREATE TABLE reminders(
 id TEXT PRIMARY KEY, todo_id TEXT NOT NULL REFERENCES todos(id), slot INTEGER NOT NULL,
 at TEXT NOT NULL, active INTEGER NOT NULL, remote_id TEXT,
 delivery_state TEXT NOT NULL DEFAULT 'pending', delivery_token TEXT,
 receipt TEXT, UNIQUE(todo_id,slot));
CREATE TABLE outbox(
 id TEXT PRIMARY KEY, todo_id TEXT NOT NULL REFERENCES todos(id), version INTEGER NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('pending','synced','superseded')),
 attempts INTEGER NOT NULL DEFAULT 0, error TEXT, retry_at TEXT,
 created_at TEXT NOT NULL, UNIQUE(todo_id,version));
CREATE TABLE requests(id TEXT PRIMARY KEY, body TEXT NOT NULL, result TEXT NOT NULL);
CREATE TABLE operations(
 id TEXT PRIMARY KEY, todo_id TEXT NOT NULL, version INTEGER NOT NULL,
 reminder_id TEXT NOT NULL, kind TEXT NOT NULL, remote_id TEXT, spec TEXT,
 state TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
 result TEXT, error TEXT);
CREATE UNIQUE INDEX single_external_operation ON operations((1))
 WHERE state IN ('inflight','uncertain');
PRAGMA user_version=1;
'''


@contextmanager
def transaction(path):
    db = sqlite3.connect(path, timeout=15, isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA busy_timeout=15000')
        db.execute('PRAGMA synchronous=FULL')
        db.execute('BEGIN IMMEDIATE')
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()
