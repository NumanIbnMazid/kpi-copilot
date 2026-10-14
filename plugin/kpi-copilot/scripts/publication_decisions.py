"""Record an explicit, evidence-bound publication decision.

Notes-only decisions never supply a score. A reviewed value requires a separate
explicit decision, keeps the computation visible, and expires with its evidence.
Normal note review and PMS write guards remain.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace


def basis(measure, period):
    fields = ('key', 'value', 'unit', 'numerator', 'denominator', 'threshold',
              'measurement_formula', 'gaps', 'review_items', 'counted_keys')
    data = {k: measure.get(k) for k in fields}
    data['period'] = {k: period.get(k) for k in ('name', 'start', 'end', 'as_of')}
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def apply(engine, period, measures):
    for m in measures:
        entry = (engine.manual.get(period['name']) or {}).get(m.name) or {}
        mode = entry.get('publication')
        if mode not in ('notes_only', 'reviewed_value'):
            continue
        current = basis(m.as_dict(), period)
        valid = (not period.get('upcoming') and entry.get('basis') == current
                 and all(str(entry.get(k) or '').strip() for k in ('note', 'why', 'by', 'decided_on', 'authority')))
        if mode == 'reviewed_value':
            value = entry.get('value')
            lo, hi = engine.reg_by_key.get(m.key, {}).get('range') or [0, 100]
            valid = valid and valid_reviewed_value(entry, lo, hi)
        m.publication_review = {k: entry.get(k) for k in ('why', 'by', 'decided_on', 'authority')}
        m.publication_review.update(mode=mode, basis=current, status='applied' if valid else 'stale')
        if not valid:
            m.publish_blocked = True
            continue
        from kpi_engine import _strip_links
        m.computed_value, m.computed_note = m.value, m.unmeasured_note if m.value is None else m.note
        m.value = m.pms_value = None
        m.status, m.availability = 'Not measured', 'Notes only'
        if mode == 'reviewed_value':
            m.value = float(value)
            m.pms_value = min(hi, m.value)
            m.threshold, m.direction, m.threshold_source = engine.thresholds[m.key]
            m.status = ('Measured' if m.threshold is None else
                        'Met' if (value >= m.threshold if m.direction == 'higher-is-better' else value <= m.threshold)
                        else 'Not met')
            m.availability = 'Reviewed decision'
        m.overridden, m.override_reason, m.override_by = True, entry['why'], entry['by']
        m.publish_blocked = False
        m.clamped = m.value is not None and m.pms_value != m.value
        m.note = m.summary_note = m.generated_note = m.unmeasured_note = m.unmeasured_summary = _strip_links(entry['note']).strip()
        # The reviewed note states the material scope or exception. Reviewer and
        # authorization belong in the audit, not boilerplate appended to PMS.
        m.context_note = ''
        m.note_parts = [m.note]
        engine.manual_report.append({'period': period['name'], 'kpi': m.name, 'status': 'applied',
                                     'computed': m.computed_value, 'set_to': m.value, 'note_changed': True,
                                     'pms_value': m.pms_value,
                                     'why': entry['why'], 'by': entry['by']})


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def valid_reviewed_value(entry, lo, hi):
    """Keep the actual result; an explicit ceiling decision controls only PMS."""
    value = entry.get('value')
    if not numeric(value) or value < lo:
        return False
    if value > hi or 'pms_value' in entry:
        capped = entry.get('pms_value')
        return numeric(capped) and capped == min(value, hi)
    return True


def reviewed_basis(measure, period):
    review = measure.get('publication_review') or {}
    return review['basis'] if review.get('status') == 'applied' else basis(measure, period)


def prepare(document, results, kif, questions, today, registry=None):
    """Validate every decision before changing the private manual/answer records."""
    if not document.get('authority') or not document.get('by'):
        raise ValueError('Record who made the decisions and the user instruction authorizing them.')
    periods = {p['name']: p for p in kif['periods']}
    measures = {(p['period'], m['name']): m for p in results['periods'] for m in p['measures']}
    entries, seen = [], set()
    decisions = [('notes_only', d) for d in document.get('notes_only') or []]
    decisions += [('reviewed_value', d) for d in document.get('reviewed_values') or []]
    ranges = {m['name']: m.get('range') or [0, 100] for m in (registry or {}).get('kpis', [])}
    for mode, d in decisions:
        key = (d['period'], d['kpi'])
        if key in seen or key not in measures or periods[key[0]].get('upcoming'):
            raise ValueError('Choose each current, known period/KPI once.')
        seen.add(key)
        if d.get('basis') != reviewed_basis(measures[key], periods[key[0]]):
            raise ValueError('The reviewed measurement changed; review it again.')
        if not all(str(d.get(k) or '').strip() for k in ('note', 'why')):
            raise ValueError('Publication decisions require a note and reason.')
        if mode == 'notes_only' and d.get('value') is not None:
            raise ValueError('Notes-only decisions require a note and reason, and cannot carry a numeric value.')
        if mode == 'reviewed_value':
            lo, hi = ranges.get(key[1], [0, 100])
            if not valid_reviewed_value(d, lo, hi):
                raise ValueError('A reviewed value must be finite and at least the PMS minimum; '
                                 'above the maximum, explicitly set pms_value to the ceiling '
                                 'and state the actual result and cap in the note.')
        entry = {'publication': mode, 'basis': d['basis'], 'note': d['note'],
                             'why': d['why'], 'by': document['by'], 'authority': document['authority'],
                             'decided_on': today}
        if mode == 'reviewed_value':
            entry['value'] = d['value']
            if 'pms_value' in d:
                entry['pms_value'] = d['pms_value']
        entries.append((key, entry))
    known = {q['id']: q for q in questions}
    resolutions = []
    for d in document.get('questions') or []:
        qid = d['id']
        coverage = {tuple(pair) for pair in d.get('covered_by') or []}
        if qid not in known or not qid.startswith(('judge:', 'measurement:', 'publication:')):
            raise ValueError('Only a current measurement or judgement question can receive this disposition.')
        if not coverage or not coverage <= seen or not str(d.get('decision') or '').strip():
            raise ValueError('Every question decision must name its reviewed measurements and rationale.')
        if qid.startswith('measurement:') and '|' in qid:
            expected = tuple(qid[len('measurement:'):].split('|', 1))
            if expected not in coverage:
                raise ValueError('The disposition must cover the measurement named by the question.')
        if qid.startswith('publication:'):
            expected = tuple(qid[len('publication:'):].rsplit(':', 1)[0].split('|', 1))
            if expected not in coverage:
                raise ValueError('The disposition must cover the stale publication decision.')
        if qid == 'measurement:method-alignment':
            blocked = {key for key, m in measures.items() if m.get('publish_blocked')
                       and not periods[key[0]].get('upcoming')}
            if not blocked <= seen:
                raise ValueError('Unaligned or unresolved scores must stay out of numeric publication.')
        resolutions.append(d)
    return entries, resolutions


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--profile', required=True, type=Path)
    ap.add_argument('--project', required=True)
    ap.add_argument('--decisions', required=True, type=Path)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    from kpi import Workspace, _yaml_dump
    ws = Workspace(SimpleNamespace(profile=args.profile, project=args.project))
    model = json.loads((ws.dir / 'workbook_model.json').read_text())
    nxt = json.loads((ws.dir / 'next.json').read_text())
    doc = json.loads(args.decisions.read_text())
    from kpi import input_digest
    if nxt.get('input_digest') != input_digest(ws):
        raise ValueError('Inputs changed since the run. Recompute before recording publication decisions.')
    registry = json.loads(ws.registry_path.read_text())
    entries, resolutions = prepare(doc, model['results'], model['kif'], nxt.get('questions') or [], ws.today, registry)
    print(f'Reviewed {len(entries)} publication decisions and {len(resolutions)} question dispositions.')
    if not args.apply:
        print('Dry run. No decisions recorded.')
        return
    audit = ws.dir / 'publication-decisions'
    audit.mkdir(exist_ok=True)
    digest = hashlib.sha256(args.decisions.read_bytes()).hexdigest()[:16]
    path = audit / (digest + '.json')
    if not path.exists():
        path.write_text(json.dumps({'decisions': doc, 'manual_before': ws.manual,
                                    'answers_before': ws.ledger.data.get('answers', {})}, indent=2))
    for (period, name), entry in entries:
        ws.manual.setdefault(period, {})[name] = entry
    _yaml_dump(ws.dir / 'manual.yaml', ws.manual)
    for d in resolutions:
        ws.ledger.set_answer(d['id'], d['decision'], 'ai', doc['authority'])
        ws.ledger.settle(d['id'], 'resolved', d['decision'], doc['by'])
    ws.save()
    print('Recorded decisions with their evidence basis. Run the normal pipeline before publishing.')


if __name__ == '__main__':
    main()
