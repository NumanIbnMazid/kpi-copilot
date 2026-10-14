"""Narrative review must carry the work and outcomes behind a number."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import judge


class NoteContextTests(unittest.TestCase):
    def fixture(self):
        def metric(key, name, counted):
            return {'key': key, 'name': name, 'status': 'Measured', 'value': 5,
                    'counted_keys': counted, 'note': 'Current result.', 'note_parts': ['Current result.']}
        results = {'periods': [{'period': 'Cycle', 'measures': [
            metric('velocity', 'Velocity', ['EX-1']),
            metric('productivity_index', 'Productivity Index', []),
            metric('task_comprehension', 'Task Comprehension', ['EX-1']),
            metric('rejection_rate', 'Defect Rejection Rate', ['BUG-1']),
            metric('defect_rate', 'Defect Rate', ['BUG-2'])]}]}
        reports = [
            {'key': 'BUG-1', 'period': 'Cycle', 'title': 'Sign-in prompt', 'kind': 'Bug',
             'rejected': 'Yes', 'rejection_reason': 'Expected sign-in behavior.'},
            {'key': 'BUG-2', 'period': 'Previous', 'title': 'Visitor search fails', 'kind': 'Bug',
             'rejected': 'No', 'against_task': 'EX-1'}]
        kif = {'project': {'measurement_source': {'defects': reports}},
               'periods': [{'name': 'Cycle', 'capacity': {'basis': 'pms_timelog',
                            'billable_count': 3, 'hours_per_day': 8, 'resource_days': 2}}],
               'tasks': [{'key': 'EX-1', 'period': 'Cycle', 'title': 'Visitor search', 'story_points': 5},
                         {'key': 'EX-2', 'period': 'Cycle', 'title': 'Unfinished export', 'story_points': 8},
                         {'key': 'EX-1', 'period': 'Previous', 'title': 'Earlier duplicate'}],
               'defects': reports}
        return results, kif

    def test_completed_work_matches_output_population_for_each_related_kpi(self):
        results, kif = self.fixture()
        notes = judge._notes_needed(results, {}, True, kif, {})
        for note in notes[:3]:
            self.assertEqual([t['title'] for t in note['context']['completed_work']], ['Visitor search'])
        self.assertEqual(notes[1]['context']['project_effort']['hours_per_day'], 8)
        self.assertEqual(notes[1]['context']['project_effort']['billable_count'], 3)

    def test_report_outcomes_keep_rejection_reason_and_cumulative_defect_scope(self):
        results, kif = self.fixture()
        notes = judge._notes_needed(results, {}, True, kif, {})
        rejection = notes[3]['context']['bug_report_outcomes']
        self.assertEqual([r['key'] for r in rejection], ['BUG-1'])
        self.assertEqual(rejection[0]['rejection_reason'], 'Expected sign-in behavior.')
        density = notes[4]['context']['bug_report_outcomes']
        self.assertEqual([r['key'] for r in density], ['BUG-2'])
        self.assertTrue(density[0]['counted'])

    def test_changed_work_context_requires_renewed_note_review(self):
        results, kif = self.fixture()
        before = judge._notes_needed(results, {}, True, kif, {})[0]
        facts = {'reasons': {'_reviews': {'Cycle|Velocity':
                 {'signature': before['review_signature'], 'text': ''}}}}
        self.assertNotIn('Velocity', [n['kpi'] for n in judge._notes_needed(results, facts, True, kif, {})])
        changed = copy.deepcopy(kif)
        changed['tasks'][0]['title'] = 'Visitor search and filtering'
        self.assertIn('Velocity', [n['kpi'] for n in judge._notes_needed(results, facts, True, changed, {})])


if __name__ == '__main__':
    unittest.main()
