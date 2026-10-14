"""Import an explicitly approved estimate CSV into the project judgement ledger.

Uses exact ticket keys, validates the entire file before applying any changes,
and retains both the source attachment and the prior ledger outside the checkout.
Only estimates change; a CSV status never supplies delivery or defect evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path
from types import SimpleNamespace

from kpi import Workspace
from sources import table


def prepare(path, board, key_column='Ticket', points_column='Story Points', notes_column='Notes'):
    columns = {'key': key_column, 'points': points_column}
    if notes_column:
        columns['notes'] = notes_column
    rows, error = table(path, {'columns': columns})
    if error:
        raise ValueError(error)
    index = {}
    for item in board.get('items', []):
        if item.get('key'):
            index.setdefault(item['key'], []).append(item)
    result, seen = [], set()
    for row in rows:
        key = str(row.get('key') or '').strip()
        if not key or key in seen:
            raise ValueError('Every estimate needs a unique, nonempty ticket key: ' + key)
        seen.add(key)
        if len(index.get(key, [])) != 1:
            raise ValueError('Estimate key must match exactly one board item: ' + key)
        try:
            points = float(row['points'])
        except (TypeError, ValueError):
            raise ValueError('Missing or invalid story points for ' + key) from None
        if not math.isfinite(points) or points < 0:
            raise ValueError('Story points must be finite and nonnegative for ' + key)
        result.append((index[key][0], points, str(row.get('notes') or '')))
    if not result:
        raise ValueError('No estimates found')
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--profile', required=True, type=Path)
    ap.add_argument('--project', required=True)
    ap.add_argument('--file', required=True, type=Path)
    ap.add_argument('--evidence', required=True)
    ap.add_argument('--why', required=True)
    ap.add_argument('--key-column', default='Ticket')
    ap.add_argument('--points-column', default='Story Points')
    ap.add_argument('--notes-column', default='Notes')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    ws = Workspace(SimpleNamespace(profile=args.profile, project=args.project))
    board = json.loads((ws.dir / 'cache' / 'board.json').read_text())
    updates = prepare(args.file, board, args.key_column, args.points_column, args.notes_column)
    print(f'Validated {len(updates)} exact ticket matches; each estimate will retain source provenance.')
    if not args.apply:
        print('Dry run; pass --apply after reviewing the source.')
        return
    digest = hashlib.sha256(args.file.read_bytes()).hexdigest()
    folder = ws.dir / 'estimate-imports' / digest[:16]
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.file, folder / 'source.csv')
    if ws.ledger.path.exists() and not (folder / 'ledger-before.json').exists():
        shutil.copy2(ws.ledger.path, folder / 'ledger-before.json')
    for item, value, notes in updates:
        why = args.why + (' Source note: ' + notes if notes else '')
        ws.ledger.set(item['id'], 'set:story_points', value, 'human', why,
                      evidence=args.evidence, key=item['key'], title=item.get('title'),
                      who=ws.profile.get('owner', {}).get('name', ''))
    ws.ledger.save()
    (folder / 'receipt.json').write_text(json.dumps({'sha256': digest, 'source': args.evidence,
        'why': args.why, 'count': len(updates), 'keys': [i['key'] for i, _, _ in updates]}, indent=2))
    print(f'Applied {len(updates)} estimates. Source and receipt: {folder}')


if __name__ == '__main__':
    main()
