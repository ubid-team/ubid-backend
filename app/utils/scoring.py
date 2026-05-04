from __future__ import annotations

from typing import Iterable

from rapidfuzz import fuzz


def scaled_similarity(left: str, right: str, max_score: int, scorer=fuzz.WRatio) -> int:
    if not left or not right:
        return 0
    raw = max(
        fuzz.token_set_ratio(left, right),
        scorer(left, right),
    )
    return round((raw / 100.0) * max_score)


def exact_match_score(left: str | None, right: str | None, max_score: int) -> int:
    if left and right and str(left).strip().lower() == str(right).strip().lower():
        return max_score
    return 0


def normalize_total(score: int, max_internal: int) -> int:
    if max_internal <= 0:
        return 0
    return max(0, min(100, round((score / max_internal) * 100)))


def clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, value))


def recency_bucket(months_since: int | None, buckets: Iterable[tuple[int, int]]) -> int:
    if months_since is None:
        return 0
    for ceiling, points in buckets:
        if months_since >= ceiling:
            return points
    return 0
