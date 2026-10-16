import json
import sqlite3
import os
import subprocess
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from muse_todo.poc import backup, inspect_poc, quarantine
from muse_todo.service import TodoError


class PocTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'workspace'
        self.skill = self.root / 'skills/todo'
        (self.skill / 'bin').mkdir(parents=True)
        (self.skill / 'SKILL.md').write_text('old skill', encoding='utf-8')
        (self.skill / 'bin/todo.py').write_text('# old code', encoding='utf-8')
        self.db = self.root / 'data/todo/todos.db'
        self.db.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.db)) as db:
            db.execute('CREATE TABLE old_todos(title TEXT)')
            db.execute("INSERT INTO old_todos VALUES ('valuable user data')")
            db.commit()
        self.dest = Path(self.temp.name) / 'backup'

    def test_backup_and_quarantine_preserve_data_and_disable_skill(self):
        manifest = backup(self.root, self.dest)
        with closing(sqlite3.connect(self.dest / 'todos.db')) as db:
            self.assertEqual(db.execute('SELECT title FROM old_todos').fetchone()[0], 'valuable user data')
        with self.assertRaises(TodoError):
            quarantine(manifest, quiesced=False)
        result = quarantine(manifest, quiesced=True)
        self.assertTrue(result['quarantined'])
        self.assertFalse((self.skill / 'SKILL.md').exists())
        self.assertFalse(self.db.exists())
        self.assertEqual((self.dest / 'quarantine/skills/todo/bin/todo.py').read_text(), '# old code')
        self.assertTrue(quarantine(manifest, quiesced=True)['quarantined'])

    def test_unknown_skill_files_are_preserved_and_prevent_quarantine(self):
        unknown = self.skill / 'notes.txt'
        unknown.write_text('keep me')
        manifest = backup(self.root, self.dest)
        with self.assertRaises(TodoError):
            quarantine(manifest, quiesced=True)
        self.assertTrue(unknown.exists())
        self.assertTrue((self.skill / 'SKILL.md').exists())

    def test_changed_source_after_backup_is_preserved(self):
        manifest = backup(self.root, self.dest)
        (self.skill / 'bin/todo.py').write_text('# changed')
        with self.assertRaises(TodoError):
            quarantine(manifest, quiesced=True)
        self.assertTrue(self.db.exists())

    def test_tampered_backup_is_rejected(self):
        manifest = backup(self.root, self.dest)
        (self.dest / 'todos.db').write_bytes(b'corrupt')
        with self.assertRaises(TodoError):
            quarantine(manifest, quiesced=True)
        self.assertTrue(self.db.exists())

    def test_live_wal_backup_contains_committed_rows(self):
        with closing(sqlite3.connect(self.db)) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute("INSERT INTO old_todos VALUES ('WAL committed')")
            db.commit()
            backup(self.root, self.dest)
            with closing(sqlite3.connect(self.dest / 'todos.db')) as copied:
                self.assertEqual(copied.execute('SELECT count(*) FROM old_todos').fetchone()[0], 2)

    def test_inspection_does_not_create_missing_paths(self):
        missing = self.root / 'does-not-exist'
        result = inspect_poc(missing)
        self.assertFalse(missing.exists())
        self.assertEqual(result['files'], [])

    @unittest.skipUnless(os.name == 'nt', 'Windows junction regression')
    def test_internal_junction_cannot_redirect_known_poc_files(self):
        source = (self.skill / 'bin').resolve()
        target = (self.skill / 'real-bin').resolve()
        self.assertTrue(source.is_relative_to(self.root.resolve()))
        self.assertTrue(target.is_relative_to(self.root.resolve()))
        source.rename(target)
        create = subprocess.run(['cmd', '/c', 'mklink', '/J', str(source), str(target)], capture_output=True)
        self.assertEqual(create.returncode, 0)
        self.addCleanup(lambda: source.rmdir() if source.exists() else None)
        with self.assertRaises(TodoError):
            inspect_poc(self.root)
        self.assertTrue((target / 'todo.py').exists())


if __name__ == '__main__':
    unittest.main()
