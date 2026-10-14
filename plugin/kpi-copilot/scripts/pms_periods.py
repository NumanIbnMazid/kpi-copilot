"""Retire explicitly named PMS reporting periods, with a backup and identity checks.

This does not change source milestones or calculation inputs. Prepare a private plan
first; apply it only after the user authorizes removal of its exact periods.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from pms_push import _api
from profile_lib import load as load_profile, resolve as resolve_profile


def period_list(raw, project_id):
    rows = raw if isinstance(raw, list) else raw.get('data')
    if not isinstance(rows, list) or any(str(r.get('projectId')) != str(project_id) for r in rows):
        raise ValueError('PMS returned an invalid project period list.')
    if len({r.get('id') for r in rows}) != len(rows):
        raise ValueError('PMS returned duplicate period identities.')
    return rows


def select(rows, names, keep):
    if not names or len(set(names)) != len(names) or set(names) & set(keep):
        raise ValueError('Name each obsolete period once; retained periods cannot be removed.')
    if not keep or any(sum(r.get('name') == n for r in rows) != 1 for n in keep):
        raise ValueError('Every replacement reporting period must already exist exactly once.')
    chosen = []
    for name in names:
        matches = [r for r in rows if r.get('name') == name]
        if len(matches) != 1:
            raise ValueError('Every obsolete period must match exactly one current period.')
        chosen.append(matches[0])
    return chosen


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--profile', required=True, type=Path)
    ap.add_argument('--project', required=True)
    ap.add_argument('--plan', required=True, type=Path)
    ap.add_argument('--retire', action='append', default=[])
    ap.add_argument('--keep', action='append', default=[])
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    profile, project = resolve_profile(load_profile(args.profile), args.project)
    pid = project['pms_project_id']
    base = profile['organization']['pms_base_url'].rstrip('/')
    token = os.environ.get('PMS_TOKEN')
    endpoint = f'/api/projects/{pid}/periods'
    call = lambda path, **kw: _api(base, path, token=token, **kw)
    rows = period_list(call(endpoint), pid)
    if not args.apply:
        chosen = select(rows, args.retire, args.keep)
        details = []
        for row in chosen:
            raw = call(endpoint + '/' + str(row['id']))
            detail = raw.get('data', raw)
            if detail.get('id') != row['id'] or detail.get('name') != row['name'] or not detail.get('updatedAt'):
                raise ValueError('PMS period identity or concurrency timestamp is missing.')
            details.append(detail)
        plan = {'pms': base, 'project_id': pid, 'prepared_at': datetime.now(timezone.utc).isoformat(),
                'keep': args.keep, 'retire': details, 'period_list_before': rows}
        args.plan.parent.mkdir(parents=True, exist_ok=True)
        with args.plan.open('x') as f:
            json.dump(plan, f, indent=2)
        args.plan.chmod(0o600)
        print(f'Backed up {len(details)} obsolete periods to {args.plan}. No PMS data changed.')
        for row in details:
            print(f"  {row['id']}: {row['name']}")
        return
    plan = json.loads(args.plan.read_text())
    if plan.get('pms') != base or plan.get('project_id') != pid:
        raise ValueError('The plan belongs to a different PMS project.')
    chosen = select(rows, [r['name'] for r in plan['retire']], plan['keep'])
    if [(r['id'], r['name']) for r in chosen] != [(r['id'], r['name']) for r in plan['retire']]:
        raise ValueError('The period identities changed after the backup.')
    # Check every candidate before the first destructive action.
    for saved in plan['retire']:
        raw = call(endpoint + '/' + str(saved['id']))
        if raw.get('data', raw) != saved:
            raise ValueError('A period changed after the backup; prepare and review a new plan.')
    receipt = {'project_id': pid, 'results': []}
    receipt_path = args.plan.with_suffix('.receipt.json')
    try:
        for saved in plan['retire']:
            call(endpoint + '/' + str(saved['id']), method='DELETE',
                 extra={'Last-Modified': saved['updatedAt']})
            remaining = period_list(call(endpoint), pid)
            if any(r['id'] == saved['id'] for r in remaining):
                raise ValueError('PMS still contains the removed period; stopping.')
            if not all(any(r['name'] == n for r in remaining) for n in plan['keep']):
                raise ValueError('A retained period is missing; stopping.')
            receipt['results'].append({'id': saved['id'], 'name': saved['name'], 'result': 'removed and verified'})
            print(f"Removed {saved['name']}; replacement periods retained.")
    finally:
        receipt_path.write_text(json.dumps(receipt, indent=2))
        receipt_path.chmod(0o600)


if __name__ == '__main__':
    main()
