"""A reviewed blank with context must not turn into a guessed score."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import kpi_engine
import publication_decisions as P


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.kif = {'project': {'name': 'Example', 'velocity_unit': 'Story Points'},
                    'periods': [{'name': 'Cycle', 'start': '2026-10-01', 'end': '2026-10-14', 'as_of': '2026-10-13'}],
                    'tasks': [{'key': 'EX-1', 'period': 'Cycle', 'type': 'Task', 'title': 'Feature', 'story_points': 5,
                               'delivered': '2026-10-05'}], 'defects': []}
        self.registry = json.loads((ROOT / 'schemas/kpi_registry.default.json').read_text())

    def decision(self):
        result = kpi_engine.Engine(self.kif, {}, self.registry).run()[0]
        measure = next(m for m in result.measures if m.key == 'escaped_defect_rate')
        entry = {'publication': 'notes_only', 'basis': P.basis(measure.as_dict(), self.kif['periods'][0]),
                 'note': 'The work has not reached the client. No escaped defects have been observed before client delivery.',
                 'why': 'The project lead confirmed no client release; publish context without a percentage.',
                 'by': 'Reviewer', 'decided_on': '2026-10-13', 'authority': 'Project lead requested notes-only publication.'}
        return result, entry

    def test_note_only_publishes_explicit_blank_and_keeps_reason(self):
        _, entry = self.decision()
        results = kpi_engine.Engine(self.kif, {}, self.registry, manual={'Cycle': {'Escaped Defect Rate': entry}}).run()
        m = next(m for m in results[0].measures if m.key == 'escaped_defect_rate')
        self.assertIsNone(m.value)
        self.assertFalse(m.publish_blocked)
        self.assertEqual(m.unmeasured_note, entry['note'])
        payload = kpi_engine.to_pms_payloads(results, self.kif)[0]
        row = next(x for x in payload['skipped'] if x['name'] == 'Escaped Defect Rate')
        self.assertFalse(row['preserve_existing'])
        self.assertEqual(row['note'], entry['note'])

    def test_changed_release_evidence_invalidates_decision(self):
        _, entry = self.decision()
        changed = copy.deepcopy(self.kif)
        changed['periods'][0]['handover_date'] = '2026-10-12'
        results = kpi_engine.Engine(changed, {}, self.registry, manual={'Cycle': {'Escaped Defect Rate': entry}}).run()
        m = next(m for m in results[0].measures if m.key == 'escaped_defect_rate')
        self.assertTrue(m.publish_blocked)
        self.assertEqual(m.publication_review['status'], 'stale')

    def test_incomplete_authority_cannot_clear_block(self):
        _, entry = self.decision()
        entry.pop('authority')
        results = kpi_engine.Engine(self.kif, {}, self.registry, manual={'Cycle': {'Escaped Defect Rate': entry}}).run()
        self.assertTrue(next(m for m in results[0].measures if m.key == 'escaped_defect_rate').publish_blocked)

    def test_reviewed_zero_keeps_computation_and_publishes_current_target(self):
        _, entry = self.decision()
        entry.update(publication='reviewed_value', value=0,
                     authority='The project lead requested zero before a client build is shared.')
        engine = kpi_engine.Engine(self.kif, {}, self.registry,
                                  manual={'Cycle': {'Escaped Defect Rate': entry}})
        result = engine.run()[0]
        m = next(m for m in result.measures if m.key == 'escaped_defect_rate')
        self.assertEqual(m.value, 0)
        self.assertIsNone(m.computed_value)
        self.assertFalse(m.publish_blocked)
        self.assertEqual(m.threshold, engine.thresholds[m.key][0])
        self.assertEqual(m.note, entry['note'])
        self.assertEqual(m.publication_review['authority'], entry['authority'])
        self.assertTrue(engine.manual_report)
        payload = kpi_engine.to_pms_payloads([result], self.kif)[0]
        self.assertTrue(any(row['name'] == m.name and row['value'] == 0 for row in payload['kpis']))
        import sheet_model
        tabs = sheet_model.build(self.kif, {'periods': [result.as_dict()]},
                                 {'profile': {}, 'registry': self.registry})
        decisions = next(t for t in tabs if t.name == 'Decisions')
        labels = [c.get('v') for (row, col), c in decisions.cells.items() if col == 2]
        self.assertIn('Escaped Defect Rate: publish reviewed value 0.', labels)
        self.assertNotIn('Escaped Defect Rate: publish explanation without a score.', labels)

    def test_reviewed_score_expires_with_release_evidence(self):
        _, entry = self.decision()
        entry.update(publication='reviewed_value', value=0)
        changed = copy.deepcopy(self.kif)
        changed['periods'][0]['handover_date'] = '2026-10-12'
        result = kpi_engine.Engine(changed, {}, self.registry,
                                  manual={'Cycle': {'Escaped Defect Rate': entry}}).run()[0]
        m = next(m for m in result.measures if m.key == 'escaped_defect_rate')
        self.assertTrue(m.publish_blocked)
        self.assertEqual(m.publication_review['status'], 'stale')

    def test_reviewed_values_reject_nonfinite_and_out_of_range(self):
        result, entry = self.decision()
        for value in (True, float('nan'), float('inf'), -1, 101):
            doc = {'by': 'Reviewer', 'authority': 'Explicit project lead decision.',
                   'reviewed_values': [{'period': 'Cycle', 'kpi': 'Escaped Defect Rate', **entry, 'value': value}]}
            with self.assertRaises(ValueError):
                P.prepare(doc, {'periods': [result.as_dict()]}, self.kif, [], '2026-10-14', self.registry)

    def test_replacing_notes_only_uses_original_computation_basis(self):
        _, entry = self.decision()
        result = kpi_engine.Engine(self.kif, {}, self.registry,
                                  manual={'Cycle': {'Escaped Defect Rate': entry}}).run()[0]
        doc = {'by': 'Reviewer', 'authority': 'Explicit project lead zero convention.',
               'reviewed_values': [{'period': 'Cycle', 'kpi': 'Escaped Defect Rate', **entry, 'value': 0}]}
        entries, _ = P.prepare(doc, {'periods': [result.as_dict()]}, self.kif, [], '2026-10-14', self.registry)
        self.assertEqual(entries[0][1]['publication'], 'reviewed_value')
        self.assertEqual(entries[0][1]['value'], 0)

    def test_explicit_ceiling_preserves_actual_and_caps_only_pms(self):
        self.kif['tasks'][0]['story_points'] = 42
        next(k for k in self.registry['kpis'] if k['key'] == 'velocity')['range'] = [0, 30]
        original = kpi_engine.Engine(self.kif, {}, self.registry).run()[0]
        measure = next(m for m in original.measures if m.key == 'velocity')
        decision = {'period': 'Cycle', 'kpi': 'Velocity', 'value': 42, 'pms_value': 30,
                    'basis': P.basis(measure.as_dict(), self.kif['periods'][0]),
                    'note': '42 SP completed || PMS capped at 30.',
                    'why': 'Retain actual completed output and use the PMS ceiling.'}
        doc = {'by': 'Reviewer', 'authority': 'Use the ceiling and note the actual result.',
               'reviewed_values': [decision]}
        entries, _ = P.prepare(doc, {'periods': [original.as_dict()]}, self.kif, [],
                               '2026-10-14', self.registry)
        manual = {'Cycle': {'Velocity': entries[0][1]}}
        result = kpi_engine.Engine(self.kif, {}, self.registry, manual=manual).run()[0]
        actual = next(m for m in result.measures if m.key == 'velocity')
        self.assertEqual(actual.value, 42)
        self.assertEqual(actual.pms_value, 30)
        self.assertTrue(actual.clamped)
        self.assertFalse(actual.publish_blocked)
        self.assertEqual(actual.note, decision['note'])
        row = next(k for k in kpi_engine.to_pms_payloads([result], self.kif)[0]['kpis']
                   if k['name'] == 'Velocity')
        self.assertEqual(row['value'], 30)
        for invalid_cap in (29, 31, True, float('nan')):
            decision['pms_value'] = invalid_cap
            with self.assertRaises(ValueError):
                P.prepare(doc, {'periods': [original.as_dict()]}, self.kif, [],
                          '2026-10-14', self.registry)
        next(k for k in self.registry['kpis'] if k['key'] == 'velocity')['range'] = [0, 20]
        changed = kpi_engine.Engine(self.kif, {}, self.registry, manual=manual).run()[0]
        self.assertTrue(next(m for m in changed.measures if m.key == 'velocity').publish_blocked)

    def test_recording_rejects_wrong_measurement_coverage(self):
        result, entry = self.decision()
        d = {'period': 'Cycle', 'kpi': 'Escaped Defect Rate', **entry}
        doc = {'by': 'Reviewer', 'authority': entry['authority'], 'notes_only': [d],
               'questions': [{'id': 'measurement:Cycle|Defect Rate', 'decision': 'Publish context.',
                              'covered_by': [['Cycle', 'Escaped Defect Rate']]}]}
        with self.assertRaises(ValueError):
            P.prepare(doc, {'periods': [result.as_dict()]}, self.kif,
                      [{'id': 'measurement:Cycle|Defect Rate'}], '2026-10-13')

    def test_stale_publication_question_requires_matching_review(self):
        result, entry = self.decision()
        qid = 'publication:Cycle|Escaped Defect Rate:' + entry['basis']
        doc = {'by': 'Reviewer', 'authority': entry['authority'],
               'notes_only': [{'period': 'Cycle', 'kpi': 'Escaped Defect Rate', **entry}],
               'questions': [{'id': qid, 'decision': 'Refresh the reviewed note.',
                              'covered_by': [['Cycle', 'Escaped Defect Rate']]}]}
        entries, resolutions = P.prepare(doc, {'periods': [result.as_dict()]}, self.kif,
                                         [{'id': qid}], '2026-10-14')
        self.assertEqual(len(entries), 1)
        self.assertEqual(len(resolutions), 1)
        wrong = 'publication:Cycle|Defect Rate:' + entry['basis']
        doc['questions'][0]['id'] = wrong
        with self.assertRaisesRegex(ValueError, 'stale publication'):
            P.prepare(doc, {'periods': [result.as_dict()]}, self.kif, [{'id': wrong}], '2026-10-14')


if __name__ == '__main__':
    unittest.main()
