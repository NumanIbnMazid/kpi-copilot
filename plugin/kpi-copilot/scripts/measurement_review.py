"""Reviewed pilot methods. Opt-in; ordinary PMS calculations remain unchanged.

Scope estimates measure affected work, not correction time. Report shares use
decided counts. Quality history follows the original work/release, not whichever
calendar window happens to discover it.
"""
from __future__ import annotations
import re
import productivity


def description(profile, key, velocity_unit='Story Points'):
    units=(profile.get('policy') or {}).get('measurement_units') or {}
    size={'story_points':'story points','hours':'agreed estimated hours','count':'items'}.get(units.get(key,'count'),'items')
    output='story points' if velocity_unit=='Story Points' else 'agreed estimated hours'
    logged=((profile.get('sources') or {}).get('capacity') or {}).get('basis')=='pms_timelog'
    velocity=(output.capitalize()+' per logged project day',f'Completed {output} / (billable Dev and QA project hours / hours per working day)') if logged else (
        output.capitalize()+' per billable working day',f'Completed {output} / billable Dev and QA working days after holidays, leave and project allocation')
    return {
        'velocity':(output.capitalize()+' completed in the period',f'Sum of completed {output} in the reporting period') if productivity.enabled(profile) else velocity,
        'productivity_index':velocity,
        'task_comprehension':(size.title(),f'{size.title()} of reviewed work understood without client clarification / {size} of reviewed completed work x 100'),
        'client_expectation':(size.title(),f'{size.title()} delivered by the client-expected date / {size} the client expected by that date x 100'),
        'delivery_commitment':(size.title(),f'{size.title()} delivered by the agreed commitment date / {size} committed for that date x 100'),
        'defect_rate':(f'Defects per 100 {size}; completed project work to date',f'Confirmed unique defects linked to completed project work / {size} of that completed project work x 100'),
        'escaped_defect_rate':('Defect counts; same released delivery', 'Confirmed defects found after release / confirmed defects found before and after that same release x 100'),
        'rejection_rate':('Decided bug-report counts','Reports confirmed as rejected / bug reports with a confirmed accepted or rejected decision x 100'),
        'rework_rate':(f'Affected {size}; project work reviewed to date',f'{size.title()} of reviewed work with a valid return for correction / {size} of all work reviewed after the agreed completion boundary x 100'),
        'cr_rate':(size.title(),f'{size.title()} of newly approved additional or changed work / {size} in the original agreed scope x 100'),
    }[key]


def _unique(rows):
    found={}
    for row in rows:found.setdefault(row.get('_row') or row.get('_item') or row.get('key'),row)
    return list(found.values())


def _source(engine):
    return engine.kif['project'].get('measurement_source') or engine.kif


def _sum(engine,rows,key):
    import reporting
    return sum(reporting.weight(t,reporting.unit(engine.profile,key),engine.sources.get('hours_basis','dev')) for t in _unique(rows))


def _approved_scope(engine,rows):
    """An entire approved group can use its budget once, without child allocation."""
    import reporting
    chosen=reporting.unit(engine.profile,'cr_rate');source=_source(engine).get('tasks',[])
    identity=lambda t:str(t.get('_row') or t.get('_item') or t['key']).split('#window:',1)[0]
    selected=_unique(rows);ids={identity(t) for t in selected}
    groups={t['effort_group'] for t in selected if t.get('effort_group') and
            (chosen=='hours' or (chosen=='story_points' and t.get('story_points') is None))}
    budgets=[]
    for group in groups:
        members=[t for t in source if t.get('effort_group')==group and t.get('type') in ('Task','CR','Scope')]
        if any(identity(t) not in ids for t in members):
            raise ValueError('A shared approved estimate spans reporting windows; record separate agreed member estimates.')
        budget=next((t for t in source if t.get('_item')==group and t.get('effort_only')),None)
        if not budget:raise ValueError('An approved delivery group has no shared estimate.')
        budgets.append({k:v for k,v in budget.items() if k!='effort_group'})
    return _sum(engine,[t for t in selected if t.get('effort_group') not in groups]+budgets,'cr_rate')


def _set(engine,m,num,den,detail,issue=None):
    # These methods replace the legacy population; its gaps cannot describe this one.
    m.gaps=[];m.review_items=[]
    size={'story_points':'story points','hours':'estimated hours','count':'items'}.get((engine.policy.get('measurement_units') or {}).get(m.key,'count'),'items')
    m._say={};m.numerator=num;m.denominator=den;m.unit='%' if m.key!='defect_rate' else 'defects/100 '+size
    m.value=round(num/den*100,2) if den and issue is None else None
    m.availability='No reports to assess' if not den and m.key=='rejection_rate' and issue is None else ''
    m.note_parts=[f'{m.name} is {m.value:g} {m.unit}.' if m.value is not None else f'{m.name} has no measured result.',detail]
    if issue:
        m.note_parts.append(issue);m.gaps.append(issue);m.publish_blocked=True
    m.status='Measured' if m.value is not None else 'Not measured'
    if not engine.policy.get('measurement_targets_aligned'):
        m.threshold=None;m.threshold_source='New pilot method; PMS target needs review.';m.publish_blocked=True
        m.gaps.append(f'Confirm the PMS target and measurement method for {m.name}.')
    elif m.value is not None and m.threshold is not None:
        m.status='Met' if (m.value>=m.threshold if m.direction=='higher-is-better' else m.value<=m.threshold) else 'Not met'
    lo,hi=engine.reg_by_key.get(m.key,{}).get('range') or [0,100]
    m.pms_value=m.value;m.clamped=False
    if m.value is not None and not lo<=m.value<=hi:
        m.pms_value=None;m.publish_blocked=True
        m.gaps.append(f'The calculated result is {m.value:g}; PMS accepts only {lo:g} to {hi:g}. Keep the real result in the note and align PMS before submission.')


def apply(engine,m,p):
    keys={'defect_rate','escaped_defect_rate','rejection_rate','rework_rate','cr_rate'}
    if m.key not in keys or p.get('upcoming'):return False
    source=_source(engine);asof=p.get('as_of') or p.get('end') or '9999-12-31'
    tasks=_unique(source.get('tasks',[]))
    reports=_unique([d for d in source.get('defects',[]) if d.get('reported_on') and str(d['reported_on'])[:10]<=asof])
    for row in tasks+reports:
        if row.get('key'):
            m.review_refs.append({'match':re.escape(row['key'])+r'(?!\w)',
                'items':[{k:row.get(k) for k in ('key','title','link')}]})
    try:
        if m.key=='cr_rate':
            rows=[t for t in engine.deliverables_in(p['name']) if t.get('type')=='CR']
            missing=[t['key'] for t in rows if not t.get('approved_on')]
            if missing:raise ValueError('Record the approval date for '+', '.join(missing)+', so each request enters the correct reporting window.')
            dated=[t for t in rows if p.get('start','')<=str(t.get('approved_on') or '')[:10]<=asof]
            changed=[t['key'] for t in dated if t.get('request_kind')=='Change request']
            # A replacement feature's estimate is not the added effort. Until the
            # source records a separate incremental estimate, ask instead of guessing.
            if changed:raise ValueError('Record a separate agreed incremental estimate for the changed requirements: '+', '.join(changed)+'. The replacement feature estimate cannot be used as added effort.')
            unknown=[t['key'] for t in dated if t.get('request_kind') not in ('Additional request','Change request')]
            if unknown:raise ValueError('Decide whether these requests add deliverables or change agreed requirements: '+', '.join(unknown)+'.')
            baseline=[t for t in engine.kif['project'].get('reporting_baseline',[]) if not t.get('effort_only')]
            num=_approved_scope(engine,dated);den=_sum(engine,baseline,m.key)
            m.counted_keys=[t['key'] for t in dated]
            _set(engine,m,num,den,f'{len(dated)} newly approved Additional Requests in this reporting window. Original agreed scope is retained as the baseline; approval, not implementation or closure, chooses the reporting window. Changed requirements need a separate incremental estimate.',None if den else 'No positive agreed scope baseline is available.')
            return True
        if m.key=='rejection_rate':
            rows=[d for d in engine.defects_in(p['name']) if engine._defect_kind(d)]
            decided=[d for d in rows if d.get('rejected') in ('Yes','No')]
            num=sum(d.get('rejected')=='Yes' for d in decided);den=len(decided)
            detail=f'{num} rejected '+('report' if num==1 else 'reports')+f' among {den} decided reports; {len(rows)-den} reports still need a decision. PMS rejection reasons remain in the review; duplicates are named separately rather than treated as new defects.'
            _set(engine,m,num,den,detail,'Decide the pending bug reports before treating this result as complete.' if len(decided)!=len(rows) else None)
            return True
        if m.key=='rework_rate':
            boundary=lambda t:t.get('rework_closed',t.get('closed'))
            rows=[t for t in tasks if t.get('type') in ('Task','CR','Scope') and
                  not (t.get('closed') and t.get('delivery_eligible')=='No') and
                  boundary(t) and str(boundary(t))[:10]<=asof]
            assessed=[];affected=[];events=0;pending=[]
            for t in rows:
                dates=[d for d in t.get('rework_dates') or [] if str(d)[:10]<=asof]
                candidates=[d for d in t.get('rework_candidates') or [] if str(d)[:10]<=asof]
                if t.get('reopened') not in ('Yes','No'):
                    if candidates:pending.append(t['key'])
                    continue
                if t.get('reopened')=='Yes' and t.get('rework_dates') is None:
                    pending.append(t['key']);continue
                assessed.append(t)
                if dates:affected.append(t);events+=len(dates)
            num=_sum(engine,affected,m.key);den=_sum(engine,assessed,m.key)
            m.counted_keys=[t['key'] for t in affected]
            detail=f'Project work reviewed through {asof}: {len(affected)} affected item{"s" if len(affected)!=1 else ""}, {events} valid return event{"s" if events!=1 else ""}, {len(assessed)} assessed items out of {len(rows)} eligible items. Each affected item contributes its original estimate once. This shows affected scope, not hours spent correcting it. The completion boundary is the one agreed in the workflow.'
            issue='Review the cause and dates of returns for '+', '.join(pending)+'.' if pending else 'No completed work has a reviewed return outcome.' if not den else None
            _set(engine,m,num,den,detail,issue)
            if len(assessed)!=len(rows) and m.value is not None:
                m.availability='Provisional';m.publish_blocked=True
                known={t['key'] for t in assessed}
                m.gaps.append('Confirm the return outcome for '+', '.join(t['key'] for t in rows if t['key'] not in known)+'. The provisional rate covers only the reviewed work.')
            return True
        accepted=[t for t in tasks if t.get('type') in ('Task','CR','Scope') and t.get('closed') and str(t['closed'])[:10]<=asof and t.get('delivery_eligible','Yes')=='Yes']
        eligible=[d for d in reports if engine._defect_kind(d) and d.get('pre_existing')!='Yes']
        unresolved=[d['key'] for d in eligible if d.get('rejected') not in ('Yes','No') or d.get('pre_existing') not in ('Yes','No')]
        valid=[d for d in eligible if d.get('rejected')=='No' and d.get('pre_existing')=='No']
        if m.key=='defect_rate':
            size={'story_points':'story points','hours':'agreed estimated hours','count':'items'}.get((engine.policy.get('measurement_units') or {}).get(m.key,'count'),'items')
            by_key={t['key']:t for t in accepted}
            all_keys={t['key'] for t in tasks if t.get('type') in ('Task','CR','Scope')}
            missing=[d['key'] for d in valid if not d.get('against_task') or d.get('against_task') not in all_keys]
            selected=[d for d in valid if d.get('against_task') in by_key]
            waiting=[d['key'] for d in valid if d.get('against_task') in all_keys and d.get('against_task') not in by_key]
            # A shared group budget is credited once, only after all its delivery
            # children are closed. Member estimates must not be invented.
            # A shared hours budget does not replace independently agreed points.
            grouped=[t for t in accepted if t.get('effort_group') and
                     not ((engine.policy.get('measurement_units') or {}).get(m.key)=='story_points'
                          and isinstance(t.get('story_points'),(int,float)))]
            groups={t.get('effort_group') for t in grouped}
            budgets=[]
            for group in groups:
                members=[t for t in tasks if t.get('effort_group')==group and t.get('type') in ('Task','CR','Scope')]
                if any(t['key'] not in by_key for t in members):raise ValueError('A delivery group is only partly completed; provide member estimates before measuring its completed scope.')
                budget=next((t for t in tasks if t.get('_item')==group and t.get('effort_only')),None)
                if not budget:raise ValueError('A completed delivery group has no agreed estimate.')
                budgets.append({k:v for k,v in budget.items() if k!='effort_group'})
            effort=[t for t in accepted if t.get('effort_group') not in groups]+budgets
            num=len(selected);den=_sum(engine,effort,m.key)
            m.counted_keys=[d['key'] for d in selected]
            issue='Link these confirmed defects to the implementation they belong to: '+', '.join(missing)+'.' if missing else 'Review defect validity and whether the defect was introduced by this work: '+', '.join(unresolved)+'.' if unresolved else f'No positive completed {size} scope is available.' if not den else None
            _set(engine,m,num,den,f'Completed project work through {asof}; {num} confirmed defects linked to {den:g} completed {size}. {len(waiting)} confirmed defects await completion of their linked work'+(': '+', '.join(waiting) if waiting else '')+'. Earlier-release defects and rejected reports are excluded. This is project-to-date density, not defects discovered this fortnight divided by unrelated closures.',issue)
            return True
        cycles={d.get('period') for d in reports if p.get('start','')<=str(d.get('reported_on') or '')[:10]<=asof}
        released={old['name']:old.get('handover_date') for old in source.get('periods',[]) if old.get('handover_date') and str(old['handover_date'])[:10]<=asof}
        missing=cycles-set(released)
        rows=[d for d in valid if d.get('period') in cycles]
        pending=[d['key'] for d in rows if d.get('phase') not in ('Pre-release','Post-release')]
        num=sum(d.get('phase')=='Post-release' for d in rows);den=len(rows)
        issue='Record the actual release date for '+', '.join(sorted(missing))+'. An agreed commitment is not an actual release date.' if missing else 'Review release classification for '+', '.join(pending)+'.' if pending else 'Review the undecided defect reports: '+', '.join(unresolved)+'.' if unresolved else 'No released delivery with assessed defects is available.' if not den else None
        _set(engine,m,num,den,f'{num} post-release defects among {den} confirmed defects from the same original delivery cycles, including earlier pre-release findings. Rejected and pre-existing defects are excluded. Read customer impact and observation time in the review notes.',issue)
        return True
    except ValueError as exc:
        _set(engine,m,None,None,'The chosen method needs agreed estimates and reviewed evidence.',str(exc))
        return True


def annotate(engine,m,p):
    m.measurement_method,m.measurement_formula=description(engine.profile,m.key,engine.kif['project'].get('velocity_unit','Story Points'))
    method=f'Method: {m.measurement_method}. Formula: {m.measurement_formula}.'
    if m.key not in ('velocity', 'productivity_index') or not productivity.enabled(engine.profile):
        method += ' Pilot method v2.'
    # Alignment is one project decision, not one repeated question per KPI/window.
    for attr in ('gaps','review_items'):
        setattr(m,attr,[s for s in getattr(m,attr,[]) if not s.startswith('Confirm the PMS target and')])
    # A blank caused by no reports is an explanation, not a question to answer.
    # Keep actual gaps and edited-summary conflicts as the review actions.
    m.review_items=list(dict.fromkeys(m.gaps+[s for s in m.review_items if s.startswith('The figures changed after')]))
    # Keep the method in every destination, including blanks and human overrides.
    for attr in ('summary_note','generated_note','unmeasured_summary'):
        text=getattr(m,attr,'')
        if not text.endswith(method):
            setattr(m,attr,text+' || '+method if text else method)
    # The Sheet joins its editable summary and context in this order. Use the
    # same order in engine/PMS notes, including unmeasured and manual results.
    m.note=' || '.join(filter(None,[m.summary_note,m.context_note]))
    if m.value is None:
        m.unmeasured_note=' || '.join(filter(None,[m.unmeasured_summary,m.context_note]))
