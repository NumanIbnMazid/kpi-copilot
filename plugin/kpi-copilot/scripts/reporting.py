"""Opt-in fixed reporting windows and explicit measurement units.

Delivery-cycle history remains intact. A calendar window gets its own dated rows;
neither cumulative estimates nor old reopen events are credited a second time.
"""
from __future__ import annotations
import copy
import datetime as dt
import math
import statistics
from productivity import enabled as productivity_enabled


def windows(config, today):
    anchor=dt.date.fromisoformat(config['anchor'])
    now=dt.date.fromisoformat(today)
    width=int(config.get('days',14))
    if width<1: raise ValueError('Reporting interval must be positive')
    start=dt.date.fromisoformat(config.get('start') or config['anchor'])
    end=dt.date.fromisoformat(config.get('end') or today)
    if end<start:
        if not config.get('end'):return []
        raise ValueError('Reporting end must not precede project start')
    result=[]
    for i in range((start-anchor).days//width,(end-anchor).days//width+1):
        a=anchor+dt.timedelta(days=i*width)
        b=a+dt.timedelta(days=width-1)
        a=max(a,start)
        if config.get('end'):b=min(b,end)
        upcoming=now<a
        result.append({'name':f'{a.isoformat()} to {b:%m-%d}', 'start':a.isoformat(),'end':b.isoformat(),
                       'as_of':min(now,b).isoformat(), 'reporting_window':True,
                       'upcoming':upcoming,
                       'notes':('Upcoming reporting window.' if upcoming else
                                'Opening partial reporting window, aligned to the configured cutoff.' if (b-a).days+1<width else
                                'Fixed reporting interval; output is counted only inside these dates.')})
    return result


def intervalize(kif, profile, today, board=None):
    config=(profile.get('periods') or {}).get('cadence')
    if not config: return kif
    out=copy.deepcopy(kif)
    if (profile.get('policy') or {}).get('measurement_review'):
        # Keep original delivery/release membership. Calendar discovery and
        # completion windows are not interchangeable quality populations.
        out['project']['measurement_source']={k:copy.deepcopy(kif[k]) for k in ('tasks','defects','periods')}
    # Milestone dates are not commitments for every calendar window.
    for field in ('client_date','commit_date'):
        out['project'][field]=None
    agreed=config.get('agreed_delivery_date')
    if agreed:
        out['project'].update(client_date=agreed,commit_date=agreed,client_check='Handover',dates_why=config.get('delivery_date_context','Agreed project delivery date.'))
    out['project']['reporting_baseline']=[copy.deepcopy(t) for t in kif.get('tasks',[]) if t.get('type')=='Task']
    out['periods']=windows(config,today)
    out['tasks'],out['defects']=[],[]
    gate=(profile.get('policy') or {}).get('velocity',{}).get('completion','delivered')
    for p in out['periods']:
        if agreed and p['start']<=agreed<=p['end']:
            p.update(client_date=agreed,commit_date=agreed,client_check='Handover')
        if p.get('upcoming'):continue
        a,b=p['start'],p['as_of']
        inside=lambda value: bool(value and a<=str(value)[:10]<=b)
        for task in kif.get('tasks',[]):
            completion=task.get('closed' if gate=='closed' else 'delivered')
            due=lambda value: bool(value and a<=str(value)[:10]<=p['end'])
            relevant=any(inside(task.get(k)) for k in ('created','closed','rework_closed','approved_on')) or any(due(task.get(k)) for k in ('client_date','commit_date')) or inside(completion)
            # Rework on earlier work belongs to the window of the event. A reviewed
            # Yes can be dated only when every candidate event was accepted.
            dates=task.get('rework_dates')
            candidates=task.get('rework_candidates') or []
            relevant=relevant or any(inside(d) for d in (dates or [])+candidates)
            if not relevant and not task.get('effort_only'): continue
            t=copy.deepcopy(task)
            t['source_period']=task['period']
            t['period']=p['name']
            t['_row']=f'{task.get("_row") or task.get("_item") or task["key"]}#window:{p["start"]}'
            t['delivered']=str(completion)[:10] if inside(completion) else None
            t['closed']=task.get('closed') if inside(task.get('closed')) else None
            # A promise belongs to its due window; an earlier delivery remains
            # evidence for that promise without earning output twice.
            t['commitment_delivered']=task.get('delivered') if task.get('delivered') and str(task['delivered'])[:10]<=b else None
            for date_field, outcome in (('client_date','met_client_date'),('commit_date','met_commitment')):
                if agreed or not due(task.get(date_field)):
                    t[date_field]=None
                    t[outcome]=None
            t['rework_candidates']=[d for d in candidates if inside(d)]
            if gate=='closed' and inside(completion) and 'delivery_eligible' in task:
                if task['delivery_eligible']=='No':
                    t['type']='Excluded'
                    t['exclude_reason']='Closed without completed implementation. '+str((task.get('basis',{}).get('delivery') or {}).get('why') or '')
                    t['delivered']=None
                elif task['delivery_eligible'] is None:
                    p.setdefault('delivery_review_pending',[]).append(task['key'])
                    t['delivered']=None
            # The window population is work whose QA close boundary was reached in
            # this interval or whose reviewed reopen occurred in it.
            if task.get('reopened')=='Yes':
                if dates is None:
                    t['reopened']=None; t['reopen_count']=None
                else:
                    n=sum(inside(d) for d in dates)
                    t['reopened']='Yes' if n else 'No';t['reopen_count']=n
            if not inside(task.get('rework_closed')) and not any(inside(d) for d in dates or []):
                t['rework_closed']=None
            if t.get('delivered') or t.get('closed') or relevant or t.get('effort_only'):
                out['tasks'].append(t)
        for defect in kif.get('defects',[]):
            if not inside(defect.get('reported_on')): continue
            d=copy.deepcopy(defect);d['source_period']=d['period'];d['period']=p['name']
            d['_row']=f'{d.get("_row") or d.get("_item") or d["key"]}#window:{p["start"]}'
            out['defects'].append(d)
        # A date on a milestone must not turn into a handover of every interval.
        handovers=[x.get('handover_date') for x in kif['periods'] if inside(x.get('handover_date'))]
        if handovers: p['handover_date']=max(handovers)
    return out


def filter_work(work,kif):
    """Judge only rows that can affect this pilot; keep source-cycle answer choices."""
    active={t.get('_item') for kind in ('tasks','defects') for t in kif.get(kind,[])}
    work['queue']=[q for q in work.get('queue',[]) if q.get('item_id') in active]
    work['questions']=[q for q in work.get('questions',[]) if not q.get('id','').startswith('handover:')]


def unit(profile, key):
    return ((profile.get('policy') or {}).get('measurement_units') or {}).get(key,'count')


def weight(row, chosen, basis='dev'):
    if chosen=='count': return 1.0
    if row.get('effort_group') and chosen!='story_points':
        raise ValueError('A group estimate cannot be divided between member outcomes; provide member estimates')
    values=[row.get('story_points')] if chosen=='story_points' else [row.get('hours_dev')]
    if chosen=='hours' and basis=='dev+qa': values.append(row.get('hours_qa'))
    if any(v is None or not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) or v<0 for v in values):
        label='story-point' if chosen=='story_points' else 'hours'
        raise ValueError(f'The {label} estimate is missing or invalid for {row.get("key") or "an item"}. Record an agreed estimate before measuring this rate.')
    return sum(values)


def pilot_target(engine, key, period):
    """Local comparison goals never imply PMS alignment or submission approval."""
    target=((engine.profile.get('policy') or {}).get('pilot_targets') or {}).get(key)
    if not target:return None, None
    why=target.get('why') or 'Provisional pilot review goal'
    if target.get('strategy')=='previous_velocity_median':
        minimum=int(target.get('minimum_periods',3));rates=[]
        velocity=(engine.profile.get('policy') or {}).get('velocity') or {}
        for old in engine.kif['periods']:
            if not old.get('reporting_window') or old.get('end','')>=period.get('start','') or old.get('as_of')!=old.get('end'):continue
            if velocity.get('effective_from') and old.get('start','')<velocity['effective_from']:continue
            den=(old.get('capacity') or {}).get('resource_days')
            if (old.get('capacity') or {}).get('provisional') or (old.get('capacity') or {}).get('missing_entry_resources'):continue
            raw=engine.velocity(old)
            if den and den>0 and raw.value is not None and not raw.gaps and not old.get('delivery_review_pending'):
                rates.append((old['end'],raw.value/den))
        rates=sorted(rates)[-minimum:]
        if len(rates)<minimum:return None,f'{why} Requires {minimum} completed, fully measured windows; {len(rates)} available.'
        return round(statistics.median(r for _,r in rates),4),f'{why} Median of the preceding {minimum} completed, fully measured windows.'
    return target.get('value'),why


def apply(engine, measure, period):
    """Change a metric's mathematical basis before its note and status are finalized."""
    m=measure;cfg=(engine.profile.get('policy') or {})
    if m.key == 'productivity_index':
        return
    if cfg.get('measurement_review'):
        import measurement_review
        if measurement_review.apply(engine,m,period):return
    agreed=((engine.profile.get('periods') or {}).get('cadence') or {}).get('agreed_delivery_date')
    if agreed and m.key in ('client_expectation','delivery_commitment') and period.get('as_of','')<agreed and not period.get('upcoming'):
        m.value=None;m.pms_value=None;m.status='Not measured';m.availability='Not due yet';m.gaps=[];m.review_items=[];m._say={}
        context=((engine.profile.get('periods') or {}).get('cadence') or {}).get('delivery_date_context')
        m.note_parts=[f'{m.name} is not scored yet because the agreed delivery date has not arrived. '
                      f'The client expects the completed project by {agreed}, and the team has committed to the same date.',
                      context or 'This date applies to the whole project, rather than a separate delivery every reporting period.',
                      'The result will show whether the project was delivered on time once the agreed date or actual delivery is reached.']
        return
    v=cfg.get('velocity') or {}
    import productivity
    active_rate=(m.key=='velocity' and not productivity.enabled(engine.profile) and v.get('mode')=='per_resource_day' and
                 (not v.get('effective_from') or period.get('start','')>=v['effective_from']))
    chosen=unit(engine.profile,m.key)
    if period.get('upcoming'):
        if active_rate:m.unit=('SP' if engine.kif['project'].get('velocity_unit')=='Story Points' else 'estimated h')+'/resource-day'
        elif m.key=='defect_rate' and chosen!='count':m.unit='defects/100 '+('story points' if chosen=='story_points' else 'estimated hours')
        m.value=m.pms_value=m.numerator=m.denominator=None
        if active_rate or chosen!='count':m.threshold=None
        m.status='Not measured';m.publish_blocked=True;m.gaps=[];m._say={}
        m.note_parts=[f'{m.name} is not measured. This reporting window has not started.',
                      f'Scheduled for {period["start"]} through {period["end"]}; no earlier work is credited to it.','']
        return
    interval_cr=m.key=='cr_rate' and period.get('reporting_window')
    if m.key=='rework_rate' and period.get('reporting_window'):
        pending=[t['key'] for t in engine.tasks_in(period['name']) if t.get('rework_candidates') and t.get('reopened') not in ('Yes','No')]
        if pending:
            why='Review the cause of return events in this interval for: '+', '.join(pending)+'.'
            m.value=None;m.pms_value=None;m.clamped=False;m.status='Not measured';m._say={}
            m.note_parts=['Rework Rate is not measured.',why];m.gaps.append(why);m.publish_blocked=True
            return
    if not active_rate and chosen=='count' and not interval_cr: return
    old_note=' '.join(x for x in m.note_parts if x)
    gaps=[]
    if interval_cr:
        m.numerator=m.denominator=None
        # Creation is not approval. Without approval timing, a carried-over addition
        # cannot be counted as a newly approved request in each reporting window.
        rows=[t for t in engine.deliverables_in(period['name']) if t.get('type')=='CR']
        baseline=engine.kif['project'].get('reporting_baseline') or []
        dated=[t for t in rows if t.get('approved_on') and period['start']<=str(t['approved_on'])[:10]<=period['as_of']]
        try:
            missing=[t for t in rows if not t.get('approved_on')]
            if missing:raise ValueError('The approval date is missing for '+', '.join(t['key']+' — '+t['title'] for t in missing[:3])+('. Other affected requests are listed in Team Review.' if len(missing)>3 else '.')+' Record the approval date so the request is counted in the right period.')
            num=sum(weight(t,chosen,engine.sources.get('hours_basis','dev')) for t in dated)
            den=sum(weight(t,chosen,engine.sources.get('hours_basis','dev')) for t in baseline if not t.get('effort_only'))
            m.numerator,m.denominator=num,den
            m.value=round(num/den*100,2) if den else None
            if not den:gaps.append('No reviewed project baseline is available.')
        except ValueError as e:
            m.value=None;gaps.append(str(e))
        m.unit='%';m._say={}
        m.note_parts=[f'CR Rate is {m.value:g}%.' if m.value is not None else 'CR Rate is not measured.',
                      'Newly approved additional requests in this interval / reviewed project baseline × 100. '+('Count basis.' if chosen=='count' else 'Effort basis: '+chosen+'.'),' '.join(gaps)]
        m.gaps.extend(gaps)
        m.status='Not measured' if m.value is None else 'Met' if m.threshold is not None and m.value<=m.threshold else 'Not met' if m.threshold is not None else 'Measured'
        lo,hi=engine.reg_by_key.get(m.key,{}).get('range') or [0,100]
        m.pms_value=max(lo,min(hi,m.value)) if m.value is not None else None;m.clamped=m.value is not None and m.pms_value!=m.value
        if chosen=='count':return
        # Continue through target alignment below, without calculating again.
        summary,detail=m.note_parts[:2]
    elif active_rate:
        cap=period.get('capacity') or {}
        den=cap.get('resource_days')
        m.unit=('SP' if engine.kif['project'].get('velocity_unit')=='Story Points' else 'estimated h')+'/resource-day'
        total=m.value
        if period.get('delivery_review_pending'):
            total=None;m.value=None;m.numerator=None
            gaps.append('Completed implementation needs review for: '+', '.join(period['delivery_review_pending'])+'.')
        if m.gaps and total is not None:
            total=None;m.value=None;m.numerator=None
            gaps.append('The completed output total is incomplete; the rate is withheld until all required estimates are recorded.')
        if total is None and not period.get('delivery_review_pending') and not engine.delivered_in(period['name']) and 'status_history' in engine.capabilities:
            total=0.0;m.numerator=0.0
        m.denominator=den
        if den is None or not isinstance(den,(float,int)) or not math.isfinite(den) or den<=0:
            gaps.append(cap.get('error') or 'Billable resource working days are unavailable or zero; verify staffing and calendar coverage.')
            m.value=None
        elif total is not None:
            m.value=round(total/den,4)
        amount='not measured' if total is None else f'{total:g}'
        summary=(f'Velocity is {m.value:g} {m.unit}: {amount} completed '
                 f'{"story points" if m.unit.startswith("SP") else "estimated hours"} / {den:g} billable resource working days.'
                 if m.value is not None else f'Velocity is not measured. Completed output: {amount}.')
        if total is None:gaps.extend(m.gaps)
        detail=(f'The denominator uses recorded project hours for {cap.get("billable_count",0)} eligible billable Dev/QA resources; ' if cap.get('basis')=='pms_timelog' else f'Capacity includes {cap.get("billable_count",0)} billable resources, after weekends, holidays and leave; ')+(
                f'{cap.get("non_billable_count",0)} non-billable members are excluded. '
                f'Completion boundary: {v.get("completion","delivered")}. '
                f'Through {period.get("as_of") or period.get("end")}.')
        if cap.get('basis')=='pms_timelog' and cap.get('missing_entry_resources'):
            who=', '.join(cap['missing_entry_resources'])
            if v.get('missing_timelogs')=='withhold' and m.value is not None:
                # Resource-days without everyone's hours understate capacity and overstate the rate.
                m.value=None
                summary=(f'Velocity is not measured. Completed output: {amount} '
                         f'{"story points" if m.unit.startswith("SP") else "estimated hours"}; the billable resource-days are incomplete.')
                gaps.append(f'Project timelogs in PMS are missing for {who}. Velocity is measured once their hours on this project are logged for this window.')
            else:
                gaps.append('Confirm missing project timelogs for: '+who+'. See Capacity for each person’s recorded hours.')
        if m.value is not None and (cap.get('provisional') or cap.get('missing_entry_resources')):m.availability='Provisional'
        if den is not None:detail+=f' Recorded effort: {den:g} '+('resource-day.' if den==1 else 'resource-days.')
        if cap.get('allocation_basis'): detail+=' '+cap['allocation_basis'].rstrip('.')+'.'
        for check in cap.get('timesheet_crosschecks',[]):
            if check.get('error'):detail+=' '+check['error']
            else:detail+=f' Supporting timesheet {check["start"]}–{check["end"]}: {check["billable_logged_hours"]:g} logged billable work hours, entries for {check["billable_members_with_entries"]} of {check["billable_members"]} billable members; allocation remains the configured assumption.'
    else:
        name=period['name'];basis=engine.sources.get('hours_basis','dev')
        w=lambda rows:sum(weight(r,chosen,basis) for r in rows)
        label='story points' if chosen=='story_points' else 'estimated hours'
        if m.key=='defect_rate':m.unit=f'defects/100 {label}'
        try:
            if m.key=='defect_rate' and period.get('delivery_review_pending'):
                raise ValueError('Completed implementation needs review before defining the effort denominator.')
            if m.key=='defect_rate':
                counted,_=engine.counted_defects(name)
                delivered=engine.delivered_in(name)
                effort=[t for t in delivered if not t.get('effort_group')]+[t for t in engine.tasks_in(name) if t.get('effort_only') and t.get('delivered')]
                # Missing delivered group budgets cannot create a smaller denominator.
                groups={t.get('_item') for t in effort if t.get('effort_only')}
                if any(t.get('effort_group') not in groups for t in delivered if t.get('effort_group')):
                    raise ValueError('Delivered group members have no completed group budget')
                num,den=len(counted),w(effort)
                m.unit=f'defects/100 {label}'
                formula=f'valid defects / completed {label} × 100'
            elif m.key in ('rejection_rate','escaped_defect_rate'):
                rows=[d for d in engine.defects_in(name) if engine._defect_kind(d)]
                if m.key=='rejection_rate': selected=[d for d in rows if d.get('rejected')=='Yes']
                else:
                    rows=[d for d in rows if d.get('rejected')!='Yes'];selected=[d for d in rows if d.get('phase')=='Post-release']
                num,den=w(selected),w(rows)
                m.unit='%';formula=f'{label} on qualifying reports / {label} on all eligible reports × 100'
            elif m.key in ('task_comprehension','client_expectation','delivery_commitment'):
                field={'task_comprehension':'understood','client_expectation':'met_client_date','delivery_commitment':'met_commitment'}[m.key]
                population=(engine.delivered_in(name) if m.key=='task_comprehension' and period.get('reporting_window') else engine.deliverables_in(name))
                rows=[t for t in population if t.get(field) in ('Yes','No')]
                num,den=w([t for t in rows if t[field]=='Yes']),w(rows)
                m.unit='%';formula=f'{label} meeting the criterion / assessed {label} × 100'
            elif m.key=='rework_rate':
                from kpi_engine import rework_population
                completed,_,assumed=rework_population(engine.kif,engine.profile,name)
                rows=[t for t in completed if t.get('reopened') in ('Yes','No')]+assumed
                num=sum(weight(t,chosen,basis)*(1 if cfg.get('measurement_review') else int(t.get('reopen_count') or 1)) for t in rows if t.get('reopened')=='Yes')
                den=w(rows);m.unit='%';formula=f'{label} of affected completed work / assessed completed {label} × 100' if cfg.get('measurement_review') else f'{label} of rework events / assessed completed {label} × 100'
            elif m.key=='cr_rate':
                rows=engine.tasks_in(name)
                base=[t for t in rows if t.get('type')=='Task']
                if not base: base=[t for t in engine.kif['tasks'] if t.get('type')=='Task']
                num,den=w([t for t in rows if t.get('type')=='CR']),w(base)
                m.unit='%';formula=f'additional-request {label} / baseline planned {label} × 100'
            else: return
            m.numerator,m.denominator=num,den
            # Retain evidence gates (e.g. client exposure is still required for escaped defects).
            m.value=round(num/den*100,2) if den>0 and m.value is not None else None
            if not den: gaps.append(f'No assessed {label} denominator; zero is not a missing estimate.')
            summary=(f'{m.name} is {m.value:g} {m.unit}. ' if m.value is not None else f'{m.name} is not measured. ')+f'Measured as {formula}; numerator {num:g}, denominator {den:g}.'
        except ValueError as e:
            m.value=None;m.numerator=m.denominator=None;summary=f'{m.name} is not measured in {label}.';gaps.append(str(e))
        detail='Measurement basis: '+label+'. '+(' '.join(m.gaps) if m.value is None else '')
    # A legacy count/total threshold has the wrong dimension. Explicit alignment is
    # required before any alternate-basis value can be submitted to PMS.
    if not cfg.get('measurement_targets_aligned'):
        m.threshold,local_why=pilot_target(engine,m.key,period)
        m.threshold_source=('Local pilot review target (PMS unchanged): '+local_why if local_why else 'Pilot target requires PMS alignment for this measurement basis')
        if local_why:detail+=' '+m.threshold_source.rstrip('.')+'.'
        m.publish_blocked=True
        gaps.append(f'Confirm the PMS target and unit for {m.name} under the pilot measurement basis.')
    if m.key=='defect_rate' and chosen!='count' and m.denominator is not None:
        detail+=' “Per 100” describes the scale; a period does not need 100 story points. Read the rate alongside its defect count and completed effort, because a small scope can produce a large swing.'
    m.status='Not measured' if m.value is None else ('Measured' if m.threshold is None else
        'Met' if (m.value>=m.threshold if m.direction=='higher-is-better' else m.value<=m.threshold) else 'Not met')
    m._say={}
    m.note_parts=[summary,detail,' '.join(gaps)]
    m.gaps.extend(gaps)
    lo,hi=engine.reg_by_key.get(m.key,{}).get('range') or [0,100]
    m.pms_value=max(lo,min(hi,m.value)) if m.value is not None else None
    m.clamped=m.value is not None and m.pms_value!=m.value
