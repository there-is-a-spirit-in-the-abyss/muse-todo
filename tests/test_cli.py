import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'test.db'

    def run_cli(self, payload):
        return subprocess.run([sys.executable, str(ROOT / 'bin/todo.py'), '--db', str(self.db)],
                              input=payload, capture_output=True, encoding='utf-8', cwd=self.temp.name)

    def test_cli_runs_from_unrelated_directory_and_reads_real_database(self):
        self.assertEqual(self.run_cli('{"command":"init"}').returncode, 0)
        p = self.run_cli(json.dumps(dict(command='add', request_id='cli-1', title='測試中文'), ensure_ascii=False))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(json.loads(p.stdout)['ok'])
        p = self.run_cli('{"command":"list"}')
        self.assertEqual(json.loads(p.stdout)['result']['todos'][0]['title'], '測試中文')

    def test_invalid_json_and_duplicate_keys_fail_without_database_creation(self):
        for data in ['{', '{"command":"init","command":"list"}', '[1]', '{"command":NaN}']:
            p = self.run_cli(data)
            self.assertEqual(p.returncode, 2, p.stdout)
            self.assertFalse(json.loads(p.stdout)['ok'])
            self.assertFalse(self.db.exists())

    def test_input_file(self):
        path = Path(self.temp.name) / 'command.json'
        path.write_text('{"command":"init","timezone":"UTC"}', encoding='utf-8')
        p = subprocess.run([sys.executable, str(ROOT / 'bin/todo.py'), '--db', str(self.db), '--input', str(path)],
                           capture_output=True, encoding='utf-8')
        self.assertEqual(p.returncode, 0, p.stdout)


if __name__ == '__main__':
    unittest.main()
