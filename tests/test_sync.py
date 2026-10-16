import copy
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from muse_todo.service import TodoService, TodoError, iso


class SyncTests(unittest.TestCase):
    """Real SQLite + simulated external scheduler. NOT Muse cron E2E."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = datetime(2030, 1, 1, 10, tzinfo=timezone.utc)
        self.s = TodoService(Path(self.temp.name) / 'todo.db', clock=lambda: self.now)
        self.s.execute({'command': 'init'})
        self.jobs = []
        self.seq = 0
        self.t = self.s.execute(dict(command='add', request_id='add', title='買書',
                                    reminder={'mode': 'custom', 'times': ['2030-01-01T12:00:00Z']}))

    def snapshot(self):
        barrier = self.s.execute({'command': 'sync.status'})['snapshot_barrier']
        return dict(complete=True, observed_at=iso(self.now), barrier=barrier, jobs=copy.deepcopy(self.jobs))

    def next(self):
        return self.s.execute(dict(command='sync.next', snapshot=self.snapshot()))

    def apply(self, op, ack=True):
        # Only the external cron boundary is simulated.
        if op['kind'] == 'add':
            self.seq += 1
            rid = f'cron-{self.seq}'
            self.jobs.append(dict(id=rid, marker=op['marker'], spec=op['spec']))
        elif op['kind'] == 'update':
            rid = op['remote_id']
            job = next(j for j in self.jobs if j['id'] == rid)
            job.update(marker=op['marker'], spec=op['spec'])
        else:
            rid = op['remote_id']
            self.jobs = [j for j in self.jobs if j['id'] != rid]
        if ack:
            self.s.execute(dict(command='sync.ack', operation_id=op['id'], remote_id=rid))
        return rid

    def drain(self):
        for _ in range(30):
            r = self.next()
            if r['operation'] is None:
                self.assertEqual(r['status'], 'idle')
                return r
            self.apply(r['operation'])
        self.fail('sync did not converge')

    def edit(self, **changes):
        t = self.s.execute({'command': 'get', 'id': self.t['id']})
        return self.s.execute(dict(command='update', request_id=f'edit-{t["version"]}',
                                   id=t['id'], expected_version=t['version'], changes=changes))

    def test_add_adopts_id_and_marks_synced_only_after_snapshot(self):
        op = self.next()['operation']
        self.assertEqual(op['kind'], 'add')
        self.apply(op)
        t = self.s.execute({'command': 'get', 'id': self.t['id']})
        self.assertEqual(t['sync']['state'], 'pending')
        self.drain()
        t = self.s.execute({'command': 'get', 'id': self.t['id']})
        self.assertEqual(t['sync']['state'], 'synced')
        self.assertEqual(t['reminders'][0]['remote_id'], 'cron-1')

    def test_update_time_uses_native_update_and_name_updates_payload(self):
        self.drain()
        self.edit(title='新標題', reminder={'mode': 'custom', 'times': ['2030-01-01T13:00:00Z']})
        op = self.next()['operation']
        self.assertEqual(op['kind'], 'update')
        self.assertEqual(op['remote_id'], 'cron-1')
        self.apply(op)
        self.drain()
        self.assertEqual(len(self.jobs), 1)
        self.assertEqual(self.jobs[0]['spec']['at'], '2030-01-01T13:00:00Z')
        self.assertEqual(self.jobs[0]['spec']['title'], '新標題')

    def test_complete_removes_job_and_delivery_gate_denies_old_payload(self):
        self.drain()
        spec = self.jobs[0]['spec']
        self.edit(status='completed')
        self.now += timedelta(hours=2)
        gate = self.s.execute(dict(command='delivery.check', reminder_id=spec['reminder_id'], version=spec['version'], at=spec['at']))
        self.assertFalse(gate['deliver'])
        self.drain()
        self.assertEqual(self.jobs, [])

    def test_delete_cancels_only_owned_jobs(self):
        self.drain()
        self.jobs.append(dict(id='unrelated', marker='other-app', spec={}))
        self.s.execute(dict(command='delete', request_id='delete', id=self.t['id'], expected_version=1))
        self.drain()
        self.assertEqual([j['id'] for j in self.jobs], ['unrelated'])

    def test_definite_failure_retries_with_backoff(self):
        op = self.next()['operation']
        self.s.execute(dict(command='sync.fail', operation_id=op['id'], outcome='not_applied', error='validation rejected'))
        r = self.next()
        self.assertEqual(r['status'], 'retry_wait')
        self.assertIsNone(r['operation'])
        self.now += timedelta(seconds=31)
        self.drain()
        self.assertEqual(len(self.jobs), 1)

    def test_success_then_lost_ack_recovers_without_duplicate_add(self):
        op = self.next()['operation']
        self.apply(op, ack=False)
        self.assertEqual(self.next()['status'], 'blocked')
        self.s.execute(dict(command='sync.recover', operation_id=op['id'], quiesced=True, evidence='tool run ended; complete list reloaded'))
        self.drain()
        self.assertEqual(len(self.jobs), 1)

    def test_unknown_outcome_blocks_until_explicit_quiescence(self):
        op = self.next()['operation']
        self.s.execute(dict(command='sync.fail', operation_id=op['id'], outcome='unknown', error='timeout'))
        self.assertEqual(self.next()['status'], 'blocked')
        with self.assertRaises(TodoError):
            self.s.execute(dict(command='sync.recover', operation_id=op['id'], quiesced=False, evidence='not sure'))

    def test_lease_expiry_does_not_authorize_second_writer(self):
        self.next()
        self.now += timedelta(hours=1)
        self.assertEqual(self.next()['status'], 'blocked')
        self.assertEqual(self.jobs, [])

    def test_stale_ack_does_not_overwrite_new_state(self):
        op = self.next()['operation']
        t = self.edit(status='completed')
        self.apply(op)
        self.assertEqual(self.s.execute({'command': 'get', 'id': t['id']})['status'], 'completed')
        self.drain()
        self.assertEqual(self.jobs, [])

    def test_reconcile_repairs_missing_wrong_and_duplicate_jobs(self):
        self.drain()
        self.jobs[0]['spec']['title'] = '被改壞'
        self.jobs.append(dict(self.jobs[0], id='duplicate'))
        r = self.s.execute(dict(command='reconcile', snapshot=self.snapshot()))
        self.assertTrue(r['drift'])
        self.drain()
        self.assertEqual(len(self.jobs), 1)
        self.assertEqual(self.jobs[0]['spec']['title'], '買書')
        self.jobs.clear()
        self.drain()
        self.assertEqual(len(self.jobs), 1)

    def test_expired_one_shot_is_unknown_not_recreated(self):
        self.drain()
        self.jobs.clear()
        self.now += timedelta(hours=3)
        self.drain()
        t = self.s.execute({'command': 'get', 'id': self.t['id']})
        self.assertEqual(t['reminders'][0]['delivery_state'], 'expired_unknown')
        self.assertEqual(self.jobs, [])

    def test_delivery_receipt_and_duplicate_dispatch(self):
        self.drain()
        spec = self.jobs[0]['spec']
        self.now += timedelta(hours=2)
        cmd = dict(command='delivery.check', reminder_id=spec['reminder_id'], version=spec['version'], at=spec['at'])
        self.assertTrue(self.s.execute(cmd)['deliver'])
        self.assertFalse(self.s.execute(cmd)['deliver'])
        self.s.execute(dict(command='delivery.ack', reminder_id=spec['reminder_id'], token=self.s.execute({'command': 'get', 'id': self.t['id']})['reminders'][0]['delivery_token'], receipt='native-run:123'))
        self.jobs.clear()
        self.drain()
        self.assertEqual(self.s.execute({'command': 'get', 'id': self.t['id']})['reminders'][0]['delivery_state'], 'delivered')

    def test_early_delivery_is_denied(self):
        self.drain()
        spec = self.jobs[0]['spec']
        result = self.s.execute(dict(command='delivery.check', reminder_id=spec['reminder_id'], version=spec['version'], at=spec['at']))
        self.assertFalse(result['deliver'])

    def test_partial_stale_or_duplicate_id_snapshot_is_rejected(self):
        bad = [dict(complete=False, observed_at=iso(self.now), jobs=[]),
               dict(complete=True, observed_at='2020-01-01T00:00:00Z', jobs=[]),
               dict(complete=True, observed_at=iso(self.now), jobs=[dict(id='x'), dict(id='x')])]
        for snap in bad:
            with self.subTest(snap=snap), self.assertRaises(TodoError):
                self.s.execute(dict(command='sync.next', snapshot=snap))

    def test_replayed_ack_is_idempotent_but_conflicting_ack_rejected(self):
        op = self.next()['operation']
        rid = self.apply(op)
        a = self.s.execute(dict(command='sync.ack', operation_id=op['id'], remote_id=rid))
        self.assertTrue(a['acknowledged'])
        with self.assertRaises(TodoError):
            self.s.execute(dict(command='sync.ack', operation_id=op['id'], remote_id='wrong'))

    def test_pre_operation_snapshot_cannot_be_reused_after_ack(self):
        stale = self.snapshot()
        op = self.s.execute(dict(command='sync.next', snapshot=stale))['operation']
        self.apply(op)
        with self.assertRaises(TodoError):
            self.s.execute(dict(command='sync.next', snapshot=stale))
        self.drain()
        self.assertEqual(len(self.jobs), 1)

    def test_maintenance_preserves_due_job_during_native_dispatch_delay(self):
        self.drain()
        self.now += timedelta(hours=2, minutes=1)
        result = self.next()
        self.assertIsNone(result['operation'])
        self.assertEqual(len(self.jobs), 1)
        spec = self.jobs[0]['spec']
        gate = self.s.execute(dict(command='delivery.check', reminder_id=spec['reminder_id'], version=spec['version'], at=spec['at']))
        self.assertTrue(gate['deliver'])

    def test_due_job_removed_after_delivery_window(self):
        self.drain()
        self.now += timedelta(hours=2, minutes=16)
        op = self.next()['operation']
        self.assertEqual(op['kind'], 'remove')

    def test_stale_due_payload_is_reported_not_rescheduled_into_past(self):
        self.drain()
        self.now += timedelta(hours=2, minutes=1)
        self.edit(title='到期後改名')
        result = self.next()
        self.assertIsNone(result['operation'])
        self.assertEqual(result['status'], 'delivery_wait')
        self.assertEqual(self.s.execute({'command': 'get', 'id': self.t['id']})['sync']['state'], 'pending')

    def test_concurrent_synchronizers_reserve_only_one_operation(self):
        snapshot = self.snapshot()
        def reserve(_):
            return self.s.execute(dict(command='sync.next', snapshot=snapshot))
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(reserve, range(8)))
        self.assertEqual(sum(r['operation'] is not None for r in results), 1)
        self.assertEqual(sum(r['status'] == 'blocked' for r in results), 7)

    def test_concurrent_delivery_only_grants_one_sender(self):
        self.drain()
        spec = self.jobs[0]['spec']
        self.now += timedelta(hours=2)
        cmd = dict(command='delivery.check', reminder_id=spec['reminder_id'], version=spec['version'], at=spec['at'])
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.s.execute(cmd), range(8)))
        self.assertEqual(sum(r['deliver'] for r in results), 1)

    def test_late_ack_after_recovery_cannot_close_new_operation(self):
        old = self.next()['operation']
        self.s.execute(dict(command='sync.recover', operation_id=old['id'], quiesced=True, evidence='old native invocation ended'))
        new = self.next()['operation']
        with self.assertRaises(TodoError):
            self.s.execute(dict(command='sync.ack', operation_id=old['id'], remote_id='late-old-job'))
        self.assertEqual(self.next()['operation_id'], new['id'])


if __name__ == '__main__':
    unittest.main()
