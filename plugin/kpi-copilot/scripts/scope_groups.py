"""Resolve configured delivery groups without duplicating their tickets or estimates.

Only groups tied to an approved source row are expanded automatically. Description links
are not guessed to be children: the profile must name those members explicitly.
"""
from __future__ import annotations

import re


def resolve(classifier) -> tuple[dict, dict]:
    cfg = classifier.conv.get("grouping") or {}
    if not cfg.get("split_source_children") and not cfg.get("linked_members"):
        return {}, {}
    items = classifier.board.get("items") or []
    lookup = {str(i.get(k)): i for i in items for k in ("id", "key") if i.get(k)}
    explicit = cfg.get("linked_members") or {}
    excluded = [re.compile(p, re.I) for p in cfg.get("exclude_member_patterns") or []]
    parents, members = {}, {}
    # Match each source to its best card, never to every similar child title.
    candidates = {}
    for item in items:
        row, score = classifier.match_scope(item)
        if row and score >= .85:
            old = candidates.get(row["_idx"])
            if not old or score > old[2]:
                candidates[row["_idx"]] = item, row, score
    for parent, source, _ in candidates.values():
        keys = explicit.get(parent.get("key")) or explicit.get(parent["id"])
        if keys:
            missing = [k for k in keys if str(k) not in lookup]
            if missing:
                raise ValueError(f"Group {parent.get('key') or parent['id']} is missing configured members: "
                                 + ", ".join(missing) + ". Refresh the bounded board export.")
            children = [lookup[str(k)] for k in keys]
        elif cfg.get("split_source_children"):
            children = [i for i in items if i.get("parent") == parent["id"]]
            if max(parent.get("subtasks", 0), len(children)) < 2:
                continue
            if parent.get("subtasks", 0) > len(children):
                raise ValueError(f"Group {parent.get('key') or parent['id']} has unread subtasks. "
                                 "Enable include_subtasks and refresh the board export.")
        else:
            continue
        children = [i for i in children if i.get("kind") not in ("milestone", "approval", "section")
                    and not any(rx.search(i.get("title") or "") for rx in excluded)]
        children = list({i["id"]: i for i in children}.values())
        if len(children) < 2:
            continue
        group = {"parent": parent, "source": source, "members": children,
                 "inherit_delivery": bool(cfg.get("inherit_parent_delivery"))}
        parents[parent["id"]] = group
        for child in children:
            if child["id"] == parent["id"] or child["id"] in members:
                raise ValueError("A delivery ticket belongs to more than one configured group; resolve "
                                 "the overlap before counting it.")
            own, score = classifier.match_scope(child)
            if own and score >= .85 and own["_idx"] != source["_idx"]:
                raise ValueError("A group member has a separate approved estimate. Remove it from the "
                                 "group to avoid counting the same budget twice.")
            members[child["id"]] = group
    if set(parents) & set(members):
        raise ValueError("Nested estimated groups need an explicit non-overlapping member mapping.")
    return parents, members
