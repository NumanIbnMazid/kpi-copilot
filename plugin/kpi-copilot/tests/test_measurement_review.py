import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from kpi_engine import Engine
import measurement_review as review
import reporting
import json


class ReviewedMethods(unittest.TestCase):
    def setup_case(self,tasks=None,defects=None):
        p={'name':'Window','start':'2026-03-01','end':'2026-03-14','as_of':'2026-03-14'}
        k={'project':{'name':'Example','velocity_unit':'Story Points'},'periods':[p], 'tasks':tasks or [],'defects':defects or []}
        profile={'policy':{'measurement_review':True,'measurement_targets_aligned':False,'measurement_units':{'defect_rate':'story_points','rework_rate':'story_points'} }}
        r=json.loads((Path(__file__).resolve().parents[1]/'schemas/kpi_registry.default.json').read_text())
        return Engine(k,profile,r),p

    def task(self,key,points,returned=False):
        return {'key':key,'period':'Window','type':'Task','closed':'2026-03-02','story_points':points,'reopened':'Yes' if returned else 'No','rework_dates':['2026-03-03','2026-03-04'] if returned else [],'delivery_eligible':'Yes'}

    def test_repeated_returns_count_scope_once(self):
        e,p=self.setup_case([self.task('EX-1',2,True),self.task('EX-2',8)])
        m=e.rework_rate(p);review.apply(e,m,p)
        self.assertEqual((m.numerator,m.denominator,m.value),(2,10,20))
        self.assertIn('2 valid return events',' '.join(m.note_parts))
        e.kif['tasks'][0]['story_points']=8;e.kif['tasks'][1]['story_points']=2
        m=e.rework_rate(p);review.apply(e,m,p);self.assertEqual(m.value,80)

    def test_future_return_not_counted_in_earlier_window(self):
        t=self.task('EX-1',2,True);t['rework_dates']=['2026-03-20']
        e,p=self.setup_case([t]);m=e.rework_rate(p);review.apply(e,m,p)
        self.assertEqual(m.value,0)

    def test_missing_return_date_and_estimate_withheld(self):
        t=self.task('EX-1',2,True);t.pop('rework_dates')
        e,p=self.setup_case([t]);m=e.rework_rate(p);review.apply(e,m,p);self.assertIsNone(m.value)
        t=self.task('EX-1',None);e,p=self.setup_case([t]);m=e.rework_rate(p);review.apply(e,m,p);self.assertIsNone(m.value)

    def test_rejection_uses_decisions_not_bug_estimates(self):
        d=[{'key':'B1','period':'Window','kind':'Bug','rejected':'Yes','story_points':100}, {'key':'B2','period':'Window','kind':'Bug','rejected':'No','story_points':1}]
        e,p=self.setup_case(defects=d);m=e.rejection_rate(p);review.apply(e,m,p);self.assertEqual(m.value,50)
        d.append({'key':'B3','period':'Window','kind':'Bug','rejected':None})
        m=e.rejection_rate(p);review.apply(e,m,p);self.assertIsNone(m.value);self.assertEqual(m.denominator,2)

    def test_no_reports_not_a_zero_percentage(self):
        e,p=self.setup_case();m=e.rejection_rate(p);review.apply(e,m,p)
        self.assertIsNone(m.value);self.assertEqual(m.availability,'No reports to assess')

    def test_origin_group_is_not_an_implementation(self):
        d={'key':'B1','period':'Window','kind':'Bug','reported_on':'2026-03-04','pre_existing':'No','rejected':'No','against_task':'GROUP'}
        e,p=self.setup_case([self.task('EX-1',5),{'key':'GROUP','type':'Excluded','closed':'2026-03-02'}],[d])
        m=e.defect_rate(p);review.apply(e,m,p);self.assertIsNone(m.value)

    def test_member_points_are_independent_of_shared_hours(self):
        t=self.task('EX-1',5);t.update(effort_group='group',hours_dev=None)
        other=self.task('EX-2',8);other.update(effort_group='group',closed=None)
        e,p=self.setup_case([t,other]);m=e.defect_rate(p);review.apply(e,m,p)
        self.assertEqual((m.value,m.denominator),(0,5))
        self.assertEqual(reporting.weight(t,'story_points'),5)
        with self.assertRaises(ValueError):reporting.weight(t,'hours')
        t.update(type='CR',approved_on='2026-03-03',request_kind='Additional request')
        e.policy['measurement_units']['cr_rate']='story_points'
        e.kif['project']['reporting_baseline']=[self.task('EX-BASE',20)]
        m=e.cr_rate(p);review.apply(e,m,p)
        self.assertEqual((m.value,m.numerator,m.denominator),(25,5,20))

    def test_missing_method_inputs_enter_review_queue(self):
        from classify import Classifier
        from judge import build_queue,apply_answers
        from ledger import Ledger
        from tempfile import TemporaryDirectory
        items=[{'id':'impl','key':'EX-1','title':'Contact birthday validation','description':'Validate date of birth.'},
               {'id':'bug','key':'BUG-1','title':'Birthday validation failure','description':'EX-1 accepts an invalid date.','created_at':'2026-03-01'},
               {'id':'extra','key':'EX-2','title':'New requested export','created_at':'2026-03-04','comments':[{'at':'2026-03-06','text':'Please implement this export.'}]}]
        tasks=[self.task('EX-1',5),self.task('EX-2',3)]
        tasks[0]['_item']='impl';tasks[1].update(_item='extra',type='CR')
        defect={'_item':'bug','key':'BUG-1','kind':'Bug','pre_existing':'No','rejected':'No'}
        with TemporaryDirectory() as folder:
            ledger=Ledger(Path(folder)/'ledger.json')
            board={'items':items};c=Classifier(board,{}, {},{},ledger,'2026-03-14')
            c._measurement_links(tasks,[defect],{i['id']:i for i in items});c._attach_context()
            queue=build_queue({'queue':c.queue},None,{},Path(folder),['Window'])
            self.assertEqual(len(queue['items']),2)
            self.assertEqual(queue['items'][0]['item']['implementation_candidates'][0]['key'],'EX-1')
            path=Path(queue['answer_file']);path.parent.mkdir()
            (path.parent/'queue.json').write_text(json.dumps(queue))
            path.write_text(json.dumps({'answers':[
                {'item_id':'bug','field':'against_task','value':'EX-1','why':'Explicit implementation reference.'},
                {'item_id':'extra','field':'approved_on','value':'2026-03-06','why':'Dated client authorization.'}]}))
            result=apply_answers(path,board,ledger,{},['Window'])
            self.assertEqual(result['refused'],[])
            c=Classifier(board,{}, {},{},ledger,'2026-03-14')
            c._measurement_links(tasks,[defect],{i['id']:i for i in items})
            self.assertEqual((defect['against_task'],tasks[1]['approved_on']),('EX-1','2026-03-06'))

    def test_group_approval_counts_shared_budget_once_across_window_rows(self):
        import copy
        members=[]
        for n in (1,2):
            t=self.task(f'EX-{n}',None);t.update(_item=str(n),_row=str(n),effort_group='group',
                type='CR',approved_on='2026-03-03',request_kind='Additional request')
            members.append(t)
        budget={'key':'EX-G','_item':'group','_row':'group','type':'Excluded','effort_only':True,'story_points':8}
        e,p=self.setup_case(copy.deepcopy(members))
        e.policy['measurement_units']['cr_rate']='story_points'
        e.kif['project']['measurement_source']={'tasks':members+[budget]}
        e.kif['project']['reporting_baseline']=[self.task('EX-BASE',40)]
        for t in e.kif['tasks']:t['_row']+='#window:2026-03-01'
        m=e.cr_rate(p);review.apply(e,m,p)
        self.assertEqual((m.value,m.numerator),(20,8))
        e.kif['tasks'].pop()
        m=e.cr_rate(p);review.apply(e,m,p)
        self.assertIsNone(m.value)

    def test_late_defect_uses_original_completed_scope(self):
        t=self.task('EX-1',5);t['closed']='2026-02-20'
        d={'key':'B1','period':'Window','kind':'Bug','reported_on':'2026-03-04','pre_existing':'No','rejected':'No','against_task':'EX-1'}
        e,p=self.setup_case([t],[d]);m=e.defect_rate(p);review.apply(e,m,p)
        self.assertEqual((m.numerator,m.denominator,m.value),(1,5,20))

    def test_escape_uses_previous_pre_release_reports(self):
        d=[{'key':'B1','period':'Release A','kind':'Bug','reported_on':'2026-02-20','pre_existing':'No','rejected':'No','phase':'Pre-release'}, {'key':'B2','period':'Release A','kind':'Bug','reported_on':'2026-03-03','pre_existing':'No','rejected':'No','phase':'Post-release'}]
        e,p=self.setup_case(defects=d);e.kif['periods'].append({'name':'Release A','handover_date':'2026-03-01'})
        m=e.escaped_defect_rate(p);review.apply(e,m,p);self.assertEqual(m.value,50)

    def test_method_is_retained_in_blank_notes(self):
        e,p=self.setup_case();m=e.rejection_rate(p);review.apply(e,m,p);e.finish_note(m,p['name']);review.annotate(e,m,p)
        self.assertIn('Formula:',m.unmeasured_note);self.assertIn('decided',m.measurement_method.lower())
        self.assertEqual(m.review_items,[])

    def test_changed_feature_estimate_is_not_incremental_effort(self):
        t=self.task('EX-1',11);t.update(type='CR',approved_on='2026-03-03',request_kind='Change request')
        e,p=self.setup_case([t]);p['reporting_window']=True
        e.kif['project']['reporting_baseline']=[self.task('EX-BASE',80)]
        m=e.cr_rate(p);review.apply(e,m,p)
        self.assertIsNone(m.value);self.assertIn('incremental estimate',' '.join(m.gaps))

    def test_revised_population_clears_legacy_gaps(self):
        e,p=self.setup_case([self.task('EX-1',5)])
        m=e.defect_rate(p);m.gaps=['An obsolete count-based gap.']
        review.apply(e,m,p)
        self.assertEqual(m.value,0);self.assertNotIn('An obsolete count-based gap.',m.gaps)

    def test_sheet_and_engine_join_method_before_context(self):
        e,p=self.setup_case([self.task('EX-1',5)])
        m=e.rework_rate(p);review.apply(e,m,p)
        e.reasons={'Window':{'Rework Rate':'The review found no implementation returns.'}}
        e.finish_note(m,p['name']);review.annotate(e,m,p)
        self.assertEqual(m.note,m.summary_note+' || '+m.context_note)
        review.annotate(e,m,p)
        self.assertEqual(m.summary_note.count('Pilot method v2.'),1)

    def test_closed_report_without_implementation_is_not_rework_scope(self):
        t=self.task('EX-REPORT',None);t['delivery_eligible']='No'
        e,p=self.setup_case([t,self.task('EX-1',5)])
        m=e.rework_rate(p);review.apply(e,m,p)
        self.assertEqual((m.value,m.denominator),(0,5))

    def test_qa_return_can_qualify_before_final_acceptance(self):
        t=self.task('EX-1',5,True);t['closed']=None
        t.update(rework_closed='2026-03-02',delivery_eligible='No')
        e,p=self.setup_case([t]);m=e.rework_rate(p);review.apply(e,m,p)
        self.assertEqual((m.value,m.denominator),(100,5))

    def test_retest_does_not_move_first_qa_boundary(self):
        from classify import Classifier,Proposal
        profile={'policy':{'measurement_review':True},'workflow':{
            'closed_when':{'values':['Closed']},'reopened_when':{'closed_values':['QA']},
            'delivered_when':{'values':['QA']}}}
        facts={'periods':{'periods':[{'name':'Window','start':'2026-03-01','end':'2026-03-14'}]}}
        item={'id':'example','key':'EX-1','title':'Example implementation','section':'QA','fields':{},
              'created_at':'2026-03-01','events':[
                  {'kind':'section','at':'2026-03-02','to':'QA'},
                  {'kind':'section','at':'2026-03-03','to':'Doing'},
                  {'kind':'section','at':'2026-03-12','to':'QA'}]}
        c=Classifier({'items':[]},profile,{},facts,None,'2026-03-14')
        row=c.task_row(item,Proposal('Task','Agreed work',1),{'period':'Window'})
        self.assertEqual(row['rework_closed'],'2026-03-02')

    def test_alternate_hour_basis_is_not_labelled_story_points(self):
        t=self.task('EX-1',5);t['hours_dev']=40
        e,p=self.setup_case([t]);e.policy['measurement_units']['defect_rate']='hours'
        m=e.defect_rate(p);review.apply(e,m,p)
        self.assertEqual(m.denominator,40)
        self.assertIn('40 completed agreed estimated hours',' '.join(m.note_parts))
        method,formula=review.description(e.profile,'velocity','Hours')
        self.assertNotIn('story points',formula)

if __name__=='__main__':unittest.main()
