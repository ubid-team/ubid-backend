from __future__ import annotations

import re
from typing import Iterable

import pandas as pd


COMMON_BUSINESS_TOKENS = {
    "m s",
    "m/s",
    "pvt",
    "private",
    "ltd",
    "limited",
    "enterprises",
    "enterprise",
    "industries",
    "industry",
    "co",
    "company",
}


def normalize_text(value: str | None) -> str:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return ""
    text = str(value).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    tokens = [token for token in text.split() if token not in COMMON_BUSINESS_TOKENS]
    return " ".join(tokens)


def collapse_text(*values: str | None) -> str:
    return " ".join(part for part in (normalize_text(value) for value in values) if part).strip()


def compact_alnum(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", normalize_text(value))


def split_pipe_values(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in str(value).split("|") if part.strip()]


def contains_any(text: str, options: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(option.lower() in lowered for option in options)
