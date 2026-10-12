"""Synthetic regressions for rates, capacity and review boundaries."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import kpi_engine, reporting, pms_capacity, team_review, notifications


class ReportingTests(unittest.TestCase):
    def kif(self):
        return {'project':{'name':'Example','velocity_unit':'Story Points'},
                'generated':{'capabilities':['status_history','comments']},
                'periods':[{'name':'Cycle','start':'2026-10-03','end':'2026-10-16'}],
                'tasks':[{'key':'EX-1','_item':'1','_row':'1','period':'Cycle','type':'Task',
                          'delivered':'2026-10-05','closed':'2026-10-05','story_points':26,'title':'Example feature',
                          'hours_dev':40,'hours_qa':8,'reopened':'No','rework_closed':'2026-10-05'}],
                'defects':[]}

    def engine(self,kif,profile):
        registry=json.loads((ROOT/'schemas'/'kpi_registry.default.json').read_text())
        return kpi_engine.Engine(kif,profile,registry)

    def test_rate_scales_with_working_days_and_preserves_total(self):
        k=self.kif();p=k['periods'][0];p['capacity']={'resource_days':26,'billable_count':3}
        profile={'policy':{'velocity':{'mode':'per_resource_day'}}}
        e=self.engine(k,profile);m=e.velocity(p);reporting.apply(e,m,p)
        self.assertEqual((m.value,m.numerator,m.denominator),(1,26,26))
        self.assertIsNone(m.threshold);self.assertTrue(m.publish_blocked)
        k['tasks'][0]['story_points']=52;p['capacity']['resource_days']=52
        e=self.engine(k,profile);m=e.velocity(p);reporting.apply(e,m,p)
        self.assertEqual(m.value,1)

    def test_missing_capacity_never_becomes_a_green_zero(self):
        k=self.kif();e=self.engine(k,{'policy':{'velocity':{'mode':'per_resource_day'}}})
        m=e.velocity(k['periods'][0]);reporting.apply(e,m,k['periods'][0])
        self.assertIsNone(m.value);self.assertTrue(m.gaps)

    def test_pilot_velocity_baseline_requires_three_valid_completed_windows(self):
        k=self.kif();k['periods']=[];k['tasks']=[]
        for i,rate in enumerate([1,3,2,50]):
            name=f'Window {i}'
            k['periods'].append({'name':name,'start':f'2026-10-{3+i*3:02d}','end':f'2026-10-{5+i*3:02d}',
                                'as_of':f'2026-10-{5+i*3:02d}','reporting_window':True,'capacity':{'resource_days':10}})
            k['tasks'].append({'key':f'EX-{i}','period':name,'type':'Task','delivered':f'2026-10-{4+i*3:02d}','story_points':rate*10})
        cfg={'policy':{'velocity':{'mode':'per_resource_day'},'pilot_targets':{'velocity':{'strategy':'previous_velocity_median','minimum_periods':3,'why':'Comparison baseline'}}}}
        e=self.engine(k,cfg);value,why=reporting.pilot_target(e,'velocity',{'start':'2026-10-09'})
        self.assertIsNone(value);self.assertIn('2 available',why)
        value,_=reporting.pilot_target(e,'velocity',{'start':'2026-10-12'})
        self.assertEqual(value,2)
        k['periods'][2]['as_of']='2026-10-10'
        self.assertIsNone(reporting.pilot_target(e,'velocity',{'start':'2026-10-12'})[0])

    def test_small_scope_density_is_scaled_and_local_goal_cannot_publish(self):
        k=self.kif();k['tasks'][0]['story_points']=20
        k['defects']=[{'key':f'EX-B{i}','period':'Cycle','kind':'Bug','rejected':'No','pre_existing':'No','phase':'QA'} for i in range(2)]
        cfg={'policy':{'measurement_units':{'defect_rate':'story_points'},'pilot_targets':{'defect_rate':{'value':0,'why':'Provisional quality goal'}}}}
        e=self.engine(k,cfg);m=e.defect_rate(k['periods'][0]);reporting.apply(e,m,k['periods'][0])
        self.assertEqual((m.value,m.numerator,m.denominator),(10,2,20));self.assertEqual(m.threshold,0)
        self.assertTrue(m.publish_blocked);self.assertEqual(m.status,'Not met')
        self.assertIn('does not need 100 story points',' '.join(m.note_parts))

    def test_window_labels_and_review_timestamps_are_not_coerced_to_dates(self):
        import sheet_model
        t=sheet_model.Tab('Example');label='2026-10-03 to 10-16';stamp='2026-10-07T04:00:00Z'
        t.put(1,1,label);t.put(1,2,stamp)
        self.assertEqual(t.cells[(1,1)]['v'],label);self.assertEqual(t.cells[(1,2)]['v'],stamp)

    def test_note_verification_ignores_section_stops_but_preserves_figures(self):
        import sheet_verify
        self.assertEqual(sheet_verify._note_clean('Rate 0.25. || Reviewed.'),sheet_verify._note_clean('Rate 0.25 || Reviewed'))
        self.assertNotEqual(sheet_verify._note_clean('Rate 0.25.'),sheet_verify._note_clean('Rate 0.2.'))

    def test_unmeasured_window_formulas_preserve_review_and_future_gates(self):
        import sheet_model
        k=self.kif();cfg={'periods':{'cadence':{'anchor':'2026-10-03','end':'2026-10-30'}},'policy':{'no_defects_as_zero':True}}
        out=reporting.intervalize(k,cfg,'2026-10-07');e=self.engine(out,cfg)
        results={'periods':[p.as_dict() for p in e.run()]}
        tabs=sheet_model.build(out,results,{'profile':cfg,'registry':e.registry})
        summary=next(t for t in tabs if t.name=='KPI Summary')
        for r in range(4,22):
            if summary.cells[(r,1)]['v']==out['periods'][-1]['name']:
                self.assertIn(f'O{r}=""',summary.cells[(r,7)]['f'])

    def test_unjudged_closure_withholds_output_and_invalid_closure_is_excluded(self):
        k=self.kif();profile={'periods':{'cadence':{'anchor':'2026-10-03'}},'policy':{'velocity':{'mode':'per_resource_day','completion':'closed'}}}
        k['tasks'][0]['delivery_eligible']=None
        out=reporting.intervalize(k,profile,'2026-10-07');p=out['periods'][0];p['capacity']={'resource_days':14}
        e=self.engine(out,profile);m=e.velocity(p);reporting.apply(e,m,p)
        self.assertIsNone(m.value);self.assertIn('EX-1',p['delivery_review_pending'])
        k['tasks'][0]['delivery_eligible']='No'
        out=reporting.intervalize(k,profile,'2026-10-07')
        self.assertEqual(out['tasks'][0]['type'],'Excluded');self.assertIsNone(out['tasks'][0]['delivered'])

    def test_future_window_commitments_remain_visible_without_milestone_date_leak(self):
        k=self.kif();k['project']['client_date']='2026-09-24';k['tasks'][0].update(closed=None,delivered=None,client_date='2026-10-16')
        out=reporting.intervalize(k,{'periods':{'cadence':{'anchor':'2026-10-03'}}},'2026-10-07')
        self.assertEqual(len(out['tasks']),1);self.assertIsNone(out['project']['client_date'])

    def test_commitments_use_due_window_without_recrediting_earlier_output(self):
        k=self.kif();k['tasks'][0].update(commit_date='2026-10-30',met_commitment='Yes')
        cfg={'periods':{'cadence':{'anchor':'2026-10-03'}}}
        out=reporting.intervalize(k,cfg,'2026-10-30')
        first,later=out['tasks']
        self.assertIsNone(first['commit_date']);self.assertIsNone(first['met_commitment'])
        self.assertIsNone(later['delivered'])
        self.assertEqual(later['commitment_delivered'],'2026-10-05')
        self.assertEqual(later['met_commitment'],'Yes')

    def test_comprehension_is_assessed_with_completed_work_once(self):
        k=self.kif();k['tasks'][0].update(understood='No',commit_date='2026-10-30')
        out=reporting.intervalize(k,{'periods':{'cadence':{'anchor':'2026-10-03'}}},'2026-10-30')
        e=self.engine(out,{})
        self.assertEqual(e.task_comprehension(out['periods'][0]).denominator,1)
        self.assertEqual(e.task_comprehension(out['periods'][1]).denominator,0)

    def test_sparse_timesheets_never_replace_capacity(self):
        raw=self.raw();c=pms_capacity.normalize(raw,'2026-10-05','2026-10-16',[0,1,2,3,4])
        ts={'data':[{'worklogs':[{'user':{'id':1},'timeSpentInMinute':60},{'user':{'id':4},'timeSpentInMinute':600}]}]}
        s=pms_capacity.timesheet_summary(ts,raw['members']['data'],'2026-09-27','2026-10-03','2026-10-07')
        self.assertEqual(s['billable_logged_hours'],1);self.assertEqual(s['billable_members_with_entries'],1)
        self.assertTrue(s['entry_delay_possible']);self.assertEqual(c['resource_days'],26)

    def test_alternate_metric_keeps_missing_exposure_gate(self):
        k=self.kif();k['defects']=[{'key':'EX-B','period':'Cycle','kind':'Bug','rejected':'No','phase':'Post-release','story_points':5}]
        profile={'policy':{'measurement_units':{'escaped_defect_rate':'story_points'}}}
        e=self.engine(k,profile);m=e.escaped_defect_rate(k['periods'][0]);reporting.apply(e,m,k['periods'][0])
        self.assertIsNone(m.value)

    def test_interval_additions_require_approval_timing(self):
        k=self.kif();k['tasks'][0]['type']='CR';k['tasks'][0]['created']='2026-10-05'
        profile={'periods':{'cadence':{'anchor':'2026-10-03'}}};out=reporting.intervalize(k,profile,'2026-10-07')
        e=self.engine(out,profile);p=out['periods'][0];m=e.cr_rate(p);reporting.apply(e,m,p)
        self.assertIsNone(m.value);self.assertTrue(any('approval date' in g.lower() for g in m.gaps))

    def raw(self):
        members=[{'user':{'id':i,'name':f'Person {i}'},'isBillable':i<4,'joinedOn':'2026-01-01','leftOn':None} for i in range(1,5)]
        return {'members':{'data':members},'history':{'data':[{'userId':i,'isJoined':True,'date':'2026-01-01'} for i in range(1,5)]},
                'calendar':{'data':{'events':[],'holidays':[{'startDate':'2026-10-06','endDate':'2026-10-06'}],
                  'leaves':[{'userId':3,'startDate':'2026-10-07','endDate':'2026-10-07','startDatePortion':'all_day','endDatePortion':'all_day'}]}}}

    def test_guidance_example_is_26_net_days_and_excludes_non_billable(self):
        c=pms_capacity.normalize(self.raw(),'2026-10-05','2026-10-16',[0,1,2,3,4])
        self.assertEqual(c['resource_days'],26)
        self.assertEqual([r['net_days'] for r in c['resources']],[9,9,8])
        self.assertEqual(c['non_billable_count'],1)

    def test_holiday_and_duplicate_half_leave_are_not_deducted_twice(self):
        raw=self.raw();r=raw['calendar']['data']['leaves'][0]
        r.update(startDate='2026-10-06',endDate='2026-10-06')
        self.assertEqual(pms_capacity.normalize(raw,'2026-10-05','2026-10-16',[0,1,2,3,4])['resource_days'],27)
        r.update(startDate='2026-10-07',endDate='2026-10-07',startDatePortion='afternoon',endDatePortion='afternoon')
        raw['calendar']['data']['leaves'].append(copy.deepcopy(r))
        self.assertEqual(pms_capacity.normalize(raw,'2026-10-05','2026-10-16',[0,1,2,3,4])['resource_days'],26.5)
        r['startDatePortion']='morning';r['endDatePortion']='morning'
        self.assertEqual(pms_capacity.normalize(raw,'2026-10-05','2026-10-16',[0,1,2,3,4])['resource_days'],26)

    def test_unknown_portions_and_departed_resources_withhold_capacity(self):
        raw=self.raw();raw['calendar']['data']['leaves'][0]['startDatePortion']='unknown'
        with self.assertRaises(ValueError):pms_capacity.normalize(raw,'2026-10-05','2026-10-16',[0,1,2,3,4])
        raw=self.raw();raw['history']['data'].append({'userId':99,'date':'2026-10-05','isJoined':False})
        with self.assertRaises(ValueError):pms_capacity.normalize(raw,'2026-10-05','2026-10-16',[0,1,2,3,4])

    def test_fixed_windows_do_not_credit_delivery_twice(self):
        k=self.kif();profile={'periods':{'cadence':{'anchor':'2026-10-03','days':14}}}
        out=reporting.intervalize(k,profile,'2026-10-30')
        self.assertEqual(len(out['periods']),2)
        self.assertEqual(sum(bool(t.get('delivered')) for t in out['tasks']),1)
        self.assertEqual(out['periods'][1]['start'],'2026-10-17')
        self.assertEqual(k['periods'][0]['name'],'Cycle')

    def test_whole_project_windows_clip_opening_and_show_upcoming(self):
        cfg={'anchor':'2026-10-03','days':14,'start':'2026-09-07','end':'2026-10-30'}
        windows=reporting.windows(cfg,'2026-10-07')
        self.assertEqual([(p['start'],p['end']) for p in windows],
                         [('2026-09-07','2026-09-18'),('2026-09-19','2026-10-02'),('2026-10-03','2026-10-16'),('2026-10-17','2026-10-30')])
        self.assertTrue(windows[-1]['upcoming']);self.assertIn('partial',windows[0]['notes'])
        self.assertEqual(windows[0]['as_of'],'2026-09-18')

    def test_future_window_has_no_output_capacity_or_review_calls(self):
        k=self.kif();cfg={'periods':{'cadence':{'anchor':'2026-10-03','end':'2026-10-30'}},'policy':{'velocity':{'mode':'per_resource_day'}}}
        out=reporting.intervalize(k,cfg,'2026-10-07');future=out['periods'][-1]
        self.assertFalse(any(t['period']==future['name'] for t in out['tasks']))
        e=self.engine(out,cfg);m=e.velocity(future);reporting.apply(e,m,future)
        self.assertIsNone(m.value);self.assertEqual(m.unit,'SP/resource-day')
        result={'periods':[{'period':future['name'],'measures':[{'name':'Velocity','value':None,'note':'Future window'}]}]}
        self.assertEqual(team_review.prepare(out,result,{},True),([],[]))

    def test_explicit_period_replacement_is_retained_across_reruns(self):
        import workbook_history as H
        old={'name':'Old milestone','start':'2026-09-07','end':'2026-09-10'}
        k=self.kif();history={'periods':{H.period_key(old):{'period':old}}}
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(H.replace_periods(history,k,Path(d)),{'Old milestone'})
            self.assertFalse(history['periods']);self.assertEqual(len(list((Path(d)/'archives').glob('*.json'))),1)
            self.assertEqual(H.replace_periods(history,k,Path(d)),{'Old milestone'})

    def test_old_rework_and_uncertain_event_attribution_are_not_credited(self):
        k=self.kif();k['tasks'][0].update(reopened='Yes',reopen_count=1,rework_dates=['2026-09-30'])
        profile={'periods':{'cadence':{'anchor':'2026-10-03','days':14}}}
        t=reporting.intervalize(k,profile,'2026-10-16')['tasks'][0]
        self.assertEqual(t['reopened'],'No');self.assertEqual(t['reopen_count'],0)
        k['tasks'][0]['rework_dates']=None
        self.assertIsNone(reporting.intervalize(k,profile,'2026-10-16')['tasks'][0]['reopened'])

    def test_unresolved_current_return_event_withholds_rework_rate(self):
        k=self.kif();k['tasks'][0].update(reopened=None,rework_candidates=['2026-10-06'])
        profile={'periods':{'cadence':{'anchor':'2026-10-03'}}};out=reporting.intervalize(k,profile,'2026-10-07')
        e=self.engine(out,profile);p=out['periods'][0];m=e.rework_rate(p);reporting.apply(e,m,p)
        self.assertIsNone(m.value);self.assertTrue(m.publish_blocked)

    def test_incomplete_estimated_total_cannot_understate_a_rate(self):
        k=self.kif();extra=copy.deepcopy(k['tasks'][0]);extra.update(key='EX-2',_item='2',_row='2',story_points=None);k['tasks'].append(extra)
        k['periods'][0]['capacity']={'resource_days':26}
        profile={'sources':{'missing_estimate':'partial'},'policy':{'velocity':{'mode':'per_resource_day'}}}
        e=self.engine(k,profile);m=e.velocity(k['periods'][0]);self.assertEqual(m.value,26)
        reporting.apply(e,m,k['periods'][0]);self.assertIsNone(m.value)

    def test_equal_bug_counts_have_different_density_for_different_scope(self):
        k=self.kif();k['defects']=[{'key':f'EX-B{i}','period':'Cycle','kind':'Bug','rejected':'No','pre_existing':'No','phase':'QA'} for i in range(4)]
        profile={'policy':{'measurement_units':{'defect_rate':'story_points'}}}
        e=self.engine(k,profile);m=e.defect_rate(k['periods'][0]);reporting.apply(e,m,k['periods'][0])
        self.assertAlmostEqual(m.value,15.38)
        k['tasks'][0]['story_points']=52
        e=self.engine(k,profile);m=e.defect_rate(k['periods'][0]);reporting.apply(e,m,k['periods'][0])
        self.assertAlmostEqual(m.value,7.69)
        self.assertEqual(m.unit,'defects/100 story points')

    def test_weighted_report_rates_require_report_estimates(self):
        k=self.kif();k['defects']=[{'key':'EX-B','period':'Cycle','kind':'Bug','rejected':'Yes'}]
        profile={'policy':{'measurement_units':{'rejection_rate':'story_points'}}}
        e=self.engine(k,profile);m=e.rejection_rate(k['periods'][0]);reporting.apply(e,m,k['periods'][0])
        self.assertIsNone(m.value);self.assertIsNone(m.denominator)
        self.assertTrue(any('missing' in g.lower() for g in m.gaps))

    def test_final_review_stays_stale_until_a_person_renews_it(self):
        k=self.kif();facts={};results={'periods':[{'period':'Cycle','measures':[{'name':'Velocity','value':26,'note':'26 points','unit':'SP'}]}]}
        rows,_=team_review.prepare(k,results,facts,True);r=facts['team_review']['rows'][rows[0]['item']]
        r.update(decision='Approved',why='Reviewed completion evidence',reviewer='Reviewer',decided_on='2026-10-07',review_basis=r['basis'])
        self.assertEqual(team_review.prepare(k,results,facts,True)[0][0]['status'],'Resolved')
        results['periods'][0]['measures'][0]['value']=30
        self.assertEqual(team_review.prepare(k,results,facts,True)[0][0]['status'],'Stale')

    def test_applying_a_final_item_call_does_not_make_its_own_review_stale(self):
        k=self.kif();t=k['tasks'][0];t.update(reopened='Yes',rework_candidates=['2026-10-05'],_source_fingerprint='source-a')
        facts={};results={'periods':[]};rows,_=team_review.prepare(k,results,facts,True)
        r=facts['team_review']['rows'][rows[0]['item']]
        r.update(decision='No',why='Environment failure, no implementation fault',reviewer='Reviewer',decided_on='2026-10-07',review_basis=r['basis'])
        t['reopened']='No';t['basis']={'reopened':{'why':'Human decision and team feedback'}}
        self.assertEqual(team_review.prepare(k,results,facts,True)[0][0]['status'],'Resolved')
        t['_source_fingerprint']='source-b'
        self.assertEqual(team_review.prepare(k,results,facts,True)[0][0]['status'],'Stale')
        self.assertEqual(team_review.prepare(k,results,facts,True)[0][0]['status'],'Stale')

    def test_email_dry_run_has_no_delivery_side_effect(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'status.json';path.write_text(json.dumps({'subject':'KPI review','body':'Synthetic report'}))
            with patch('notifications.smtplib.SMTP') as smtp:
                preview=notifications.send(path,{'channels':['email'],'email':{'to':['reviewer@example.com']}},False)
                smtp.assert_not_called();self.assertTrue(preview['email']['dry_run'])

    def test_host_gmail_route_needs_host_delivery_and_no_smtp(self):
        cfg={'channels':['email'],'email':{'route':'host_gmail','from':'kpi@example.com','to':['reviewer@example.com']}}
        self.assertEqual(notifications.questions(cfg),[])
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'status.json';path.write_text(json.dumps({'subject':'KPI review','body':'Synthetic report'}))
            with patch('notifications.smtplib.SMTP') as smtp:
                self.assertEqual(notifications.send(path,cfg,False)['email']['route'],'host_gmail')
                with self.assertRaisesRegex(ValueError,'assistant-host Gmail'):notifications.send(path,cfg,True)
                smtp.assert_not_called()

    def test_review_shows_missing_measurement_reason(self):
        results={'periods':[{'period':'Cycle','measures':[{'name':'Velocity','value':None,'note':'Implementation reviewed','unmeasured_note':'Review needed: no assigned estimate'}]}]}
        rows,_=team_review.prepare(self.kif(),results,{},True)
        self.assertIn('Not measured',rows[0]['proposal'])
        results['periods'][0]['measures'][0]['gaps']=['Review needed: no assigned estimate']
        self.assertIn('no assigned estimate',team_review.prepare(self.kif(),results,{},True)[0][0]['proposal'])


if __name__=='__main__':unittest.main()
