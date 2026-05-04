from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from app.core.config import Settings

logger = logging.getLogger(__name__)


LOGICAL_DATASET_ALIASES: dict[str, tuple[str, ...]] = {
    "shop_establishments": ("shop_establishments", "shop_establishment"),
    "factories_act_registrations": ("factories_act_registrations", "factories"),
    "kspcb_consent_register": ("kspcb_consent_register",),
    "labour_registrations": ("labour_registrations",),
    "bbmp_trade_licenses": ("bbmp_trade_licenses",),
    "gst_taxpayer_records": ("gst_taxpayer_records",),
    "udyam_msme_records": ("udyam_msme_records",),
    "normalized_business_records": ("normalized_business_records",),
    "ubid_registry": ("ubid_registry",),
    "candidate_match_pairs": ("candidate_match_pairs",),
    "risk_assessment": ("risk_assessment",),
    "dashboard_mock": ("dashboard_mock",),
    "recommendation_rules": ("recommendation_rules",),
    "compliance_events": ("compliance_events",),
    "source_to_ubid_links": ("source_to_ubid_links",),
    "source_records_all_departments": ("source_records_all_departments",),
}


@dataclass(slots=True)
class LoadedDataset:
    logical_name: str
    path: Path
    dataframe: pd.DataFrame
    loaded_at: datetime


class DataLoader:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _resolve_data_root(self) -> Path:
        base = self.settings.data_dir
        if list(base.rglob("*.csv")):
            return base
        child_dirs = [path for path in base.iterdir() if path.is_dir()] if base.exists() else []
        csv_children = [path for path in child_dirs if list(path.rglob("*.csv"))]
        if len(csv_children) == 1:
            return csv_children[0]
        return base

    def load(self) -> tuple[dict[str, pd.DataFrame], list[LoadedDataset], Path]:
        root = self._resolve_data_root()
        datasets: dict[str, pd.DataFrame] = {}
        loaded: list[LoadedDataset] = []
        csv_paths = sorted(
            path
            for path in root.rglob("*.csv")
            if "legacy" not in {part.lower() for part in path.parts}
        )
        if not csv_paths:
            logger.warning("No CSV files found under %s", root)
            return datasets, loaded, root

        matched: set[Path] = set()
        for logical_name, aliases in LOGICAL_DATASET_ALIASES.items():
            dataset_path = self._find_path(csv_paths, aliases)
            if dataset_path is None:
                logger.warning("Expected dataset missing for logical name '%s'", logical_name)
                continue
            matched.add(dataset_path)
            dataframe = self._read_csv(dataset_path)
            datasets[logical_name] = dataframe
            loaded.append(
                LoadedDataset(
                    logical_name=logical_name,
                    path=dataset_path,
                    dataframe=dataframe,
                    loaded_at=datetime.now(timezone.utc),
                )
            )

        for csv_path in csv_paths:
            if csv_path in matched:
                continue
            logical_name = csv_path.stem
            dataframe = self._read_csv(csv_path)
            datasets.setdefault(logical_name, dataframe)
            loaded.append(
                LoadedDataset(
                    logical_name=logical_name,
                    path=csv_path,
                    dataframe=dataframe,
                    loaded_at=datetime.now(timezone.utc),
                )
            )
        return datasets, loaded, root

    @staticmethod
    def _find_path(paths: list[Path], aliases: tuple[str, ...]) -> Path | None:
        stems = {path.stem.lower(): path for path in paths}
        for alias in aliases:
            if alias.lower() in stems:
                return stems[alias.lower()]
        for path in paths:
            lower_name = path.name.lower()
            if any(alias.lower() in lower_name for alias in aliases):
                return path
        return None

    @staticmethod
    def _read_csv(path: Path) -> pd.DataFrame:
        try:
            return pd.read_csv(path, dtype=str).fillna("")
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed loading %s: %s", path, exc)
            return pd.DataFrame()
