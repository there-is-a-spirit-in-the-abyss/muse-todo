import copy
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from muse_todo.service import TodoError, TodoService, iso


ROOT = Path(__file__).resolve().parents[1]


class LanguageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'todo.db'
        self.now = datetime(2030, 1, 1, 10, tzinfo=timezone.utc)
        self.service = TodoService(self.path, clock=lambda: self.now)

    def run_cli(self, payload='', *args):
        return subprocess.run([sys.executable, str(ROOT / 'bin/todo.py'), '--db', str(self.path), *args],
                              input=payload, capture_output=True, encoding='utf-8', cwd=self.temp.name)

    def snapshot(self, jobs):
        state = self.service.execute({'command': 'sync.status'})
        return dict(complete=True, observed_at=iso(self.now), barrier=state['snapshot_barrier'], jobs=jobs)

    def add(self):
        return self.service.execute(dict(command='add', request_id='add', title='買書 / Buy pão',
                                         reminder=dict(mode='custom', times=['2030-01-01T12:00:00Z'])))

    def test_default_and_old_installations_use_english(self):
        self.assertEqual(self.service.execute({'command': 'init'})['locale'], 'en-US')
        with closing(sqlite3.connect(self.path)) as db:
            with db:
                db.execute("DELETE FROM meta WHERE key='locale'")
        self.assertEqual(self.service.execute({'command': 'settings.get'})['locale'], 'en-US')
        todo = self.add()
        op = self.service.execute(dict(command='sync.next', snapshot=self.snapshot([])))['operation']
        self.assertEqual(op['spec']['text'], 'Reminder: 買書 / Buy pão')
        self.assertEqual(todo['title'], '買書 / Buy pão')

    def test_language_persists_and_does_not_change_todos_or_replays(self):
        self.service.execute(dict(command='init', locale='es'))
        original = self.add()
        state = self.service.execute({'command': 'sync.status'})
        self.assertEqual(self.service.execute(dict(command='settings.set', locale='pt')), {'locale': 'pt'})
        reopened = TodoService(self.path, clock=lambda: self.now)
        self.assertEqual(reopened.execute({'command': 'settings.get'}), {'locale': 'pt'})
        self.assertEqual(reopened.execute(dict(command='get', id=original['id'])), original)
        self.assertEqual(self.add(), original)
        later = self.service.execute({'command': 'sync.status'})
        self.assertEqual(later['outbox'], state['outbox'])
        self.assertEqual(later['snapshot_barrier'], state['snapshot_barrier'])

    def test_invalid_locale_is_atomic_and_init_is_idempotent(self):
        self.service.execute(dict(command='init', locale='es'))
        for locale in ['fr', 'pt-BR', '', None, [], {}, 1]:
            with self.subTest(locale=locale), self.assertRaises(TodoError):
                self.service.execute(dict(command='settings.set', locale=locale))
        self.assertEqual(self.service.execute({'command': 'init'})['locale'], 'es')
        with self.assertRaises(TodoError):
            self.service.execute(dict(command='init', locale='pt'))
        self.assertEqual(self.service.execute({'command': 'settings.get'}), {'locale': 'es'})

    def test_invalid_init_locale_never_creates_database(self):
        with self.assertRaises(TodoError):
            self.service.execute(dict(command='init', locale=[]))
        self.assertFalse(self.path.exists())

    def test_service_errors_follow_saved_language_and_preserve_field_names(self):
        for locale, missing, required in [
            ('en-US', 'todo not found', 'title must be nonempty text, at most 255 characters'),
            ('es', 'Tarea no encontrada', 'title debe ser texto no vacío de hasta 255 caracteres'),
            ('pt', 'Tarefa não encontrada', 'title deve ser texto não vazio com até 255 caracteres'),
        ]:
            with self.subTest(locale=locale):
                if not self.path.exists():
                    self.service.execute({'command': 'init'})
                self.service.execute(dict(command='settings.set', locale=locale))
                with self.assertRaises(TodoError) as caught:
                    self.service.execute(dict(command='get', id='missing'))
                self.assertEqual(str(caught.exception), missing)
                with self.assertRaises(TodoError) as caught:
                    self.service.execute(dict(command='add', request_id='bad', title=''))
                self.assertEqual(str(caught.exception), required)

    def test_cli_input_errors_and_help_use_persisted_locale(self):
        self.service.execute(dict(command='init', locale='es'))
        bad = self.run_cli('{')
        self.assertEqual(bad.returncode, 2)
        self.assertEqual(json.loads(bad.stdout), dict(ok=False, error='JSONDecodeError', message='JSON no válido'))
        duplicate = self.run_cli('{"command":"list","command":"get"}')
        self.assertEqual(json.loads(duplicate.stdout)['message'], 'Clave JSON duplicada: command')
        help_run = self.run_cli('', '--help')
        self.assertEqual(help_run.returncode, 0)
        self.assertIn('Ejecutor de comandos JSON', help_run.stdout)
        self.assertIn('Mostrar esta ayuda', help_run.stdout)
        absent = self.run_cli('', '--input', str(Path(self.temp.name) / 'absent.json'))
        self.assertEqual(json.loads(absent.stdout)['message'], 'No se pudo leer o escribir el archivo')

    def test_cli_portuguese_validation_and_argument_errors(self):
        self.service.execute(dict(command='init', locale='pt'))
        result = self.run_cli('{"command":"list","status":"wrong"}')
        self.assertEqual(json.loads(result.stdout)['message'], 'Filtro de estado inválido')
        invalid = self.run_cli('', '--unknown')
        self.assertEqual(invalid.returncode, 2)
        self.assertIn('Argumentos não reconhecidos: --unknown', invalid.stderr)

    def test_cli_missing_argument_value_still_uses_saved_language(self):
        self.service.execute(dict(command='init', locale='pt'))
        invalid = self.run_cli('', '--db')
        self.assertEqual(invalid.returncode, 2)
        self.assertIn('O argumento --db exige um valor', invalid.stderr)
        self.assertEqual(self.service.execute({'command': 'settings.get'}), {'locale': 'pt'})

    def test_switch_preserves_inflight_and_reconciles_localized_text(self):
        self.service.execute(dict(command='init', locale='es'))
        todo = self.add()
        old = self.service.execute(dict(command='sync.next', snapshot=self.snapshot([])))['operation']
        self.assertEqual(old['spec']['text'], 'Recordatorio: 買書 / Buy pão')
        self.service.execute(dict(command='settings.set', locale='pt'))
        blocked = self.service.execute(dict(command='sync.next', snapshot=self.snapshot([])))
        self.assertEqual(blocked['status'], 'blocked')
        self.assertEqual(blocked['operation_id'], old['id'])
        self.assertIn('operação externa', blocked['reason'])
        self.service.execute(dict(command='sync.ack', operation_id=old['id'], remote_id='cron-1'))
        jobs = [dict(id='cron-1', marker=old['marker'], spec=copy.deepcopy(old['spec']))]
        new = self.service.execute(dict(command='sync.next', snapshot=self.snapshot(jobs)))['operation']
        self.assertEqual(new['kind'], 'update')
        self.assertEqual(new['marker'], old['marker'])
        self.assertEqual(new['version'], todo['version'])
        self.assertEqual(new['spec']['text'], 'Lembrete: 買書 / Buy pão')

    def test_delivery_uses_current_language_without_resetting_claim(self):
        self.service.execute(dict(command='init', locale='es'))
        todo = self.add()
        reminder = todo['reminders'][0]
        self.service.execute(dict(command='settings.set', locale='pt'))
        self.now += timedelta(hours=2)
        command = dict(command='delivery.check', reminder_id=reminder['id'], version=todo['version'], at=reminder['at'])
        result = self.service.execute(command)
        self.assertEqual(result['text'], 'Lembrete: 買書 / Buy pão')
        self.service.execute(dict(command='settings.set', locale='en-US'))
        self.assertFalse(self.service.execute(command)['deliver'])

    def test_poc_cli_explicit_locale_localizes_without_creating_data(self):
        result = subprocess.run([sys.executable, str(ROOT / 'bin/poc.py'), '--locale', 'pt', 'quarantine',
                                 '--manifest', str(Path(self.temp.name) / 'missing.json')],
                                capture_output=True, encoding='utf-8')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['error'],
                         'Pare os processos antigos e os trabalhos cron PoC identificados antes do isolamento')
        self.assertFalse(self.path.exists())

    def test_poc_service_error_and_subcommand_help_use_selected_language(self):
        from muse_todo.poc import backup
        with self.assertRaises(TodoError):
            backup(self.temp.name, Path(self.temp.name) / 'data/todo/backup')
        result = subprocess.run([sys.executable, str(ROOT / 'bin/poc.py'), '--locale', 'es', 'quarantine', '--help'],
                                capture_output=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0)
        self.assertIn('Confirmar que los procesos antiguos', result.stdout)
        self.assertIn('Mostrar esta ayuda', result.stdout)

    def test_cli_does_not_leak_english_from_invalid_subcommand_choice(self):
        result = subprocess.run([sys.executable, str(ROOT / 'bin/poc.py'), '--locale', 'pt', 'bad'],
                                capture_output=True, encoding='utf-8')
        self.assertEqual(result.returncode, 2)
        self.assertIn('escolha entre', result.stderr)
        self.assertNotIn('choose from', result.stderr)

    def test_spanish_sync_validation_and_denial_reasons_are_localized(self):
        self.service.execute(dict(command='init', locale='es'))
        todo = self.add()
        with self.assertRaises(TodoError) as caught:
            self.service.execute(dict(command='sync.next', snapshot=dict(complete=False)))
        self.assertIn('instantánea completa', str(caught.exception))
        reminder = todo['reminders'][0]
        result = self.service.execute(dict(command='delivery.check', reminder_id=reminder['id'],
                                           version=99, at=reminder['at']))
        self.assertEqual(result, dict(deliver=False, reason='Recordatorio obsoleto o inactivo'))
        self.assertEqual(self.service.execute(dict(command='get', id=todo['id']))['status'], 'pending')

    def test_human_validation_labels_are_translated_without_changing_json_fields(self):
        self.service.execute(dict(command='init', locale='es'))
        with self.assertRaises(TodoError) as caught:
            self.service.execute(dict(command='sync.next', snapshot=self.snapshot([dict(marker='x')])))
        self.assertIn('identificador del trabajo remoto', str(caught.exception))
        todo = self.add()
        with self.assertRaises(TodoError) as caught:
            self.service.execute(dict(command='delivery.ack', reminder_id=todo['reminders'][0]['id'], receipt='test'))
        self.assertIn('token de entrega', str(caught.exception))
        self.assertNotIn('delivery token', str(caught.exception))

    def test_malformed_json_constants_keep_error_class_and_localize_details(self):
        self.service.execute(dict(command='init', locale='pt'))
        result = self.run_cli('{"command":NaN}')
        self.assertEqual(json.loads(result.stdout), dict(ok=False, error='TodoError', message='Constante JSON inválida: NaN'))
        result = self.run_cli('{"command":"list","injected":1}')
        self.assertEqual(json.loads(result.stdout)['message'], "Campos desconhecidos: ['injected']")


if __name__ == '__main__':
    unittest.main()
