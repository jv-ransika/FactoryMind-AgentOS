from __future__ import annotations

import re


def keywords(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9_]+", value.lower()) if len(token) > 2}


def keyword_overlap(query: str, values: list[str]) -> tuple[list[str], float]:
    query_terms = keywords(query)
    if not query_terms:
        return [], 0.0

    candidate_terms: set[str] = set()
    for value in values:
        candidate_terms.update(keywords(value))

    matched = sorted(query_terms.intersection(candidate_terms))
    return matched, float(len(matched))
