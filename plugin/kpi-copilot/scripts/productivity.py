"""Separate completed output from output per productive project day."""
from __future__ import annotations

import math


def enabled(profile):
    return bool((profile.get('policy', {}).get('productivity_index') or {}).get('enabled'))


def prepare_velocity(engine, period, m):
    """Incomplete output cannot become a complete total by dropping open calls."""
    if period.get('upcoming'):
        return
    pending = period.get('delivery_review_pending') or []
    if pending or m.gaps:
        known = m.value
        if pending:
            m.gaps.append('Confirm implementation and QA acceptance for: ' + ', '.join(pending) + '.')
        m.value = m.pms_value = None
        m.status = 'Not measured'
        m.publish_blocked = True
        m._say = {}
        m.note_parts = ['Velocity is not measured because the completed output total is not yet confirmed.',
                        f'The reviewed completed work currently accounts for {known:g} story points.' if known is not None else 'Completed work still needs agreed estimates.']


def measure(engine, period, velocity):
    cap = period.get('capacity') or {}
    total = velocity.value
    days = cap.get('resource_days')
    gaps = []
    if period.get('upcoming'):
        gaps.append('This reporting window has not started.')
    elif engine.kif['project'].get('velocity_unit') != 'Story Points':
        gaps.append('Productivity Index needs completed story points; estimated hours are a different unit.')
    elif total is None or velocity.gaps or period.get('delivery_review_pending'):
        gaps.append('The completed story-point total is incomplete; resolve the Velocity evidence first.')
    if not isinstance(days, (int, float)) or isinstance(days, bool) or not math.isfinite(days) or days <= 0:
        gaps.append(cap.get('error') or 'Productive project person-days are unavailable or zero.')
    if cap.get('missing_entry_resources'):
        gaps.append('Project hours are missing for ' + ', '.join(cap['missing_entry_resources']) + '; confirm their project effort before measuring PI.')
    value = round(total / days, 4) if not gaps else None
    m = engine._measure('productivity_index', value=value, unit='SP/person-day',
                        numerator=total, denominator=days, gaps=gaps)
    m.name = 'Productivity Index'
    if m.pms_id is None:
        m.threshold = None
        m.threshold_source = 'Separate KPI; PMS field not yet configured'
        m.status = 'Measured' if value is not None else 'Not measured'
        m.pms_value = None
        m.clamped = False
    m.publish_blocked = bool(gaps)
    summary = (f'Productivity Index (PI) is {value:g} SP/person-day: {total:g} completed story points / {days:g} productive project person-days.'
               if value is not None else 'Productivity Index (PI) is not measured. ' + (
                   'This reporting window has not started.' if period.get('upcoming') else
                   'Completed output and productive project effort must both be confirmed for the same period.'))
    if cap.get('basis') == 'pms_timelog':
        count = cap.get('billable_count')
        resources = f'the {count} eligible billable Dev/QA resources' if isinstance(count, int) else 'eligible billable Dev/QA resources'
        basis = (f'Project hours recorded by {resources} are divided by '
                 f'{cap.get("hours_per_day", 8):g} hours per person-day. '
                 'Holidays and leave are not deducted again from actual work hours.')
    else:
        basis = 'Productive project days exclude holidays and leave and apply the recorded project allocation.'
    detail = basis + ' Shared resources contribute only their recorded project effort.'
    m.note_parts = [summary, detail]
    m._say = {}
    if cap.get('provisional') or (period.get('as_of') and period.get('as_of') < period.get('end', '')):
        m.availability = 'Provisional' if value is not None else ''
    return m


def add_pms_fallback(measures):
    """Use one reviewed note until the registry supplies a real PI field ID."""
    pi = next((m for m in measures if m.key == 'productivity_index'), None)
    velocity = next((m for m in measures if m.key == 'velocity'), None)
    if not pi or not velocity or pi.pms_id is not None:
        return
    text = 'Temporary PMS companion KPI: ' + (pi.note if pi.value is not None else pi.unmeasured_note)
    for field in ('summary_note', 'generated_note'):
        current = getattr(velocity, field)
        setattr(velocity, field, ' || '.join(x for x in (current, text) if x))
    velocity.note = ' || '.join(x for x in (velocity.summary_note, velocity.context_note) if x)
    if velocity.value is None:
        velocity.unmeasured_summary = ' || '.join(x for x in (velocity.unmeasured_summary, text) if x)
        velocity.unmeasured_note = ' || '.join(x for x in (velocity.unmeasured_summary, velocity.context_note) if x)
