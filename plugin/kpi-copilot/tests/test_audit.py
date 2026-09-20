"""Failure-path regressions from the product audit. No credentials or live writes."""
from __future__ import annotations
import contextlib
import copy
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import board, classify, judge, kpi, kpi_engine, kpi_registry, ledger
import pms_push, profile_lib, profile_tool, sheet_google, sheet_model, sheet_readback, sheet_xlsx, sources
import yaml
from openpyxl import Workbook, load_workbook


def adapter(name):
    spec = importlib.util.spec_from_file_location('audit_' + name, ROOT / 'adapters' / name / 'api.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        shutil.copytree(ROOT / 'examples' / 'northwind-board', self.base / 'fixture')
        self.profile = self.base / 'fixture' / 'profile.yaml'
        self.profile_data = profile_lib.load(self.profile)
        self.snap = json.loads((self.profile.parent / 'board.json').read_text())
        self.args = SimpleNamespace(profile=str(self.profile), project='northwind-q3', today='2026-09-18',
                                    date=None, offline=False, by='', no_publish=False)

    def ws(self):
        return kpi.Workspace(self.args)

    def test_configured_registry_is_used_by_engine_and_sheet(self):
        reg = json.loads(kpi_registry.DEFAULT.read_text())
        reg['source'] = 'pms'
        reg['projects'] = {'101': {'defect_rate': {'threshold': 87}}}
        self.profile_data['organization']['kpi_registry'] = 'targets/custom.json'
        self.profile.write_text(yaml.safe_dump(self.profile_data))
        target = self.profile.parent / 'targets' / 'custom.json'
        target.parent.mkdir()
        target.write_text(json.dumps(reg))
        ws = self.ws()
        kif, _ = classify.to_kif(self.snap, ws.profile, ws.project, ws.facts, ws.ledger, ws.today)
        ws.run_dir.mkdir(parents=True)
        path = ws.run_dir / 'run.kif.json'
        path.write_text(json.dumps(kif))
        results = kpi.compute(ws, path)
        m = next(m for m in results['periods'][0]['measures'] if m['key'] == 'defect_rate')
        self.assertEqual(m['threshold'], 87)
        self.assertEqual(kpi._registry(ws), reg)
        tabs = sheet_model.build(kif, results, {'profile': ws.profile, 'registry': reg})
        config = next(t for t in tabs if t.name == 'Config')
        row = next(r for (r,c), cell in config.cells.items() if c == 2 and cell.get('v') == 'Defect Rate')
        self.assertEqual(config.cells[row,6]['v'], 87)
        self.assertTrue(config.cells[row,7]['v'])

    def test_profile_override_type_fails_before_workspace_created(self):
        self.profile_data['projects'][0]['overrides'] = {'policy': {'count_observations': 'false'}}
        self.profile.write_text(yaml.safe_dump(self.profile_data))
        with self.assertRaises(SystemExit):
            self.ws()
        self.assertFalse((self.profile.parent / 'northwind-q3' / 'ledger.json').exists())

    def test_custom_registry_missing_does_not_silently_fallback(self):
        with self.assertRaises(SystemExit):
            kpi_registry.resolve_path(self.profile, {'organization': {'kpi_registry': 'missing.json'}})

    def test_corrupt_memory_and_baseline_are_preserved(self):
        for filename, reader in [('ledger.json', ledger.Ledger), ('sheet_state.json', sheet_readback.load_state)]:
            p = self.base / filename
            p.write_text('{broken')
            with self.assertRaises(SystemExit):
                reader(p)
            self.assertEqual(p.read_text(), '{broken')

    def test_failed_readback_stops_before_overwrite(self):
        ws = self.ws()
        book = ws.dir / 'review.xlsx'
        book.write_bytes(b'not a zip')
        state = {'destination': {'kind': 'xlsx', 'path': str(book)}, 'values': {'Config': {}}}
        sheet_readback.save_state(ws.dir / 'sheet_state.json', state)
        with self.assertRaisesRegex(SystemExit, 'Nothing will overwrite'):
            kpi.read_back(ws, {}, self.args)
        self.assertEqual(book.read_bytes(), b'not a zip')

    def test_remote_offline_preview_keeps_original_baseline_and_file(self):
        ws = self.ws()
        book = ws.dir / 'review.xlsx'
        book.write_bytes(b'keep local edits too')
        state = {'destination': {'kind': 'google', 'id': 'sheet-123', 'path': str(book)}, 'values': {'Config': {}}}
        path = ws.dir / 'sheet_state.json'
        sheet_readback.save_state(path, state)
        before = path.read_bytes()
        self.args.offline = True
        self.assertTrue(kpi.read_back(ws, {}, self.args))
        tab = sheet_model.Tab('Preview')
        tab.put(1, 1, 'preview')
        with patch.object(sheet_model, 'build', return_value=[tab]):
            dest, _ = kpi.publish(ws, {}, {}, {}, self.args)
        self.assertIn('Preview - ', dest['path'])
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(book.read_bytes(), b'keep local edits too')

    def test_failed_google_publish_preserves_destination(self):
        ws = self.ws()
        ws.profile['output'] = {'workbook': 'google-sheets'}
        state = {'destination': {'kind': 'google', 'id': 'sheet-123'}, 'values': {}}
        ws.previous_sheet_state = state
        path = ws.dir / 'sheet_state.json'
        sheet_readback.save_state(path, state)
        before = path.read_bytes()
        tab = sheet_model.Tab('Preview'); tab.put(1, 1, 'value')
        with patch.object(sheet_model, 'build', return_value=[tab]), \
             patch.object(kpi.G, 'how_signed_in', return_value='test'), \
             patch.object(sheet_google, 'publish', side_effect=kpi.G.GoogleError('unavailable')):
            _, notes = kpi.publish(ws, {}, {}, {}, self.args)
        self.assertIn('not updated', notes[0])
        self.assertEqual(path.read_bytes(), before)

    def test_local_writer_preserves_custom_tabs_and_literal_text(self):
        path = self.base / 'review.xlsx'
        wb = Workbook(); wb.active.title = 'My notes'; wb.active['A1'] = 'Keep this'; wb.save(path)
        tab = sheet_model.Tab('Task Register'); tab.put(1, 1, '=HYPERLINK("bad","bad")')
        sheet_xlsx.write([tab], path)
        wb = load_workbook(path)
        self.assertEqual(wb['My notes']['A1'].value, 'Keep this')
        self.assertEqual(wb['Task Register']['A1'].data_type, 's')

    def test_google_readback_is_not_cut_off_at_2000_rows(self):
        class Session:
            def call(self, *args, **kw):
                self.ranges = kw['params']['ranges']
                return {'valueRanges': [{'values': [['x']] * 2101}]}
        s = Session(); grid = sheet_google.read_grid('id', ["Lead's tasks"], session=s)
        self.assertEqual(grid.rows("Lead's tasks"), 2101)
        self.assertEqual(s.ranges, ["'Lead''s tasks'"])

    def test_missing_review_tab_is_not_treated_as_cleared_cells(self):
        ws = self.ws()
        grid = lambda *args: None
        grid.rows = lambda tab: 0
        with self.assertRaisesRegex(ValueError, 'missing or empty'):
            sheet_readback.fold({'values': {'Config': {}}, 'spec': {'Config': {'kind':'cells','cells':{}}}},
                                grid, ws.ledger, ws.facts, {}, {})

    def test_changed_comment_invalidates_judgement(self):
        item = copy.deepcopy(self.snap['items'][0]); item['comments'] = [{'text':'no clarification', 'at':'2026-09-01'}]
        first = board.fingerprint(item)
        item['comments'][0]['text'] = 'client explained the requirement'
        self.assertNotEqual(first, board.fingerprint(item))

    def test_undecidable_answer_becomes_persistent_person_question(self):
        ws = self.ws()
        c = classify.Classifier(self.snap, ws.profile, ws.project, ws.facts, ws.ledger, ws.today)
        item = self.snap['items'][0]
        path = self.base / 'answers.json'
        path.write_text(json.dumps({'answers':[{'item_id':item['id'], 'field':'understood', 'value':None,
                                                'why':'Client clarification is not recorded.'}]}))
        judge.apply_answers(path, self.snap, ws.ledger, ws.facts, c.period_names)
        c.settle(item, 'understood', classify.Proposal('Yes','uncertain',0.5), 'Was it understood?', ['Yes','No'])
        self.assertFalse(c.queue)
        self.assertEqual(len(c.questions), 1)
        sheet_readback._file_answer(c.questions[0]['id'], 'No', ws.ledger, ws.facts)
        self.assertEqual(ws.ledger.get(item['id'], 'understood')['value'], 'No')
        self.assertIsNone(ws.ledger.get(item['id'], 'deferred:understood'))

    def test_stale_digest_is_withheld_but_not_deleted(self):
        facts = {'plan': {'source': {'fingerprint':'old'}, 'items':[{'title':'Scope'}]}}
        active, problems = sources.usable_facts([{'role':'plan','state':'fresh','path':'plan.pdf','fingerprint':'new'}], facts)
        self.assertEqual(active['plan'], {})
        self.assertTrue(facts['plan']['items'])
        self.assertTrue(problems)

    def test_changed_source_does_not_reuse_other_source_cache(self):
        ws = self.ws()
        source = self.base / 'old.pdf'; source.write_bytes(b'old source')
        sources.pull({'sources':{'plan':{'kind':'pdf','ref':str(source)}}},ws.dir,self.base,offline=True)
        result = sources.pull({'sources':{'plan':{'kind':'pdf','ref':'new-missing.pdf'}}},ws.dir,self.base,offline=True)
        self.assertEqual(result[0]['state'],'missing')
        self.assertIsNone(result[0]['path'])

    def test_mapping_never_falls_back_to_another_tab(self):
        path = self.base / 'data.xlsx'; wb = Workbook(); wb.active.title='Other project'
        wb.active.append(['Item','Hours']); wb.active.append(['Secret scope',8]); wb.save(path)
        rows, problem = sources.table(path, {'tab':'Expected project','columns':{'title':'Item','dev_hours':'Hours'}})
        self.assertEqual(rows,[]); self.assertIn('missing',problem)

    def test_empty_mapped_table_removes_old_rows(self):
        path = self.base / 'data.csv'; path.write_text('Item,Hours\n')
        facts = {'estimates':{'items':[{'title':'removed'}]}}
        sources.facts_from_mapping({'role':'estimates','path':str(path),'fingerprint':'new'},
                                   {'map':{'columns':{'title':'Item','dev_hours':'Hours'}}},facts)
        self.assertEqual(facts['estimates']['items'],[])

    def test_velocity_missing_is_not_zero_and_zero_is_valid(self):
        ws = self.ws()
        kif, _ = classify.to_kif(self.snap, ws.profile, ws.project, ws.facts, ws.ledger, ws.today)
        t = next(t for t in kif['tasks'] if t.get('delivered') and t['type'] != 'Excluded')
        kif['tasks']=[t]; kif['project']['velocity_unit']='Story Points'
        per = next(p for p in kif['periods'] if p['name']==t['period'])
        reg = kpi._registry(ws)
        t['story_points']=None
        self.assertIsNone(kpi_engine.Engine(copy.deepcopy(kif),ws.profile,reg).velocity(per).value)
        t['story_points']=0
        self.assertEqual(kpi_engine.Engine(copy.deepcopy(kif),ws.profile,reg).velocity(per).value,0)

    def test_long_period_names_remain_valid_join_keys(self):
        ws=self.ws(); facts=copy.deepcopy(ws.facts)
        old=facts['periods']['periods'][0]['name']; new=old+' with a long descriptive name'
        facts['periods']['periods'][0]['name']=new
        for role in ('plan','estimates'):
            for item in facts.get(role,{}).get('items',[]):
                if item.get('period')==old: item['period']=new
        kif,_=classify.to_kif(self.snap,ws.profile,ws.project,facts,ws.ledger,ws.today)
        self.assertIn(new,[p['name'] for p in kif['periods']])
        self.assertTrue(all(t['period'] in [p['name'] for p in kif['periods']] for t in kif['tasks']))

    def test_formula_ranges_cover_large_boards(self):
        ws=self.ws(); kif,_=classify.to_kif(self.snap,ws.profile,ws.project,ws.facts,ws.ledger,ws.today)
        task=copy.deepcopy(kif['tasks'][0]); kif['tasks']=[dict(task,key=f'T-{i}') for i in range(1100)]
        engine=kpi_engine.Engine(kif,ws.profile,kpi._registry(ws))
        results={'periods':[r.as_dict() for r in engine.run()]}
        tabs=sheet_model.build(kif,results,{'profile':ws.profile})
        sm=next(t for t in tabs if t.name=='KPI Summary')
        self.assertIn(f'${1100 + sheet_model.SPARE + 4}', sm.cells[4,5]['f'])

    def test_jira_uses_fully_paginated_history(self):
        jira=adapter('jira')
        issue={'id':'1','key':'DEMO-1','fields':{},'changelog':{'histories':[]},'_histories':[
            {'created':'2026-09-01','items':[{'field':'status','fromString':'Open','toString':'Closed'}]}]}
        issue['changelog']['histories']=[{'created':'2026-08-01','items':[]}]
        it=jira.item_from_issue(issue,'https://example.atlassian.net',None,'Points','Hours')
        self.assertEqual(it['events'][0]['to'],'Closed')

    def test_github_paginates_comments_and_history(self):
        gh=adapter('github')
        node={'id':'I_1','comments':{'nodes':[{'bodyText':'first'}],'pageInfo':{'hasNextPage':True,'endCursor':'c'}},
              'timelineItems':{'nodes':[],'pageInfo':{'hasNextPage':True,'endCursor':'t'}}}
        class Client:
            def query(self,q,v):
                field='comments' if v['after']=='c' else 'timelineItems'
                return {'node':{field:{'nodes':[{'bodyText':'last'}] if field=='comments' else [{'__typename':'ReopenedEvent'}],
                                      'pageInfo':{'hasNextPage':False}}}}
        got=gh.complete_issue(Client(),node,gh._FULL)
        self.assertEqual(len(got['comments']['nodes']),2)
        self.assertEqual(got['timelineItems']['nodes'][0]['__typename'],'ReopenedEvent')

    def test_pms_wrong_project_is_refused_before_network(self):
        self.profile_data['output']['mode']='assisted-push'
        self.profile.write_text(yaml.safe_dump(self.profile_data))
        payload=self.base/'payload.json'; payload.write_text(json.dumps([{'projectId':999,'periodId':1,'name':'Cycle','kpis':[]}]))
        with patch.object(pms_push,'_api') as api:
            result=pms_push.main(['--profile',str(self.profile),'--payloads',str(payload),'--apply'])
        self.assertEqual(result,2); api.assert_not_called()

    def test_pms_array_response_and_string_period_ids(self):
        raw=[{'name':'Velocity','periods':[{'periodId':7,'periodKpiValue':{'value':0,'note':'zero'}}]}]
        with patch.object(pms_push,'_api',return_value=raw):
            self.assertEqual(pms_push.read_current('https://pms.example.com',101,None)['7']['Velocity']['value'],0)

    def test_minimal_profile_and_local_targets(self):
        path=self.base/'minimal.yaml'
        profile_tool.init(path,None)
        self.assertEqual(profile_tool.validate(path),0)
        self.profile_data['targets']={'defect_rate':{'value':20,'why':'Agreed phase target'}}
        self.profile.write_text(yaml.safe_dump(self.profile_data))
        ws=self.ws()
        kif,_=classify.to_kif(self.snap,ws.profile,ws.project,ws.facts,ws.ledger,ws.today)
        ws.run_dir.mkdir(parents=True); path=ws.run_dir/'run.kif.json'; path.write_text(json.dumps(kif))
        result=kpi.compute(ws,path)
        measure=next(m for m in result['periods'][0]['measures'] if m['key']=='defect_rate')
        self.assertEqual(measure['threshold'],20)
        self.assertIn('Local review target',measure['threshold_source'])

    def test_registry_uses_maximum_when_minimum_is_null(self):
        targets,_=kpi_registry.project_thresholds([{'name':'Defect Rate','threshold':None,'minValue':None,'maxValue':15}])
        self.assertEqual(targets['defect_rate']['threshold'],15)

    def test_google_expands_grid_before_dimension_changes(self):
        tab=sheet_model.Tab('Example'); tab.put(1,30,'Wide')
        reqs=sheet_google.tab_requests(tab,1,0,{'properties':{'gridProperties':{'rowCount':5,'columnCount':8}}})
        resize=next(i for i,x in enumerate(reqs) if 'updateSheetProperties' in x)
        dimensions=next(i for i,x in enumerate(reqs) if 'updateDimensionProperties' in x)
        self.assertLess(resize,dimensions)

    def test_wrong_pms_period_owner_never_writes(self):
        import os
        self.profile_data['output']['mode']='assisted-push'
        self.profile.write_text(yaml.safe_dump(self.profile_data))
        payload=self.base/'payload.json'; payload.write_text(json.dumps([{'projectId':101,'periodId':7,'name':'Cycle','kpis':[]}]))
        calls=[]
        def api(base,path,**kw):
            calls.append(kw.get('method','GET'))
            return {'projectId':999}
        with patch.dict(os.environ,{'PMS_TOKEN':'test-only'}), patch.object(pms_push,'read_current',return_value={}), patch.object(pms_push,'_api',side_effect=api):
            result=pms_push.main(['--profile',str(self.profile),'--payloads',str(payload),'--apply'])
        self.assertNotEqual(result,0)
        self.assertNotIn('PUT',calls)

    def test_incomplete_pms_payload_never_writes(self):
        self.profile_data['output']['mode']='assisted-push'
        self.profile.write_text(yaml.safe_dump(self.profile_data))
        payload=self.base/'payload.json'; payload.write_text(json.dumps([{'projectId':101,'periodId':7,'name':'Cycle','kpis':[], 'skipped':[{'name':'Velocity'}]}]))
        with patch.object(pms_push,'_api') as api:
            result=pms_push.main(['--profile',str(self.profile),'--payloads',str(payload),'--apply'])
        self.assertEqual(result,2); api.assert_not_called()

    def test_legacy_push_log_without_timestamp(self):
        ws=self.ws(); ws.run_dir.mkdir(parents=True)
        (ws.run_dir/'push_log.json').write_text(json.dumps([{'period':'Cycle','result':'verified'}]))
        rows,pushed=kpi.push_history(ws)
        self.assertEqual(len(rows),1); self.assertIn('Cycle',pushed)

    def test_run_label_cannot_escape_workspace(self):
        self.args.date='../outside'
        with self.assertRaisesRegex(SystemExit,'single folder'):
            self.ws()

    def test_unresolved_plan_workbook_matches_engine_including_future_dates(self):
        import formulas
        with contextlib.redirect_stdout(io.StringIO()):
            code=kpi.main(['run','--profile',str(self.profile),'--project','northwind-q3',
                          '--board',str(self.profile.parent/'board.json'),'--offline','--today','2026-09-01'])
        self.assertEqual(code,0)
        directory=self.profile.parent/'northwind-q3'
        book=next(directory.glob('KPI Tracker*.xlsx'))
        result=json.loads((directory/'runs/2026-09-01/results.json').read_text())
        sol=formulas.ExcelModel().loads(str(book)).finish().calculate()
        live={str(key).split('!')[-1].strip("'"):value.value[0][0] for key,value in sol.items() if 'KPI SUMMARY' in str(key).upper()}
        sheet=load_workbook(book)['KPI Summary']
        for row in range(4,sheet.max_row+1):
            period,name=sheet.cell(row,1).value,sheet.cell(row,3).value
            if not period: continue
            expected=next(m['value'] for p in result['periods'] if p['period']==period for m in p['measures'] if m['name']==name)
            actual=live[f'G{row}']; actual=None if actual in ('',None) else round(float(actual),2)
            self.assertEqual(actual,None if expected is None else round(expected,2),f'{period}: {name}')
        self.assertFalse(any('TODAY()' in str(c.value) for sh in load_workbook(book) for row in sh for c in row))

    def test_rerun_without_period_facts_preserves_missing_period_question(self):
        (self.profile.parent/'northwind-q3/facts/periods.yaml').unlink(missing_ok=True)
        args=['run','--profile',str(self.profile),'--project','northwind-q3','--board',str(self.profile.parent/'board.json'),'--offline']
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(kpi.main(args),0)
            self.assertEqual(kpi.main(args),0)
        nxt=json.loads((self.profile.parent/'northwind-q3/next.json').read_text())
        self.assertTrue(any(q['id']=='periods' for q in nxt['questions']))

    def test_pms_readback_mismatch_is_a_failure(self):
        import os
        self.profile_data['output']['mode']='assisted-push'
        self.profile.write_text(yaml.safe_dump(self.profile_data))
        payload=self.base/'payload.json'; payload.write_text(json.dumps([{'projectId':101,'periodId':7,'name':'Cycle',
            'kpis':[{'name':'Velocity','kpiId':1,'value':10,'note':'10 points'}]}]))
        log=self.base/'push.json'
        with patch.dict(os.environ,{'PMS_TOKEN':'test-only'}), patch.object(pms_push,'read_current',side_effect=[{},None]), patch.object(pms_push,'_api',return_value={'projectId':101}):
            result=pms_push.main(['--profile',str(self.profile),'--payloads',str(payload),'--apply','--log',str(log)])
        self.assertNotEqual(result,0)
        self.assertIn('mismatch',json.loads(log.read_text())['results'][0]['result'])

    def test_changed_inputs_and_unresolved_review_refuse_submission(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(kpi.main(['run','--profile',str(self.profile),'--project','northwind-q3',
                '--board',str(self.profile.parent/'board.json'),'--offline']),0)
        args=['push','--profile',str(self.profile),'--project','northwind-q3','--apply']
        with patch.object(kpi,'_module') as writer:
            with self.assertRaisesRegex(SystemExit,'still needs review'): kpi.main(args)
            self.profile_data['owner']['name']='Changed owner'
            self.profile.write_text(yaml.safe_dump(self.profile_data))
            with self.assertRaisesRegex(SystemExit,'Inputs changed'): kpi.main(args)
            writer.assert_not_called()


if __name__ == '__main__':
    unittest.main()
