from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from rapidfuzz import fuzz

from app.core.config import Settings
from app.core.errors import DataUnavailableError
from app.data.loader import DataLoader, LoadedDataset
from app.data.normalizer import build_search_records, ensure_columns, without_ground_truth
from app.models.business import BusinessSearchResult, DataSourceSummary
from app.utils.text import normalize_text, split_pipe_values

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ConfirmationRecord:
    timestamp: datetime
    action: str
    ubid: str | None
    business_record: dict[str, Any]


class DataRepository:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.loader = DataLoader(settings)
        self.dataframes: dict[str, pd.DataFrame] = {}
        self.loaded_sources: list[LoadedDataset] = []
        self.search_records = pd.DataFrame()
        self.data_root = settings.data_dir
        self.confirmations: list[ConfirmationRecord] = []
        self.match_status: dict[str, str] = {}

    def load(self) -> None:
        self.dataframes, self.loaded_sources, self.data_root = self.loader.load()
        self._refresh_indexes()

    def reload(self) -> None:
        self.load()

    @property
    def data_loaded(self) -> bool:
        return bool(self.loaded_sources)

    def require_data(self) -> None:
        if not self.data_loaded:
            raise DataUnavailableError(
                f"No CSV data is loaded. Place the synthetic dataset under {self.settings.data_dir} and call /api/data/reload."
            )

    def source_summaries(self) -> list[DataSourceSummary]:
        return [
            DataSourceSummary(
                logical_name=item.logical_name,
                file_name=item.path.name,
                relative_path=str(item.path.relative_to(self.data_root)),
                row_count=len(item.dataframe.index),
                columns=[str(column) for column in item.dataframe.columns.tolist()],
                last_loaded_at=item.loaded_at,
            )
            for item in self.loaded_sources
        ]

    def get_dataframe(self, logical_name: str) -> pd.DataFrame:
        return self.dataframes.get(logical_name, pd.DataFrame()).copy()

    def search_businesses(self, query: str, limit: int = 20) -> list[BusinessSearchResult]:
        self.require_data()
        if self.search_records.empty:
            return []
        query_norm = normalize_text(query)
        scored: list[BusinessSearchResult] = []
        for _, row in self.search_records.iterrows():
            score = max(
                fuzz.WRatio(query_norm, row.get("search_blob", "")),
                fuzz.token_set_ratio(query_norm, row.get("business_name_norm", "")),
                fuzz.partial_ratio(query_norm, row.get("address_norm", "")),
            )
            if score < 35:
                continue
            scored.append(
                BusinessSearchResult(
                    ubid=row.get("ubid") or None,
                    source_record_id=row.get("source_record_id", ""),
                    source=row.get("source_system", ""),
                    business_name=row.get("business_name", ""),
                    address=row.get("address") or None,
                    district=row.get("district") or None,
                    pin_code=row.get("pin_code") or None,
                    business_type=row.get("business_type") or None,
                    business_category=row.get("business_category") or None,
                    score=round(score),
                    raw=without_ground_truth(row.to_dict()),
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:limit]

    def record_confirmation(self, action: str, ubid: str | None, business_record: dict[str, Any]) -> None:
        self.confirmations.append(
            ConfirmationRecord(
                timestamp=datetime.now(timezone.utc),
                action=action,
                ubid=ubid,
                business_record=business_record,
            )
        )

    def add_registry_entry(self, ubid: str, business_record: dict[str, Any], source_count: int = 1) -> None:
        registry_df = ensure_columns(
            self.get_dataframe("ubid_registry"),
            [
                "ubid",
                "canonical_business_name",
                "canonical_address",
                "district",
                "pin_code",
                "business_type",
                "business_category",
                "activity_status",
                "confidence",
                "source_record_count",
                "linked_departments",
                "created_at",
                "last_activity_date",
                "audit_policy",
            ],
        )
        registry_df.loc[len(registry_df)] = {
            "ubid": ubid,
            "canonical_business_name": business_record.get("business_name", ""),
            "canonical_address": business_record.get("address", ""),
            "district": business_record.get("district", ""),
            "pin_code": business_record.get("pin_code", ""),
            "business_type": business_record.get("business_type", ""),
            "business_category": business_record.get("business_category", ""),
            "activity_status": "ACTIVE",
            "confidence": "100",
            "source_record_count": str(source_count),
            "linked_departments": business_record.get("source", "USER_INTAKE"),
            "created_at": datetime.now(timezone.utc).date().isoformat(),
            "last_activity_date": datetime.now(timezone.utc).date().isoformat(),
            "audit_policy": "append_only; deterministic MVP",
        }
        self.dataframes["ubid_registry"] = registry_df
        self._refresh_indexes()

    def add_source_link(self, ubid: str, business_record: dict[str, Any]) -> None:
        links_df = ensure_columns(
            self.get_dataframe("source_to_ubid_links"),
            ["ubid", "source_system", "source_record_id", "link_type", "link_confidence", "linked_at"],
        )
        source_record_id = business_record.get("source_record_id") or f"USER-{len(links_df.index) + 1:06d}"
        links_df.loc[len(links_df)] = {
            "ubid": ubid,
            "source_system": business_record.get("source", "USER_INTAKE"),
            "source_record_id": source_record_id,
            "link_type": "USER_CONFIRMED",
            "link_confidence": "100",
            "linked_at": datetime.now(timezone.utc).date().isoformat(),
        }
        self.dataframes["source_to_ubid_links"] = links_df
        self._refresh_indexes()

    def district_code_for(self, district: str) -> str:
        source_df = self.get_dataframe("source_records_all_departments")
        if not source_df.empty and {"district", "district_code"}.issubset(source_df.columns):
            matches = source_df[source_df["district"].str.lower() == district.lower()]
            if not matches.empty and matches["district_code"].iloc[0]:
                return str(matches["district_code"].iloc[0]).upper()
        tokens = [token[:2].upper() for token in district.split() if token]
        return "".join(tokens)[:4] or "UNKN"

    def linked_departments_for_ubid(self, ubid: str) -> list[str]:
        links_df = self.get_dataframe("source_to_ubid_links")
        if links_df.empty:
            return []
        subset = links_df[links_df["ubid"] == ubid]
        return sorted({value for value in subset["source_system"].tolist() if value})

    def source_diversity_score(self, ubid: str | None) -> int:
        if not ubid:
            return 0
        distinct_sources = self.linked_departments_for_ubid(ubid)
        return min(5, len(distinct_sources))

    def registry_count(self) -> int:
        return len(self.get_dataframe("ubid_registry").index)

    def find_registry_row(self, ubid: str) -> dict[str, Any] | None:
        registry_df = self.get_dataframe("ubid_registry")
        if registry_df.empty:
            return None
        subset = registry_df[registry_df["ubid"] == ubid]
        if subset.empty:
            return None
        return without_ground_truth(subset.iloc[0].to_dict())

    def find_dashboard_row(self, ubid: str) -> dict[str, Any] | None:
        dashboard_df = self.get_dataframe("dashboard_mock")
        if dashboard_df.empty:
            return None
        subset = dashboard_df[dashboard_df["ubid"] == ubid]
        if subset.empty:
            return None
        return without_ground_truth(subset.iloc[0].to_dict())

    def find_risk_row(self, ubid: str) -> dict[str, Any] | None:
        risk_df = self.get_dataframe("risk_assessment")
        if risk_df.empty:
            return None
        subset = risk_df[risk_df["ubid"] == ubid]
        if subset.empty:
            return None
        return without_ground_truth(subset.iloc[0].to_dict())

    def find_events(self, ubid: str) -> list[dict[str, Any]]:
        events_df = self.get_dataframe("compliance_events")
        if events_df.empty:
            return []
        subset = events_df[events_df["ubid"] == ubid].sort_values("event_date", ascending=False)
        return [without_ground_truth(row) for row in subset.to_dict(orient="records")]

    def find_links(self, ubid: str) -> list[dict[str, Any]]:
        links_df = self.get_dataframe("source_to_ubid_links")
        if links_df.empty:
            return []
        subset = links_df[links_df["ubid"] == ubid]
        return [without_ground_truth(row) for row in subset.to_dict(orient="records")]

    def find_source_master_by_ubid(self, ubid: str) -> list[dict[str, Any]]:
        links = self.find_links(ubid)
        if not links:
            return []
        keys = {(row["source_system"], row["source_record_id"]) for row in links}
        source_df = self.get_dataframe("source_records_all_departments")
        if source_df.empty:
            return []
        mask = source_df.apply(lambda row: (row.get("source_system"), row.get("source_record_id")) in keys, axis=1)
        subset = source_df[mask]
        return [without_ground_truth(row) for row in subset.to_dict(orient="records")]

    def find_pair_by_int_id(self, match_id: int) -> dict[str, Any] | None:
        df = self.get_dataframe("candidate_match_pairs")
        if df.empty or "candidate_pair_id" not in df.columns:
            return None
        target = f"PAIR-{match_id:06d}"
        subset = df[df["candidate_pair_id"] == target]
        if subset.empty:
            return None
        return subset.iloc[0].to_dict()

    def find_ubid_for_link(self, source_system: str, record_id: str) -> str | None:
        if not source_system or not record_id:
            return None
        df = self.get_dataframe("source_to_ubid_links")
        if df.empty or not {"source_system", "source_record_id"}.issubset(df.columns):
            return None
        subset = df[(df["source_system"] == source_system) & (df["source_record_id"] == record_id)]
        if subset.empty:
            return None
        value = subset.iloc[0].get("ubid", "")
        return str(value) if value else None

    def set_match_status(self, pair_id: str, status: str) -> None:
        if not pair_id:
            return
        self.match_status[pair_id] = status

    def match_status_for(self, pair_id: str, decision: str) -> str:
        if pair_id in self.match_status:
            return self.match_status[pair_id]
        if decision == "AUTO_LINK":
            return "approved"
        if decision == "NO_MATCH":
            return "rejected"
        return "pending"

    def list_recommendation_rules(self) -> list[dict[str, Any]]:
        rules_df = self.get_dataframe("recommendation_rules")
        if rules_df.empty:
            return []
        rules_df = ensure_columns(
            rules_df,
            ["business_type", "required_registrations", "risk_flags", "primary_departments"],
        )
        output: list[dict[str, Any]] = []
        for row in rules_df.to_dict(orient="records"):
            output.append(
                {
                    "business_type": row["business_type"],
                    "required_registrations": split_pipe_values(row["required_registrations"]),
                    "risk_flags": split_pipe_values(row["risk_flags"]),
                    "primary_departments": split_pipe_values(row["primary_departments"]),
                }
            )
        return output

    def _refresh_indexes(self) -> None:
        normalized_df = self.get_dataframe("normalized_business_records")
        source_df = self.get_dataframe("source_records_all_departments")
        links_df = self.get_dataframe("source_to_ubid_links")
        if normalized_df.empty:
            self.search_records = pd.DataFrame()
            return
        self.search_records = build_search_records(normalized_df, source_df, links_df)

