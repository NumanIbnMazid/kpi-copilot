"""Read back the published summary and check its calculated values and notes."""
from __future__ import annotations

import math
from urllib.parse import quote

import google_api as G
from pms_push import _clean


def _note_clean(value):
    # Sentence versus paragraph styling may add terminal full stops to each
    # section. Preserve every word, internal punctuation and numeric decimal.
    return ' || '.join(p.strip().rstrip('.') for p in _clean(value).split(' || '))


def compare(rows: list[list], results: dict, with_units=False) -> dict:
    expected = {(p['period'], m['name']): m for p in results.get('periods') or []
                for m in p.get('measures') or []}
    seen, errors = set(), []
    for row in rows:
        if with_units:row=list(row)+['']*max(0,20-len(row))
        row = list(row) + [''] * max(0, 15 - len(row))
        identity = (row[0], row[2])
        if not row[0] or not row[2]:
            continue
        if identity not in expected:
            # Previous periods may be intentionally preserved in the same workbook.
            continue
        if identity in seen:
            errors.append({'period': row[0], 'kpi': row[2], 'field': 'duplicate row'})
        seen.add(identity)
        m = expected[identity]
        if with_units and str(row[19])!=str(m.get('unit') or ''):
            errors.append({'period':row[0],'kpi':row[2],'field':'unit','expected':m.get('unit'),'actual':row[19]})
        actual = None if row[6] in ('', None) else row[6]
        wanted = m.get('value')
        equal = actual is None and wanted is None
        if actual is not None and wanted is not None:
            try:
                equal = math.isclose(float(actual), float(wanted), abs_tol=0.005)
            except (ValueError, TypeError):
                equal = False
        if not equal:
            errors.append({'period': row[0], 'kpi': row[2], 'field': 'value', 'expected': wanted, 'actual': actual})
        wanted_note = m.get('unmeasured_note') if wanted is None else m.get('note')
        wanted_note = wanted_note or m.get('note') or ''
        if _note_clean(str(row[13] or '')) != _note_clean(wanted_note):
            errors.append({'period': row[0], 'kpi': row[2], 'field': 'note',
                           'expected': _clean(wanted_note), 'actual': _clean(str(row[13] or ''))})
    for period, name in expected.keys() - seen:
        errors.append({'period': period, 'kpi': name, 'field': 'missing row'})
    return {'checked': len(seen), 'errors': errors, 'verified': not errors}


def google(fid: str, results: dict) -> dict:
    data = G.Session().call('GET', f'{G.SHEETS}/{fid}/values/' + quote("'KPI Summary'!A4:T", safe=''),
                            params={'valueRenderOption': 'UNFORMATTED_VALUE'})
    return compare(data.get('values') or [], results,with_units=True)
