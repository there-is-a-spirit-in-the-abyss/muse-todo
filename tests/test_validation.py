import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from muse_todo.service import TodoService, TodoError


class ValidationTests(unittest.TestCase):
    def test_reject_unrelated_database_without_modifying_it(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'old.db'
            with closing(sqlite3.connect(path)) as db:
                db.execute('CREATE TABLE legacy(data TEXT)')
            before = path.read_bytes()
            with self.assertRaises(TodoError):
                TodoService(path).execute({'command': 'init'})
            self.assertEqual(before, path.read_bytes())

    def test_malformed_types_fail_as_domain_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            s = TodoService(Path(temp) / 'test.db')
            s.execute({'command': 'init'})
            commands = [dict(command=[]), dict(command='list', status=[]),
                        dict(command='add', title='x', request_id='bad', reminder={'mode': []})]
            for command in commands:
                with self.subTest(command=command), self.assertRaises(TodoError):
                    s.execute(command)


if __name__ == '__main__':
    unittest.main()
