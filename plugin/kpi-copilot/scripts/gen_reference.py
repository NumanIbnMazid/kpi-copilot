#!/usr/bin/env python3
"""
Generate the exhaustive field reference from the profile schema.

Hand-written documentation of every field is documentation that is wrong within two releases.
The schema already carries a description for each one, so the complete table is generated from
it and regenerated whenever the schema changes. The narrative documents in docs/reference/
explain *why* and *when*; this one guarantees nothing is missing.

    python3 scripts/gen_reference.py --out ../../docs/reference/all-fields.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SCHEMA = HERE.parent / "schemas" / "profile.schema.json"


def _type_of(spec: dict) -> str:
    if "enum" in spec:
        return "one of: " + ", ".join(f"`{v}`" for v in spec["enum"] if v is not None)
    if "const" in spec:
        return f"`{spec['const']}`"
    t = spec.get("type")
    if isinstance(t, list):
        t = " or ".join(x for x in t if x != "null")
    if t == "array":
        item = (spec.get("items") or {})
        if "enum" in item:
            return "list, any of: " + ", ".join(f"`{v}`" for v in item["enum"])
        return "list of " + ("objects" if item.get("properties") else str(item.get("type") or "values"))
    return str(t or "")


def _rows(props: dict, prefix: str, required: list[str], out: list[dict], depth: int = 0) -> None:
    for name, spec in props.items():
        path = f"{prefix}.{name}" if prefix else name
        xw = spec.get("x-workbook") or {}
        out.append({
            "path": path,
            "label": xw.get("label", ""),
            "type": _type_of(spec),
            "default": spec.get("default"),
            "required": name in (required or []),
            "description": (spec.get("description") or xw.get("hint") or "").strip(),
            "depth": depth,
        })
        if spec.get("properties"):
            _rows(spec["properties"], path, spec.get("required") or [], out, depth + 1)
        items = (spec.get("items") or {})
        if items.get("properties"):
            _rows(items["properties"], f"{path}[]", items.get("required") or [], out, depth + 1)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate the full profile field reference.")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    sections = schema.get("properties") or {}
    top_required = schema.get("required") or []

    lines = [
        "# Every profile field",
        "",
        "Generated from `plugin/kpi-copilot/schemas/profile.schema.json` by "
        "`scripts/gen_reference.py`. Do not edit by hand — change the schema and regenerate, "
        "or the two disagree within a release.",
        "",
        "This is the exhaustive list. The documents beside it explain *why* and *when* for the "
        "parts that need judgement; come here when you want to know whether a field exists and "
        "exactly what it takes.",
        "",
        "[Documentation](../README.md) · [Configuration guide](../16-Configuration-Field-Guide.md) · "
        "[Reference index](README.md)",
        "",
        "Commands below run from the repository root using its Python environment. "
        "On Windows use `.\\.venv\\Scripts\\python.exe` instead of `.venv/bin/python`.",
        "",
        "You can also ask for one setting at a time, which is usually faster:",
        "",
        "```bash",
        ".venv/bin/python plugin/kpi-copilot/scripts/profile_tool.py explain --key workflow.delivered_when",
        "```",
        "",
        "**Required** marks a field the schema insists on. Almost nothing is required — the "
        "tool would rather report a gap than refuse to run. Schema defaults describe fields; "
        "the minimal starter profile explicitly selects review-only. A field being accepted "
        "by the schema does not guarantee every adapter implements it; read the narrative "
        "reference for runtime limits.",
        "",
    ]

    for name, spec in sections.items():
        rows: list[dict] = []
        _rows({name: spec}, "", top_required, rows)
        head = rows[0]
        lines += [f"## `{name}`", ""]
        if head["description"]:
            lines += [head["description"], ""]
        body = rows[1:]
        if not body:
            lines += [f"Type: {head['type']}.", ""]
            continue
        lines += ["| Field | Type | Default | Required | What it is |", "|---|---|---|---|---|"]
        for r in body:
            indent = "&nbsp;&nbsp;" * max(0, r["depth"] - 1)
            default = "" if r["default"] is None else f"`{r['default']}`"
            if isinstance(r["default"], bool):
                default = "`yes`" if r["default"] else "`no`"
            desc = r["description"].replace("\n", " ").replace("|", "\\|")
            lines.append(
                f"| {indent}`{r['path'].split('.', 1)[-1]}` | {r['type']} | {default} | "
                f"{'yes' if r['required'] else ''} | {desc} |"
            )
        lines.append("")

    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    total = sum(len(_rows_for(spec, n, top_required)) for n, spec in sections.items())
    print(f"Wrote {a.out} ({len(sections)} sections, {total} fields).")
    return 0


def _rows_for(spec: dict, name: str, req: list[str]) -> list[dict]:
    out: list[dict] = []
    _rows({name: spec}, "", req, out)
    return out[1:]


if __name__ == "__main__":
    raise SystemExit(main())
