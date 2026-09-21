"""Keep published results and actionable review questions in their respective fields."""
from __future__ import annotations

import hashlib
import json
import re

# These are data-collection/review statements, not descriptions of delivery outcomes.
# Normal exclusions (existing defects, rejected reports, future due dates) still belong
# with the result because they explain the KPI's meaning.
REVIEW_LANGUAGE = re.compile(
    r"\b(?:cannot|can't|could not|couldn't)\s+(?:be\s+)?(?:measur\w*|assess\w*|judg\w*|verif\w*|confirm\w*)"
    r"|\bnot (?:measured|assessed|available|established)\b"
    r"|\b(?:no|missing|insufficient|unavailable|incomplete)\s+(?:individual\s+)?(?:evidence|history|data|record\w*|date\w*|estimate\w*)"
    r"|\b(?:history|histories|evidence|data|cause|handover|delivery|work|commitment|date)\b[^.!?]{0,110}\b(?:unavailable|missing|not available|not recorded|has not been recorded|does not establish|cannot establish)\b"
    r"|\b(?:nothing|no planned scope) to (?:measure|judge)\b"
    r"|\b(?:not enough|with enough) evidence\b"
    r"|\b(?:lack\w*|absence of)\b[^.!?]{0,65}\b(?:history|evidence|estimates?|records?)\b"
    r"|\b(?:cannot|can't)\s+yet\s+(?:be\s+)?(?:confirm\w*|measur\w*|assess\w*)\b"
    r"|\b(?:record does not|does not) establish\b"
    r"|\b(?:could not|cannot) check\b"
    r"|\bno\b[^.!?]{0,65}\bis recorded\b"
    r"|\b(?:no|not all)\b[^.!?]{0,70}\brecords whether\b",
    re.I,
)


def split(text: str) -> tuple[list[str], list[str]]:
    published, review = [], []
    for paragraph in re.split(r"\s*\|\|\s*", text or ""):
        good = []
        for part in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", paragraph):
            part = part.strip()
            if part:
                (review if REVIEW_LANGUAGE.search(part) else good).append(part)
        if good:
            published.append(" ".join(good))
    return published, review


def basis(measure: dict) -> str:
    return hashlib.sha256(json.dumps({k: measure.get(k) for k in
        ("value", "numerator", "denominator", "generated_note", "threshold", "status")},
        sort_keys=True, default=str).encode()).hexdigest()


def question(period: str, kpi: str, detail: str) -> dict:
    fingerprint = hashlib.sha256(detail.encode()).hexdigest()[:12]
    return {"id": f"review:{period}|{kpi}:{fingerprint}", "about": f"{period} · {kpi}",
            "question": "Review this measurement: " + detail, "blocking": False}
