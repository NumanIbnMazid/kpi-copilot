"""Synthetic checks for targeted period retirement and restricted registries."""
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pms_periods as P
import pms_push
import kpi_registry as R


class FakePMS:
    """One project's periods: an old milestone period and the window that replaced it."""

    def __init__(self, fail_put=False):
        self.periods = {1: {'id': 1, 'projectId': 12, 'name': 'Initial Scope', 'updatedAt': 'a',
                            'periodKpis': [{'kpiId': 9, 'value': 16.5}]},
                        2: {'id': 2, 'projectId': 12, 'name': 'Window 1', 'updatedAt': 'b', 'periodKpis': []}}
        self.fail_put = fail_put
        self.calls = []

    def __call__(self, base, path, method='GET', body=None, token=None, extra=None):
        self.calls.append(method)
        if path == '/api/projects/12/periods' and method == 'GET':
            return {'data': [{'id': p['id'], 'projectId': 12, 'name': p['name']} for p in self.periods.values()]}
        pid = int(re.fullmatch(r'/api/projects/12/periods/(\d+)', path).group(1))
        if method == 'GET':
            return {'data': json.loads(json.dumps(self.periods[pid]))}
        if method == 'PUT':
            if self.fail_put:
                raise OSError('PMS is down')
            self.periods[pid]['updatedAt'] += '+'
            return {}
        if method == 'DELETE':
            if extra.get('Last-Modified') != self.periods[pid]['updatedAt']:
                raise ValueError('stale')
            del self.periods[pid]
            return {}
        raise AssertionError(method)


class PeriodTests(unittest.TestCase):
    def test_retirement_requires_exact_names_and_live_replacements(self):
        rows = [{'id': 1, 'projectId': 12, 'name': 'Legacy'},
                {'id': 2, 'projectId': 12, 'name': 'Fortnight'}]
        self.assertEqual(P.select(rows, ['Legacy'], ['Fortnight'])[0]['id'], 1)
        for names, keep in [(['Legacy'], []), (['Legacy'], ['Missing']),
                            (['Fortnight'], ['Fortnight']), (['Legacy', 'Legacy'], ['Fortnight'])]:
            with self.assertRaises(ValueError):
                P.select(rows, names, keep)
        with self.assertRaises(ValueError):
            P.period_list(rows, 13)
        with self.assertRaises(ValueError):
            P.select(rows + [rows[0]], ['Legacy'], ['Fortnight'])

    def test_changed_backup_prevents_any_deletion(self):
        with tempfile.TemporaryDirectory() as d:
            plan = Path(d) / 'plan.json'
            detail = {'id': 1, 'name': 'Legacy', 'updatedAt': 'old', 'periodKpis': []}
            plan.write_text(json.dumps({'pms': 'https://pms.example', 'project_id': 12,
                                        'keep': ['Fortnight'], 'retire': [detail]}))
            rows = [{'id': 1, 'name': 'Legacy', 'projectId': 12},
                    {'id': 2, 'name': 'Fortnight', 'projectId': 12}]
            with patch.object(P, 'load_profile', return_value={}), patch.object(P, 'resolve_profile',
                 return_value=({'organization': {'pms_base_url': 'https://pms.example'}}, {'pms_project_id': 12})), \
                 patch.object(P, '_api', side_effect=[{'data': rows}, {'data': {**detail, 'updatedAt': 'new'}}]) as api, \
                 patch.object(sys, 'argv', ['pms_periods', '--profile', 'example.yaml', '--project', 'example',
                                           '--plan', str(plan), '--apply']):
                with self.assertRaisesRegex(ValueError, 'changed after'):
                    P.main()
                self.assertFalse(any(c.kwargs.get('method') == 'DELETE' for c in api.call_args_list))

    def test_project_definition_refresh_preserves_other_project_targets(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            profile, out = root / 'profile.json', root / 'registry.json'
            profile.write_text(json.dumps({'organization': {'pms_base_url': 'https://pms.example'}}))
            out.write_text(json.dumps({'projects': {'7': {'velocity': {'threshold': 17}}}}))
            rows = [{'kpi': {'id': 10, 'name': 'Productivity Index', 'threshold': 3,
                            'minValue': 0, 'maxValue': 30, 'isMinimumThreshold': True}}]
            with patch.object(R, 'fetch_project', return_value=rows), patch.object(R, 'fetch') as master:
                self.assertEqual(R.main(['--refresh', '--profile', str(profile), '--out', str(out),
                                         '--project', '12', '--project-definitions']), 0)
            master.assert_not_called()
            result = json.loads(out.read_text())
            self.assertEqual(result['projects']['7']['velocity']['threshold'], 17)
            self.assertEqual(next(x for x in result['kpis'] if x['key'] == 'productivity_index')['pms_id'], 10)



class ReplacedPeriodPushTests(unittest.TestCase):
    """A switch to reporting windows: the old period is named in the preview and removed only
    when that is authorized, after the window is written and verified."""

    def push(self, pms, *flags):
        d = Path(self.tmp.name)
        payloads = d / 'payloads.json'
        payloads.write_text(json.dumps([{'projectId': 12, 'periodId': 2, 'name': 'Window 1', 'description': 'One',
                                         'kpis': [{'name': 'Velocity', 'kpiId': 9, 'value': 5, 'note': 'Five points.'}]}]))
        current = {'_limits': {'Velocity': (0, 100)}, '2': {'Velocity': {'value': 5, 'note': 'Five points.'}}}
        profile = ({'organization': {'pms_base_url': 'https://pms.example'}, 'output': {'mode': 'assisted-push'}},
                   {'pms_project_id': 12})
        out = io.StringIO()
        with patch.dict(os.environ, {'PMS_TOKEN': 'test-only'}), patch.object(pms_push, 'load_profile'), \
                patch.object(pms_push, 'resolve_profile', return_value=profile), \
                patch.object(pms_push, 'read_current', return_value=current), patch.object(pms_push, '_api', pms), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = pms_push.main(['--profile', 'p.yaml', '--payloads', str(payloads), '--log', str(d / 'push_log.json'),
                                  '--replaced', 'Initial Scope', '--replaced', 'Full Project', *flags])
        return code, out.getvalue()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_the_preview_names_the_replaced_period_and_changes_nothing(self):
        pms = FakePMS()
        code, out = self.push(pms)
        self.assertEqual(code, 0)
        self.assertIn('Initial Scope  (period 1)', out)
        self.assertIn('Authorize --retire-replaced', out)
        self.assertNotIn('Full Project', out)  # never in PMS, so nothing to say
        self.assertEqual(set(pms.calls), {'GET'})

    def test_a_push_without_authorization_leaves_the_replaced_period(self):
        pms = FakePMS()
        code, out = self.push(pms, '--apply')
        self.assertEqual(code, 0)
        self.assertIn(1, pms.periods)
        self.assertNotIn('DELETE', pms.calls)
        self.assertIn('Not removed', out)

    def test_authorized_removal_follows_the_verified_window_and_keeps_a_backup(self):
        pms = FakePMS()
        code, out = self.push(pms, '--apply', '--retire-replaced')
        self.assertEqual(code, 0, out)
        self.assertEqual(sorted(pms.periods), [2])
        self.assertLess(pms.calls.index('PUT'), pms.calls.index('DELETE'))
        backup = Path(self.tmp.name) / 'retired_periods.json'
        saved = json.loads(backup.read_text())
        self.assertEqual(saved['retire'][0]['periodKpis'][0]['value'], 16.5)
        self.assertEqual(saved['keep'], ['Window 1'])
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        log = json.loads((Path(self.tmp.name) / 'push_log.json').read_text())['results']
        self.assertEqual([(r['period'], r['result']) for r in log],
                         [('Window 1', 'verified'), ('Initial Scope', 'removed and verified')])
        self.assertEqual(log[1]['action'], 'Removed from PMS')

    def test_a_failed_window_write_removes_nothing(self):
        pms = FakePMS(fail_put=True)
        code, _ = self.push(pms, '--apply', '--retire-replaced')
        self.assertNotEqual(code, 0)
        self.assertIn(1, pms.periods)
        self.assertNotIn('DELETE', pms.calls)

    def test_a_window_is_never_removed_even_if_named_as_replaced(self):
        pms = FakePMS()
        pms.periods[1]['name'] = 'Window 1 old'
        code, out = self.push(pms, '--apply', '--retire-replaced', '--replaced', 'Window 1')
        self.assertEqual(code, 0, out)
        self.assertEqual(sorted(pms.periods), [1, 2])
        self.assertIn('No replaced period is left in PMS', out)


if __name__ == '__main__':
    unittest.main()
