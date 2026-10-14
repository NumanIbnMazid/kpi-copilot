"""Synthetic checks for targeted period retirement and restricted registries."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pms_periods as P
import kpi_registry as R


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


if __name__ == '__main__':
    unittest.main()
