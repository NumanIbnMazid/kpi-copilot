"""Synthetic coverage for separate output and productive-day measurements."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import import_story_points
import kpi_engine
import pms_capacity
import sheet_model


class ProductivityTests(unittest.TestCase):
    def data(self):
        kif = {'project': {'name': 'Example', 'velocity_unit': 'Story Points'},
               'generated': {'capabilities': ['status_history', 'comments']},
               'periods': [{'name': 'Cycle', 'start': '2026-10-03', 'end': '2026-10-16',
                            'capacity': {'resource_days': 10, 'hours_per_day': 8, 'basis': 'pms_timelog'}}],
               'tasks': [{'key': 'EX-1', 'period': 'Cycle', 'type': 'Task', 'title': 'Feature',
                          'delivered': '2026-10-05', 'closed': '2026-10-05', 'story_points': 25}],
               'defects': []}
        profile = {'policy': {'productivity_index': {'enabled': True}, 'velocity': {'mode': 'per_resource_day'}}}
        registry = json.loads((ROOT / 'schemas/kpi_registry.default.json').read_text())
        return kif, profile, registry

    def run_metrics(self, kif, profile, registry):
        result = kpi_engine.Engine(kif, profile, registry).run()
        return result, {m.key: m for m in result[0].measures}

    def test_total_and_rate_are_independent_and_pms_note_is_reviewable(self):
        k, p, r = self.data()
        results, m = self.run_metrics(k, p, r)
        self.assertEqual(m['velocity'].value, 25)
        self.assertEqual(m['productivity_index'].value, 2.5)
        self.assertEqual(len(m), 10)
        self.assertIsNone(m['productivity_index'].threshold)
        self.assertIn('2.5 SP/person-day', m['velocity'].summary_note)
        payload = kpi_engine.to_pms_payloads(results, k)[0]
        self.assertTrue(all(x['kpiId'] is not None for x in payload['kpis']))
        self.assertIn('2.5 SP/person-day', next(x['note'] for x in payload['kpis'] if x['name'] == 'Velocity'))
        k['periods'][0]['capacity']['resource_days'] = 5
        _, m = self.run_metrics(k, p, r)
        self.assertEqual((m['velocity'].value, m['productivity_index'].value), (25, 5))

    def test_missing_hours_withholds_pi_without_hiding_output(self):
        k, p, r = self.data()
        k['periods'][0]['capacity']['missing_entry_resources'] = ['Example Resource']
        _, m = self.run_metrics(k, p, r)
        self.assertEqual(m['velocity'].value, 25)
        self.assertIsNone(m['productivity_index'].value)
        self.assertIn('Example Resource', ' '.join(m['productivity_index'].review_items))
        self.assertIn('not measured', m['velocity'].note)

    def test_companion_note_matches_sheet_summary_then_context(self):
        k, p, r = self.data()
        for missing in (False, True):
            if missing:
                k['periods'][0]['delivery_review_pending'] = ['EX-2']
            results = kpi_engine.Engine(k, p, r, reasons={'Cycle': {'Velocity': 'The feature was accepted after testing.'}}).run()
            velocity = results[0].measures[0]
            summary = velocity.unmeasured_summary if missing else velocity.summary_note
            expected = ' || '.join(filter(None, (summary, velocity.context_note)))
            self.assertEqual(velocity.unmeasured_note if missing else velocity.note, expected)

    def test_uncertain_delivery_withholds_both_measures(self):
        k, p, r = self.data()
        k['periods'][0]['delivery_review_pending'] = ['EX-2']
        _, m = self.run_metrics(k, p, r)
        self.assertIsNone(m['velocity'].value)
        self.assertIsNone(m['productivity_index'].value)
        self.assertIn('25 story points', m['velocity'].unmeasured_note)

    def test_real_pi_registry_field_removes_fallback(self):
        k, p, r = self.data()
        r['kpis'].append({'key': 'productivity_index', 'name': 'Productivity Index', 'pms_id': 42,
                          'range': [0, 1000], 'unit': 'SP/person-day', 'threshold': 2})
        results, m = self.run_metrics(k, p, r)
        self.assertNotIn('Temporary PMS companion', m['velocity'].note)
        payload = kpi_engine.to_pms_payloads(results, k)[0]
        self.assertEqual(next(x['value'] for x in payload['kpis'] if x['kpiId'] == 42), 2.5)

    def test_sheet_keeps_distinct_formulas_even_with_measurement_review(self):
        k, p, r = self.data()
        p['policy']['measurement_review'] = True
        results, _ = self.run_metrics(k, p, r)
        tabs = sheet_model.build(k, {'periods': [x.as_dict() for x in results]}, {'profile': p, 'registry': r})
        summary = next(t for t in tabs if t.name == 'KPI Summary')
        for (row, col), cell in list(summary.cells.items()):
            if col == 3 and cell.get('v') == 'Velocity':
                self.assertNotIn('/F', summary.cells[(row, 7)]['f'])
            if col == 3 and cell.get('v') == 'Productivity Index':
                self.assertIn(f'E{row}/F{row}', summary.cells[(row, 7)]['f'])
                self.assertNotIn('*100', summary.cells[(row, 7)]['f'])

    def test_excluded_resource_hours_and_missing_entries_do_not_affect_pi(self):
        raw = {'members': {'data': [{'user': {'id': 1, 'name': 'Example A'}, 'isBillable': True},
                                    {'user': {'id': 2, 'name': 'Example B'}, 'isBillable': True}]}}
        logs = {'data': [{'entryDate': '2026-10-05', 'worklogs': [
            {'user': {'id': 1}, 'timeSpentInMinute': 480}, {'user': {'id': 2}, 'timeSpentInMinute': 960}]}]}
        cap = pms_capacity.normalize_timelogs(raw, logs, '2026-10-05', '2026-10-05', '2026-10-13', eligible_ids=[1])
        self.assertEqual(cap['resource_days'], 1)
        self.assertEqual(cap['billable_count'], 1)
        self.assertEqual(cap['missing_entry_resources'], [])
        self.assertEqual(cap['resources'][1]['net_days'], 0)

    def test_person_day_conversion_is_independent_of_resource_count(self):
        raw = {'members': {'data': [
            {'user': {'id': i, 'name': f'Example {i}'}, 'isBillable': True}
            for i in range(1, 5)]}}
        logs = {'data': [{'entryDate': '2026-10-05', 'worklogs': [
            {'user': {'id': i}, 'timeSpentInMinute': minutes}
            for i, minutes in [(1, 480), (2, 240), (3, 240), (4, 960)]]}]}
        k, p, r = self.data()
        for hours_per_day, days, expected in [(8, 2, 12.5), (4, 4, 6.25)]:
            cap = pms_capacity.normalize_timelogs(raw, logs, '2026-10-05', '2026-10-05',
                                                '2026-10-13', hours_per_day=hours_per_day,
                                                eligible_ids=[1, 2, 3])
            self.assertEqual(cap['billable_count'], 3)
            self.assertEqual(cap['resource_days'], days)
            k['periods'][0]['capacity'] = cap
            _, metrics = self.run_metrics(k, p, r)
            pi = metrics['productivity_index']
            self.assertEqual(pi.value, expected)
            self.assertIn('3 eligible billable Dev/QA resources', pi.note)
            self.assertIn(f'{hours_per_day} hours per person-day', pi.note)

    def test_csv_rejects_duplicate_or_unknown_keys_before_import(self):
        board = {'items': [{'id': '1', 'key': 'EX-1'}]}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'points.csv'
            path.write_text('Ticket,Story Points,Notes\nEX-1,5,Reviewed\n')
            self.assertEqual(import_story_points.prepare(path, board)[0][1], 5)
            for body in ('EX-1,5,\nEX-1,3,\n', 'OTHER-1,2,\n', 'EX-1,nan,\n', 'EX-1,,\n'):
                path.write_text('Ticket,Story Points,Notes\n' + body)
                with self.assertRaises(ValueError):
                    import_story_points.prepare(path, board)

    def test_confirmed_complete_zero_does_not_require_hours_in_every_window(self):
        raw = {'members': {'data': [{'user': {'id': 1, 'name': 'Example A'}, 'isBillable': True},
                                    {'user': {'id': 2, 'name': 'Example B'}, 'isBillable': True}]}}
        logs = {'data': [{'entryDate': '2026-10-05', 'worklogs': [
            {'user': {'id': 1}, 'timeSpentInMinute': 480}]}]}
        confirmation = {'resource_id': 2, 'start': '2026-10-01', 'end': '2026-10-14',
                        'confirmed_on': '2026-10-15', 'by': 'Project lead', 'why': 'All entries are complete.'}
        cap = pms_capacity.normalize_timelogs(raw, logs, '2026-10-03', '2026-10-14', '2026-10-15',
                                            completion_confirmations=[confirmation])
        self.assertEqual(cap['resource_days'], 1)
        self.assertEqual(cap['missing_entry_resources'], [])
        self.assertEqual(cap['resources'][1]['logged_hours'], 0)
        self.assertEqual(cap['resources'][1]['included'], 'Yes')
        self.assertEqual(cap['resources'][1]['completion_confirmation'], confirmation)
        # This acknowledgement cannot waive later periods, another person, or missing authority.
        for bad in (dict(confirmation, end='2026-10-13'), dict(confirmation, resource_id=3),
                    dict(confirmation, why='')):
            cap = pms_capacity.normalize_timelogs(raw, logs, '2026-10-03', '2026-10-14', '2026-10-15',
                                                completion_confirmations=[bad])
            self.assertEqual(cap['missing_entry_resources'], ['Example B'])


if __name__ == '__main__':
    unittest.main()
