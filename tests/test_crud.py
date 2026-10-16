import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from muse_todo.service import TodoService, TodoError


class CrudTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'todos.db'
        self.now = datetime(2030, 1, 1, 10, tzinfo=timezone.utc)
        self.s = TodoService(self.db, clock=lambda: self.now)
        self.s.execute({'command': 'init', 'timezone': 'UTC'})
        self.n = 0

    def add(self, **kw):
        self.n += 1
        return self.s.execute(dict(command='add', request_id=f'add-{self.n}', title='買書', **kw))

    def update(self, todo, **kw):
        self.n += 1
        return self.s.execute(dict(command='update', request_id=f'edit-{self.n}',
                                   id=todo['id'], expected_version=todo['version'], changes=kw))

    def test_add_read_and_atomic_outbox(self):
        t = self.add(due_at='2030-01-01T14:00:00+00:00')
        self.assertEqual(t['version'], 1)
        self.assertEqual([r['at'] for r in t['reminders']],
                         ['2030-01-01T13:00:00Z', '2030-01-01T14:00:00Z'])
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute('select count(*) from outbox').fetchone()[0], 1)
        s = TodoService(self.db, clock=lambda: self.now)
        self.assertEqual(s.execute({'command': 'get', 'id': t['id']})['title'], '買書')

    def test_add_without_due_or_reminder(self):
        self.assertEqual(self.add()['reminders'], [])

    def test_explicit_reminders_replace_defaults_and_normalize_timezone(self):
        t = self.add(due_at='2030-01-01T22:00:00+08:00',
                     reminder={'mode': 'custom', 'times': ['2030-01-01T20:00:00+08:00']})
        self.assertEqual(t['due_at'], '2030-01-01T14:00:00Z')
        self.assertEqual([r['at'] for r in t['reminders']], ['2030-01-01T12:00:00Z'])

    def test_request_replay_and_conflict(self):
        cmd = dict(command='add', request_id='event-1', title='買書')
        a = self.s.execute(cmd)
        self.assertEqual(self.s.execute(cmd), a)
        with self.assertRaises(TodoError):
            self.s.execute(dict(cmd, title='另一件'))
        self.assertEqual(len(self.s.execute({'command': 'list'})['todos']), 1)

    def test_concurrent_duplicate_request_creates_one_todo(self):
        cmd = dict(command='add', request_id='race', title='一次')
        def run(_):
            return TodoService(self.db, clock=lambda: self.now).execute(cmd)['id']
        with ThreadPoolExecutor(max_workers=4) as pool:
            ids = list(pool.map(run, range(4)))
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(len(self.s.execute({'command': 'list'})['todos']), 1)

    def test_update_name_deadline_and_version_conflict(self):
        t = self.add(due_at='2030-01-01T14:00:00Z')
        u = self.update(t, title='新名稱', due_at='2030-01-01T16:00:00Z')
        self.assertEqual(u['title'], '新名稱')
        self.assertEqual(u['version'], 2)
        self.assertEqual([r['at'] for r in u['reminders']],
                         ['2030-01-01T15:00:00Z', '2030-01-01T16:00:00Z'])
        with self.assertRaises(TodoError):
            self.update(t, title='舊版本')
        self.assertEqual(self.s.execute({'command': 'get', 'id': t['id']})['title'], '新名稱')

    def test_none_mode_sticks_after_deadline_edit(self):
        t = self.add(due_at='2030-01-01T14:00:00Z')
        t = self.update(t, reminder={'mode': 'none'})
        t = self.update(t, due_at='2030-01-01T18:00:00Z')
        self.assertEqual(t['reminders'], [])
        self.assertEqual(t['reminder_mode'], 'none')

    def test_custom_absolute_times_stick_after_due_edit(self):
        t = self.add(reminder={'mode': 'custom', 'times': ['2030-01-01T12:00:00Z']})
        t = self.update(t, due_at='2030-01-01T18:00:00Z')
        self.assertEqual(t['reminders'][0]['at'], '2030-01-01T12:00:00Z')

    def test_clear_due_and_complete_cancel_desired_reminders(self):
        t = self.add(due_at='2030-01-01T14:00:00Z')
        t = self.update(t, due_at=None)
        self.assertEqual(t['reminders'], [])
        t = self.update(t, reminder={'mode': 'custom', 'times': ['2030-01-01T12:00:00Z']})
        t = self.update(t, status='completed')
        self.assertEqual(t['reminders'], [])
        self.assertEqual(self.s.execute({'command': 'list'})['todos'], [])
        self.assertEqual(len(self.s.execute({'command': 'list', 'status': 'completed'})['todos']), 1)

    def test_delete_keeps_tombstone_and_recovery_data(self):
        t = self.add(due_at='2030-01-01T14:00:00Z')
        deleted = self.s.execute(dict(command='delete', request_id='delete-1', id=t['id'], expected_version=1))
        self.assertTrue(deleted['deleted_at'])
        self.assertEqual(deleted['reminders'], [])
        self.assertEqual(self.s.execute({'command': 'list'})['todos'], [])
        self.assertEqual(len(self.s.execute({'command': 'list', 'include_deleted': True})['todos']), 1)
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute('select count(*) from reminders').fetchone()[0], 2)

    def test_invalid_commands_leave_no_rows(self):
        invalid = [dict(title=' '), dict(due_at='2030-01-01T14:00:00'),
                   dict(reminder={'mode': 'custom', 'times': ['2029-01-01T00:00:00Z']}),
                   dict(reminder={'mode': 'nonsense'}), dict(extra='ignored?')]
        for i, kw in enumerate(invalid):
            cmd = dict(command='add', request_id=f'bad-{i}', title='有效')
            cmd.update(kw)
            with self.subTest(kw=kw), self.assertRaises(TodoError):
                self.s.execute(cmd)
        self.assertEqual(self.s.execute({'command': 'list'})['todos'], [])

    def test_past_defaults_skipped_and_overdue_derived(self):
        t = self.add(due_at='2030-01-01T10:30:00Z')
        self.assertEqual(len(t['reminders']), 1)
        t = self.add(due_at='2029-01-01T10:00:00Z')
        self.assertTrue(t['overdue'])
        self.assertEqual(t['reminders'], [])

    def test_transaction_rolls_back_todo_if_outbox_insert_fails(self):
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("CREATE TRIGGER fail_queue BEFORE INSERT ON outbox BEGIN SELECT RAISE(ABORT, 'disk failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.add()
        self.assertEqual(self.s.execute({'command': 'list'})['todos'], [])

    def test_read_missing_database_does_not_create_it(self):
        missing = Path(self.temp.name) / 'missing.db'
        with self.assertRaises(TodoError):
            TodoService(missing).execute({'command': 'list'})
        self.assertFalse(missing.exists())


if __name__ == '__main__':
    unittest.main()
