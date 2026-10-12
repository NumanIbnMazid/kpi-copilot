"""One review surface for KPI summaries and disputed item judgments.

Feedback is retained independently; only a named, reasoned final call changes a
judgment. Review approval never grants authority to submit a PMS payload.
"""
import hashlib
import json
import datetime as dt


COLS=[('period','Period',20,'data',''),('subject','KPI / item',28,'data',''),
      ('proposal','Current judgment / result',42,'data',''),('evidence','Evidence',8,'data',''),
      ('dev','Dev feedback',32,'in',''),('qa','QA feedback',32,'in',''),
      ('decision','Final call',18,'in',''),('why','Final justification',55,'in',''),
      ('reviewer','Decided by',20,'in',''),('decided_on','Decision date',14,'in',''),
      ('status','Review status',18,'data',''),('updated_at','Updated at',22,'data',''),
      ('item','Review ID',12,'data',''),('basis','Basis',12,'data','')]


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()


def prepare(kif,results,facts,enabled,profile=None):
    if not enabled: return [],[]
    store=facts.setdefault('team_review',{}).setdefault('rows',{})
    rows=[];questions=[]
    active={p['period'] for p in results['periods'] if not any(x.get('name')==p['period'] and x.get('upcoming') for x in kif.get('periods',[]))}
    if not results['periods']:active={p['name'] for p in kif.get('periods',[]) if not p.get('upcoming')}
    def add(r, basis):
        ident=r['item'];sig=digest(basis);old=store.get(ident,{})
        data={**r,**{k:old.get(k) for k in ('dev','qa','decision','why','reviewer','decided_on','updated_at','review_basis')},'basis':sig}
        complete=all(data.get(k) for k in ('decision','why','reviewer','decided_on'))
        valid=data['decision']=='Approved' if ident.startswith(('kpi:','action:')) else data['decision'] in ('Yes','No')
        data['status']='Resolved' if complete and old.get('review_basis')==sig and valid else 'Stale' if complete and old.get('review_basis')!=sig else 'Open'
        if data['status']=='Stale':
            data['proposal']+=' Previous final call needs review because the facts changed.'
        store[ident]=data;rows.append(data)
    for p in results['periods']:
        if any(x.get('name')==p['period'] and x.get('upcoming') for x in kif.get('periods',[])):continue
        for m in p['measures']:
            if m.get('availability')=='Not due yet':continue
            # Keep the review list scannable; KPI Summary retains the full narrative.
            text=m.get('note') or m.get('unmeasured_note') or ''
            proposal='. '.join(text.split('. ')[:3]).rstrip('.')
            if m.get('value') is None:
                proposal='Not measured. '+proposal
                gap=next(iter(m.get('gaps') or []),'')
                if gap and gap not in proposal:proposal+='. Needs review: '+gap
            add({'item':'kpi:'+p['period']+'|'+m['name'],'period':p['period'],'subject':m['name'],
                 'proposal':proposal,'evidence':None},
                {k:m.get(k) for k in ('value','unit','numerator','denominator','note','unmeasured_note','threshold')})
            for gap in dict.fromkeys(m.get('gaps') or []):
                ident='action:'+p['period']+'|'+digest(gap)[:12]
                add({'item':ident,'period':p['period'],'subject':m['name']+' — check needed',
                     'proposal':gap+' Please agree who can resolve this; it may need the project lead rather than Dev or QA.',
                     'evidence':None},gap)
    for kind,field in [('tasks','reopened'),('defects','rejected'),('tasks','delivery_eligible')]:
        for t in kif.get(kind,[]):
            if t.get('period') not in active:continue
            ledger_field='delivery' if field=='delivery_eligible' else field
            ident=f'item:{t["period"]}|{t.get("_item")}|{ledger_field}'
            if field=='reopened' and t.get(field)!='Yes' and not t.get('rework_candidates'):continue
            if field=='rejected' and t.get(field)!='Yes' and ident not in store:continue
            if field=='delivery_eligible' and t.get(field)!='No' and ident not in store:continue
            b=(t.get('basis') or {}).get(ledger_field) or {}
            prompt={'reopened':'Does this return count as rework caused by this item’s own implementation?',
                    'rejected':'Should this report be treated as rejected rather than a valid bug?',
                    'delivery_eligible':'Did closure include an implemented change accepted by Dev and QA?'}[field]
            add({'item':ident,'period':t['period'],'subject':f'{t["key"]} — {t["title"]}',
                 'proposal':prompt+' Current call: '+str(t.get(field) or 'not yet decided')+'. '+str(b.get('why') or t.get('rejection_reason') or t.get('rework_evidence') or ''),
                 'evidence':t.get('link'),'tracker_item':t.get('_item'),'field':ledger_field},
                # A person's final call changes the judgment, not its source evidence.
                # Bind approval to the source and rules so that applying the call does
                # not immediately invalidate the approval itself.
                {'source':t.get('_source_fingerprint') or {'title':t.get('title'),'link':t.get('link')},
                 'field':ledger_field,'candidate_dates':t.get('rework_candidates'),
                 'workflow':(profile or {}).get('workflow'),'policy':(profile or {}).get('policy')})
    for t in kif.get('tasks',[]):
        if t.get('period') not in active:continue
        if t.get('type')=='Excluded':continue
        needs=[]
        if not t.get('effort_group') and t.get('story_points') is None and kif.get('project',{}).get('velocity_unit')=='Story Points':
            needs.append('Agree and record story points. Do not estimate them from the ticket count.')
        if t.get('delivered') and t.get('understood') is None:
            needs.append('Confirm whether the team needed the client to explain the requirement.')
        if t.get('type')=='CR' and not t.get('approved_on'):
            needs.append('Record when the request was approved, and confirm whether it adds work or changes an agreed requirement.')
        elif t.get('type')=='CR' and not t.get('request_kind'):
            needs.append('Confirm whether the request adds a new deliverable or changes an agreed requirement.')
        if not needs:continue
        ident='action:'+t['period']+'|'+str(t.get('_item'))+'|attention'
        add({'item':ident,'period':t['period'],'subject':t['key']+' — '+t['title'],
             'proposal':' '.join(needs)+' Agree who can provide the missing information.',
             'evidence':t.get('link')},needs)
    for p in dict.fromkeys(r['period'] for r in rows if r['status']!='Resolved'):
        questions.append({'id':'team-review:'+p,'about':p,'question':'Review the pending rows in Team Review. Dev and QA can comment separately; record the final decision, reason, reviewer and date there.',
                          'blocking':((profile or {}).get('output') or {}).get('team_review_blocks',True) is not False,
                          'link':'kpi-view:Team Review|'+p})
    return rows,questions


def tab(rows):
    import sheet_model as M
    t=M.Tab('Team Review')
    M._register(t,'Team review and checks','Everything Dev and QA should check is here, including issues that may need the project lead. Add separate feedback and agree the next action. Final calls need a reason, reviewer and date. Dashboard opens the selected period.',COLS,rows,freeze_cols=2)
    for i,r in enumerate(rows,4):
        if r.get('evidence'):
            t.put(i,2,r['subject'],'link',link=r['evidence'])
            t.put(i,4,'Source','link',link=r['evidence'])
    t.hidden_cols=[12,13,14]
    t.dropdown(4,7,max(4,len(rows)+3),7,values=['Approved','Yes','No','Needs evidence'])
    t.readback={'kind':'review','first':4,'fields':[(i,k,role) for i,(k,_,_,role,_) in enumerate(COLS,1)],'key':'item'}
    return t


def fold(now,before,ledger,facts,board_items,who,today):
    import board
    store=facts.setdefault('team_review',{}).setdefault('rows',{})
    said=[]
    for ident,r in now['rows'].items():
        previous=before['rows'].get(ident)
        if not previous: raise ValueError('Unknown Team Review row; refresh before adding decisions')
        fields=('dev','qa','decision','why','reviewer','decided_on')
        if all((r.get(k) or '')==(previous.get(k) or '') for k in fields):continue
        rec=store.get(ident)
        if rec is None: raise ValueError('Team Review identity is missing from the private ledger')
        rec.update({k:r.get(k) for k in fields});rec['updated_at']=dt.datetime.now(dt.timezone.utc).isoformat()
        # The current sheet snapshot is the basis the person saw when deciding.
        rec['review_basis']=previous.get('basis')
        if ident.startswith('item:') and rec.get('decision') in ('Yes','No') and all(rec.get(k) for k in ('why','reviewer','decided_on')):
            item=board_items.get(rec.get('tracker_item'))
            if not item: raise ValueError('The reviewed tracker item is missing; refresh the board')
            why=rec['why']+' Dev feedback: '+str(rec.get('dev') or 'not provided')+'. QA feedback: '+str(rec.get('qa') or 'not provided')+'.'
            ledger.set(item['id'],rec['field'],rec['decision'],'human',why,
                       fingerprint=board.fingerprint(item),evidence=rec.get('evidence'))
            rec['status']='Resolved'
        said.append(f'Team Review: {ident} feedback/decision retained')
    return said


def apply_context(results,facts):
    """Reasoned team decisions become context in PMS notes, not just sheet comments."""
    store=(facts.get('team_review') or {}).get('rows') or {}
    for p in results.get('periods',[]):
        for m in p['measures']:
            decision=store.get('kpi:'+p['period']+'|'+m['name'],{})
            fields={'Rework Rate':{'reopened'},'Defect Rejection Rate':{'rejected'},'Defect Rate':{'rejected','delivery'},'Velocity':{'delivery'}}.get(m['name'],set())
            relevant=[decision]+[r for r in store.values() if r.get('period')==p['period'] and r.get('field') in fields]
            notes=[f'Team decision ({r["reviewer"]}, {r["decided_on"]}): {r["why"]}' for r in relevant if r.get('status')=='Resolved']
            if notes:
                context=' '.join(notes)
                m['context_note']=' '.join(x for x in [m.get('context_note'),context] if x)
                for key in ('note','unmeasured_note'):
                    if m.get(key):m[key]+=' '+context
