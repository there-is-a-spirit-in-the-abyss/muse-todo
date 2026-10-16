"""Explicit-path backup and reversible quarantine; no cron or configuration edits."""
import hashlib
import json
import shutil
import sqlite3
import stat
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .service import TodoError, iso


SKILL_FILES = ('skills/todo/SKILL.md', 'skills/todo/bin/todo.py')
DB_FILE = 'data/todo/todos.db'
FILES = (*SKILL_FILES, DB_FILE, DB_FILE + '-wal', DB_FILE + '-shm', DB_FILE + '-journal')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def safe_path(root, relative):
    path = root / relative
    if not path.resolve().is_relative_to(root):
        raise TodoError('target escapes workspace')
    for part in [path, *path.parents]:
        if part == root:
            break
        try:
            reparse = getattr(part.lstat(), 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)
        except FileNotFoundError:
            reparse = 0
        if part.is_symlink() or reparse:
            raise TodoError('symlink/junction target is not safe to quarantine')
    return path


def inspect_poc(workspace):
    root = Path(workspace).expanduser().resolve()
    files = []
    for rel in FILES:
        p = safe_path(root, rel)
        if p.exists():
            if not p.is_file():
                raise TodoError('expected a regular file: ' + rel)
            files.append(dict(path=rel, size=p.stat().st_size, sha256=sha(p)))
    skill = safe_path(root, 'skills/todo')
    unknown = []
    if skill.exists():
        for p in skill.rglob('*'):
            rel = p.relative_to(root).as_posix()
            safe_path(root, rel)
            if not p.is_dir() and rel not in SKILL_FILES:
                unknown.append(rel)
    return dict(workspace=str(root), files=files, unknown_skill_files=sorted(unknown))


def backup(workspace, destination):
    root = Path(workspace).expanduser().resolve()
    dest = Path(destination).expanduser().resolve()
    for protected in ('skills/todo', 'data/todo'):
        if dest.is_relative_to(root / protected):
            raise TodoError('backup must be outside the old Skill/data directories')
    inventory = inspect_poc(root)
    if dest.exists():
        raise TodoError('backup destination already exists; choose a new directory')
    dest.mkdir(parents=True)
    copied = []
    for rel in SKILL_FILES:
        source = safe_path(root, rel)
        if source.exists():
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied.append(rel)
    source = safe_path(root, DB_FILE)
    if source.exists():
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=5)) as old:
            with closing(sqlite3.connect(dest / 'todos.db')) as new:
                old.backup(new)
                if new.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise TodoError('SQLite backup failed integrity check')
        copied.append('todos.db')
    # Detect writes during the backup. A live WAL backup is consistent but may
    # not represent the same point as filesystem fingerprints: require rebackup
    # after quiescence before quarantine if these differ.
    after = inspect_poc(root)
    manifest = dict(format=1, created_at=iso(datetime.now(timezone.utc)),
                    inventory=after, source_stable=inventory == after,
                    backups=[dict(path=rel, sha256=sha(dest / rel)) for rel in copied])
    manifest_path = dest / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest_path


def quarantine(manifest_path, *, quiesced=False):
    if quiesced is not True:
        raise TodoError('stop old runners and positively identified PoC cron jobs before quarantine')
    mp = Path(manifest_path).resolve()
    manifest = json.loads(mp.read_text(encoding='utf-8'))
    if manifest.get('format') != 1 or not manifest.get('source_stable'):
        raise TodoError('source changed while backing up; quiesce and take another backup')
    inventory = manifest['inventory']
    root = Path(inventory['workspace']).resolve()
    if inventory['unknown_skill_files']:
        raise TodoError('unknown Skill files preserved; inspect and separate them before quarantine')
    for item in manifest['backups']:
        if item['path'] not in (*SKILL_FILES, 'todos.db'):
            raise TodoError('invalid backup manifest path')
        p = safe_path(mp.parent, item['path'])
        if not p.is_file() or sha(p) != item['sha256']:
            raise TodoError('backup missing or changed')
    qroot = mp.parent / 'quarantine'
    planned = []
    # Validate the entire operation before moving any file. A partial interrupted
    # quarantine is resumable: the exact original file must exist at one location.
    recorded = {item['path'] for item in inventory['files']}
    for rel in FILES:
        if safe_path(root, rel).exists() and rel not in recorded:
            raise TodoError('new source file appeared since backup')
    skill = safe_path(root, 'skills/todo')
    if skill.exists():
        for p in skill.rglob('*'):
            safe_path(root, p.relative_to(root).as_posix())
            if p.is_file() and p.relative_to(root).as_posix() not in SKILL_FILES:
                raise TodoError('new unknown Skill file appeared; preserving all sources')
    for item in inventory['files']:
        rel = item['path']
        if rel not in FILES:
            raise TodoError('invalid source manifest path')
        source, target = safe_path(root, rel), safe_path(mp.parent, 'quarantine/' + rel)
        if source.exists() and target.exists():
            raise TodoError('both source and quarantine target exist')
        actual = source if source.exists() else target
        if not actual.is_file() or sha(actual) != item['sha256']:
            raise TodoError('source changed since backup; preserve it and back up again')
        planned.append((source, target))
    journal = mp.parent / 'quarantine-journal.json'
    journal.write_text(json.dumps({'quiesced': True, 'moves': [dict(source=str(a), target=str(b)) for a, b in planned]}, indent=2), encoding='utf-8')
    for source, target in planned:
        if source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
    return dict(quarantined=True, archive=str(qroot),
                note='cron and shared configuration require Agent inspection; never removed by this tool')
