from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from app.utils.text import collapse_text, normalize_text


PUBLIC_GROUND_TRUTH_COLUMNS = {"entity_id_ground_truth", "same_entity_ground_truth"}


def ensure_columns(dataframe: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    df = dataframe.copy()
    for column in columns:
        if column not in df.columns:
            df[column] = ""
    return df


def without_ground_truth(record: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in record.items() if key not in PUBLIC_GROUND_TRUTH_COLUMNS}


def build_search_records(
    normalized_df: pd.DataFrame,
    source_master_df: pd.DataFrame,
    links_df: pd.DataFrame,
) -> pd.DataFrame:
    normalized_df = ensure_columns(
        normalized_df,
        [
            "source_record_id",
            "source_system",
            "business_name_raw",
            "address_raw",
            "district",
            "pin_code",
            "business_type",
            "business_category",
            "status",
            "last_event_date",
        ],
    )
    source_master_df = ensure_columns(
        source_master_df,
        [
            "source_record_id",
            "source_system",
            "business_name",
            "trade_name",
            "address",
            "district",
            "pin_code",
            "business_type",
            "business_category",
            "phone",
            "pan_hash",
            "gstin_hash",
            "pollution_category",
            "employee_count",
            "status",
            "last_event_date",
            "district_code",
        ],
    )
    links_df = ensure_columns(links_df, ["source_record_id", "source_system", "ubid", "link_confidence"])
    merged = normalized_df.merge(
        source_master_df,
        on=["source_record_id", "source_system"],
        how="left",
        suffixes=("_normalized", "_source"),
    )
    merged = merged.merge(links_df, on=["source_record_id", "source_system"], how="left")
    merged["business_name"] = merged["business_name_raw"].where(
        merged["business_name_raw"].ne(""),
        merged["business_name"],
    )
    merged["address"] = merged["address_raw"].where(merged["address_raw"].ne(""), merged["address"])
    merged["search_blob"] = merged.apply(
        lambda row: collapse_text(
            row.get("business_name"),
            row.get("address"),
            row.get("ubid"),
            row.get("source_record_id"),
            row.get("pan_hash"),
            row.get("gstin_hash"),
        ),
        axis=1,
    )
    merged["business_name_norm"] = merged["business_name"].map(normalize_text)
    merged["address_norm"] = merged["address"].map(normalize_text)
    merged["phone_norm"] = merged["phone"].str.replace(r"\D", "", regex=True)
    return merged
