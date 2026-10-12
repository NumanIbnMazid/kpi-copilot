import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import pms_capacity as C
import sheet_navigation as N
import json
import tempfile
import judge as J
import kpi_engine as E


class CapacityTests(unittest.TestCase):
    def test_weekly_api_cannot_drop_first_week(self):
        requested=[]
        def api(base,path,**kwargs):
            import urllib.parse as U
            q=U.parse_qs(U.urlsplit(path).query);a=q['startDate'][0];b=q['endDate'][0];requested.append((a,b))
            return {'data':[{'entryDate':d.isoformat(),'worklogs':[]} for d in C.days(C.day(a),C.day(b))]}
        with patch.object(C,'_api',api):
            logs=C.read_timesheets('https://example.test',42,'2026-09-07','2026-09-18')
        self.assertEqual(requested,[('2026-09-07','2026-09-12'),('2026-09-13','2026-09-18')])
        self.assertEqual(len(logs['data']),12)

    def test_missing_dates_block_instead_of_inflating_rate(self):
        with patch.object(C,'_api',return_value={'data':[]}):
            with self.assertRaises(ValueError):C.read_timesheets('https://example.test',42,'2026-09-07','2026-09-18')

    def test_shared_resource_counts_only_project_hours(self):
        raw={'members':{'data':[{'user':{'id':1,'name':'Alex'},'isBillable':True},{'user':{'id':2,'name':'Sam'},'isBillable':False},{'user':{'id':3,'name':'Jo'},'isBillable':True}]}}
        logs={'data':[{'entryDate':'2026-09-07','worklogs':[{'user':{'id':1},'timeSpentInMinute':120},{'user':{'id':2},'timeSpentInMinute':480}]}]}
        cap=C.normalize_timelogs(raw,logs,'2026-09-07','2026-09-18','2026-10-07',8,7,[1,3])
        self.assertEqual(cap['resource_days'],.25)
        self.assertEqual([r['included'] for r in cap['resources']],['Yes','No','No'])
        self.assertEqual(cap['missing_entry_resources'],['Jo'])
        self.assertFalse(cap['provisional'])

    def test_current_week_is_provisional(self):
        raw={'members':{'data':[]}}
        self.assertTrue(C.normalize_timelogs(raw,{'data':[]},'2026-10-03','2026-10-07','2026-10-07')['provisional'])

    def test_period_view_id_is_stable_and_link_uses_real_tab_id(self):
        self.assertEqual(N.view_id('Team Review','window'),N.view_id('Team Review','window'))
        self.assertNotEqual(N.view_id('Team Review','window'),N.view_id('Team Review','other'))
        self.assertEqual(N.resolve('kpi-view:Team Review|window',{'Team Review':12}),f'#gid=12&fvid={N.view_id("Team Review","window")}')

    def test_human_context_requires_explicit_rewrite_and_keeps_history(self):
        facts={'reasons':{'Cycle':{'Velocity':'Original user context'},'_authors':{'Cycle|Velocity':'human'}}}
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'answers.json';p.write_text(json.dumps({'reasons':[{'period':'Cycle','kpi':'Velocity','why':'Updated explanation'}]}))
            result=J.apply_answers(p,{'items':[]},None,facts,['Cycle'])
            self.assertEqual(len(result['refused']),1)
            self.assertEqual(facts['reasons']['Cycle']['Velocity'],'Original user context')
            result=J.apply_answers(p,{'items':[]},None,facts,['Cycle'],context_change_reason='The user requested the new measurement explanation.')
            self.assertEqual(result['reasons'],1)
            self.assertEqual(facts['reasons']['_context_history']['Cycle|Velocity'][0]['text'],'Original user context')

    def test_future_agreement_is_not_a_zero_or_a_missing_date(self):
        import reporting
        profile={'periods':{'cadence':{'agreed_delivery_date':'2026-12-01'}}}
        engine=type('Engine',(),{'profile':profile})()
        m=E.Measure('client_expectation','Client Expectation',1,0,'% ',90,'setting','higher-is-better','Not met')
        reporting.apply(engine,m,{'as_of':'2026-10-07'})
        self.assertIsNone(m.value)
        self.assertEqual(m.availability,'Not due yet')
        self.assertEqual(m.gaps,[])
        self.assertIn('2026-12-01',' '.join(m.note_parts))

    def test_refined_types_do_not_rename_a_change_as_an_addition(self):
        import note_sentences
        p={'conventions':{'additional_request_label':'Additional Request'},'policy':{'refine_item_types':True}}
        text=note_sentences.terminology('A change request alters scope; an additional request adds work.',p)
        self.assertIn('change request',text)
        self.assertIn('Additional Request adds work',text)


if __name__=='__main__':unittest.main()
