"""Read project staffing and calendar through the normal PMS transport.

Only normalized availability is retained. Leave reasons are never needed for KPIs.
"""
from __future__ import annotations

import argparse
import json
import os
import math
import datetime as dt
from pathlib import Path

from pms_push import _api


def read(base, project_id, start, end):
    token = os.environ.get('PMS_TOKEN')
    return {
        'members': _api(base, f'/api/projects/{project_id}/members?memberType=current', token=token),
        'calendar': _api(base, f'/api/projects/{project_id}/calendar?startDate={start}&endDate={end}', token=token),
        'history': _api(base, f'/api/projects/{project_id}/histories?', token=token),
    }


def read_timesheets(base, project_id, start, end):
    """PMS accepts a date range but returns only the week containing its end date."""
    first,last=day(start),day(end);groups=[]
    while first<=last:
        cutoff=min(last,first+dt.timedelta(days=(5-first.weekday())%7))
        response=_read_timesheet_week(base,project_id,first.isoformat(),cutoff.isoformat())
        groups.extend(g for g in response['data'] if g.get('entryDate') and first<=day(g['entryDate'])<=cutoff)
        first=cutoff+dt.timedelta(days=1)
    observed=[day(g['entryDate']) for g in groups]
    expected=set(days(day(start),day(end)))
    if set(observed)!=expected or len(observed)!=len(expected):
        raise ValueError('PMS worklogs do not cover every requested date exactly once')
    return {'data':groups}


def _read_timesheet_week(base, project_id, start, end):
    """Read every explicit page through the configured PMS transport."""
    result=None
    for page in range(1,1001):
        response=_api(base, f'/api/timesheets?startDate={start}&endDate={end}&pageNumber={page}&includeFilters=true&projectId={project_id}', token=os.environ.get('PMS_TOKEN'))
        if not isinstance(response.get('data'),list):raise ValueError('PMS worklogs are unavailable')
        if result is None:result={**response,'data':[]}
        result['data'].extend(response['data'])
        pages=response.get('totalPages') or (response.get('pagination') or {}).get('totalPages')
        if pages is None:
            # The API returns all date groups unless it explicitly supplies pagination.
            if response.get('hasNextPage'):continue
            return result
        if page>=int(pages):return result
    raise ValueError('PMS worklog pagination did not finish')


def normalize_timelogs(raw, logs, start, end, today, hours_per_day=8, entry_lag_days=7, eligible_ids=None):
    """Actual project effort, with no assumed full allocation or second leave deduction."""
    hours_per_day=float(hours_per_day)
    if not math.isfinite(hours_per_day) or hours_per_day<=0:raise ValueError('Hours per day must be positive')
    members=raw['members']['data'];known={str(m['user']['id']):m for m in members}
    minutes={uid:0 for uid in known}
    for group in logs.get('data') or []:
        stamp=group.get('entryDate') or group.get('date') or group.get('workDate')
        if not stamp:raise ValueError('A worklog group has no date')
        if not day(start)<=day(stamp)<=day(end):continue
        for w in group.get('worklogs') or []:
            uid=str(w['user']['id']);n=w.get('timeSpentInMinute')
            if not isinstance(n,(int,float)) or not math.isfinite(n) or n<0:raise ValueError('Invalid worklog duration')
            if uid not in known:raise ValueError('A logged resource is absent from staffing; review historical billability')
            minutes[uid]+=n
    rows=[]
    for uid,m in known.items():
        billable=m.get('isBillable') is True
        eligible=billable and (eligible_ids is None or uid in {str(i) for i in eligible_ids})
        h=minutes[uid]/60
        reason=('Recorded billable Dev/QA project hours.' if eligible and h else
                'No project hours recorded; confirm whether entries are missing.' if eligible else
                'Non-billable membership.' if not billable else 'Outside the configured Dev/QA resource list.')
        rows.append({'resource_id':uid,'resource':m['user']['name'],'logged_hours':round(h,4),
                     'net_days':round(h/hours_per_day,4) if eligible else 0,
                     'included':'Yes' if eligible and h else 'No','reason':reason,'eligible':eligible})
    provisional=day(today)<day(end)+dt.timedelta(days=entry_lag_days)
    return {'start':start,'end':end,'basis':'pms_timelog','hours_per_day':hours_per_day,
            'resource_days':round(sum(minutes[r['resource_id']]/60/hours_per_day for r in rows if r['eligible']),4),
            'resources':rows,'billable_count':sum(r['eligible'] for r in rows),
            'non_billable_count':sum(m.get('isBillable') is False for m in members),
            'provisional':provisional,'missing_entry_resources':[r['resource'] for r in rows if r['eligible'] and not r['logged_hours']],
            'allocation_basis':f'Recorded billable Dev/QA hours for this project divided by {hours_per_day:g} hours per day. Shared resources contribute only their recorded project hours. Missing entries need review; they do not prove that no work occurred.'+(' Entries may still arrive next week; this result is provisional.' if provisional else '')}


def timesheet_summary(raw, members, start, end, today, entry_lag_days=7):
    """Describe observed worklogs. Missing entries can never reduce capacity."""
    billable={str(m['user']['id']) for m in members if m.get('isBillable') is True}
    work=0;other=0;logged=set()
    for d in raw.get('data') or []:
        for w in d.get('worklogs') or []:
            uid=str(w['user']['id']);minutes=w['timeSpentInMinute']
            if not isinstance(minutes,(int,float)) or minutes<0:raise ValueError('Invalid timesheet worklog duration')
            if uid in billable:work+=minutes;logged.add(uid)
            else:other+=minutes
    return {'start':start,'end':end,'billable_logged_hours':round(work/60,2),
            'non_billable_logged_hours':round(other/60,2),'billable_members_with_entries':len(logged),
            'billable_members':len(billable),'entry_delay_possible':day(today)<day(end)+dt.timedelta(days=entry_lag_days),
            'coverage':'Optional worklogs only; entries may be late or absent. These totals do not establish allocation, attendance, utilization, or capacity.'}


def previous_weeks(today,count=2):
    current=day(today)
    sunday=current-dt.timedelta(days=(current.weekday()+1)%7)
    return [((sunday-dt.timedelta(days=7*(i+1))).isoformat(),(sunday-dt.timedelta(days=7*i+1)).isoformat()) for i in range(count)]


def day(value):
    return dt.date.fromisoformat(str(value)[:10])


def days(start, end):
    for n in range((end-start).days+1):
        yield start + dt.timedelta(days=n)


def normalize(raw, start, end, weekdays, allocations=None):
    """Net billable resource-days. Overlapping leave/holidays are deducted once.

    PMS membership establishes billability, not project allocation. An explicit
    allocation map can reduce a shared resource's contribution; never infer it.
    """
    members = raw['members']['data']
    calendar = raw['calendar']['data']
    if not isinstance(members, list) or not all(k in calendar for k in ('holidays','leaves','events')):
        raise ValueError('PMS capacity response is incomplete')
    a,b = day(start),day(end)
    holidays = set()
    for h in calendar['holidays']:
        ha,hb = day(h.get('startDate') or h.get('date')),day(h.get('endDate') or h.get('date') or h.get('startDate'))
        holidays.update(days(ha,hb))
    leave = {}
    halves = {'first_half','second_half','morning','afternoon'}
    for r in calendar['leaves']:
        ra,rb = day(r['startDate']),day(r['endDate'])
        for d in days(max(a,ra),min(b,rb)):
            portions = [r[k] for k,edge in [('startDatePortion',ra),('endDatePortion',rb)] if d==edge]
            if not portions: portions=['all_day']
            if any(p not in halves|{'all_day'} for p in portions):
                raise ValueError('Unknown PMS leave portion; map it before calculating capacity')
            mask = 3 if 'all_day' in portions else sum({1 if p in ('first_half','morning') else 2 for p in portions})
            key = (str(r['userId']),d)
            leave[key] = leave.get(key,0) | mask
    rows=[]
    known={str(m['user']['id']) for m in members if m.get('user')}
    history=(raw.get('history') or {}).get('data')
    if not isinstance(history,list):raise ValueError('Staffing history is unavailable; current membership cannot establish historical capacity')
    for h in history:
        if not h.get('date'):continue
        if str(h['userId']) not in known and day(h['date'])<=b:
            raise ValueError('A historical resource is absent from current staffing; supply a reviewed historical capacity source')
    for m in members:
        if m.get('isBillable') is not True: continue
        uid=str(m['user']['id'])
        if not m.get('joinedOn'):
            raise ValueError('A billable member has no joining date')
        if not any(str(h['userId'])==uid and h.get('isJoined') is True and h.get('date') and day(h['date'])==day(m['joinedOn']) for h in history):
            raise ValueError('Joining date is not corroborated by staffing history')
        ma,mb=max(a,day(m['joinedOn'])),min(b,day(m['leftOn'])) if m.get('leftOn') else b
        fraction=float((allocations or {}).get(uid,1))
        if not math.isfinite(fraction) or not 0<=fraction<=1:
            raise ValueError('Resource allocation must be between zero and one')
        work=[d for d in days(ma,mb) if d.weekday() in weekdays]
        holiday=sum(d in holidays for d in work)
        pto=sum((1 if leave.get((uid,d))==3 else .5 if leave.get((uid,d)) else 0)
                for d in work if d not in holidays)
        rows.append({'resource_id':uid,'resource':m['user']['name'], 'gross_days':len(work),
                     'holiday_days':holiday,'leave_days':pto,'allocation':fraction,
                     'net_days':round((len(work)-holiday-pto)*fraction,4)})
    return {'start':start,'end':end,'resource_days':round(sum(r['net_days'] for r in rows),4),
            'resources':rows,'billable_count':len(rows),
            'non_billable_count':sum(m.get('isBillable') is False for m in members),
            'allocation_basis':'Configured resource allocation; where no allocation is recorded, the authorized fallback is full allocation. Timesheets may be entered the following week or not maintained at all; blanks do not mean no work. Completed-week hours can corroborate work but do not establish project allocation or complete attendance.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', required=True)
    p.add_argument('--project-id', type=int, required=True)
    p.add_argument('--start', required=True)
    p.add_argument('--end', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--timesheets-only', action='store_true')
    p.add_argument('--summarize-timesheets', type=Path, help='Inspect a saved API response against a saved capacity contract; no network')
    p.add_argument('--members-file', type=Path)
    p.add_argument('--today', default=dt.date.today().isoformat())
    a = p.parse_args()
    if a.summarize_timesheets:
        data=timesheet_summary(json.loads(a.summarize_timesheets.read_text()),json.loads(a.members_file.read_text())['members']['data'],a.start,a.end,a.today)
        a.out.write_text(json.dumps(data,indent=2));print(json.dumps(data,indent=2));return
    data = read_timesheets(a.base, a.project_id, a.start, a.end) if a.timesheets_only else read(a.base, a.project_id, a.start, a.end)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(data))
    a.out.chmod(0o600)
    # Inspection shows the contract, not private calendar reasons or identities.
    def shape(x):
        if isinstance(x, list):
            return {'count': len(x), 'first': shape(x[0]) if x else None}
        if isinstance(x, dict):
            return {k: shape(v) for k,v in x.items()}
        return type(x).__name__
    print(json.dumps({k: shape(v) for k,v in data.items()}, indent=2))


if __name__ == '__main__':
    main()
