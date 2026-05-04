from __future__ import annotations

import os
import sys
from pathlib import Path
from importlib import import_module, reload

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [",".join(header)]
    for row in rows:
        lines.append(",".join(row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture()
def test_data_dir(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    _write_csv(
        data_dir / "processed" / "normalized_business_records.csv",
        [
            "source_record_id",
            "source_system",
            "business_name_raw",
            "business_name_normalized",
            "address_raw",
            "address_normalized",
            "district",
            "pin_code",
            "business_type",
            "business_category",
            "pan_hash_present",
            "gstin_hash_present",
            "phone_present",
            "blocking_key_pin_category",
            "blocking_key_pin_name4",
            "status",
            "last_event_date",
            "entity_id_ground_truth",
        ],
        [
            [
                "SRC-001",
                "GST",
                "Ravi Food Processing",
                "RAVI FOOD PROCESSING",
                "Peenya Industrial Area Bengaluru",
                "PEENYA INDUSTRIAL AREA BENGALURU",
                "Bengaluru Urban",
                "560058",
                "Food Processing",
                "Manufacturing",
                "True",
                "True",
                "True",
                "560058::Manufacturing",
                "560058::RAVI",
                "ACTIVE",
                "2025-11-20",
                "ENT-1",
            ],
            [
                "SRC-002",
                "SHOP",
                "Anu Retail",
                "ANU RETAIL",
                "Mysuru Main Road",
                "MYSURU MAIN ROAD",
                "Mysuru",
                "570001",
                "Retail Store",
                "Service",
                "False",
                "False",
                "True",
                "570001::Service",
                "570001::ANUR",
                "ACTIVE",
                "2025-10-01",
                "ENT-2",
            ],
        ],
    )
    _write_csv(
        data_dir / "processed" / "ubid_registry.csv",
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
            "entity_id_ground_truth",
        ],
        [
            [
                "KA-BLRU-560058-000001",
                "Ravi Food Processing",
                "Peenya Industrial Area Bengaluru",
                "Bengaluru Urban",
                "560058",
                "Food Processing",
                "Manufacturing",
                "ACTIVE",
                "96",
                "3",
                "GST|KSPCB|LABOUR",
                "2026-05-02",
                "2025-11-20",
                "deterministic",
                "ENT-1",
            ]
        ],
    )
    _write_csv(
        data_dir / "processed" / "source_to_ubid_links.csv",
        ["ubid", "source_system", "source_record_id", "link_type", "link_confidence", "linked_at", "entity_id_ground_truth"],
        [
            ["KA-BLRU-560058-000001", "GST", "SRC-001", "AUTO_LINK", "96", "2026-05-02", "ENT-1"],
            ["KA-BLRU-560058-000001", "KSPCB", "PCB-001", "AUTO_LINK", "91", "2026-05-02", "ENT-1"],
            ["KA-BLRU-560058-000001", "LABOUR", "LAB-001", "AUTO_LINK", "88", "2026-05-02", "ENT-1"],
        ],
    )
    _write_csv(
        data_dir / "events" / "compliance_events.csv",
        ["event_id", "ubid", "source_system", "source_record_id", "event_type", "event_date", "event_outcome", "event_note"],
        [
            ["EV-1", "KA-BLRU-560058-000001", "KSPCB", "PCB-001", "INSPECTION", "2025-11-20", "OK", "inspection complete"]
        ],
    )
    _write_csv(
        data_dir / "processed" / "dashboard_mock.csv",
        [
            "ubid",
            "business_name",
            "district",
            "pin_code",
            "status",
            "linked_departments",
            "progress_identity_verified_pct",
            "progress_department_linkage_pct",
            "risk_score",
            "risk_level",
            "human_review_required",
        ],
        [["KA-BLRU-560058-000001", "Ravi Food Processing", "Bengaluru Urban", "560058", "ACTIVE", "GST|KSPCB|LABOUR", "95", "90", "42", "MEDIUM", "False"]],
    )
    _write_csv(
        data_dir / "processed" / "risk_assessment.csv",
        ["ubid", "business_name", "risk_score", "risk_level", "activity_status", "last_activity_date", "linked_departments", "risk_reasons"],
        [["KA-BLRU-560058-000001", "Ravi Food Processing", "42", "Medium", "ACTIVE", "2025-11-20", "GST|KSPCB|LABOUR", "recent inspection available"]],
    )
    _write_csv(
        data_dir / "processed" / "recommendation_rules.csv",
        ["business_type", "required_registrations", "risk_flags", "primary_departments"],
        [["Food Processing", "Shop Establishment|GST|FSSAI", "KSPCB consent missing", "SHOP|GST|KSPCB"]],
    )
    _write_csv(
        data_dir / "raw" / "source_records_all_departments.csv",
        [
            "source_record_id",
            "source_system",
            "source_system_name",
            "entity_id_ground_truth",
            "business_name",
            "trade_name",
            "owner_name_masked",
            "address",
            "locality",
            "district",
            "district_code",
            "pin_code",
            "ward",
            "zone",
            "business_type",
            "business_category",
            "nic_code",
            "pollution_category",
            "pan_hash",
            "gstin_hash",
            "udyam_hash",
            "phone",
            "email",
            "registration_date",
            "last_event_date",
            "status",
            "employee_count",
            "turnover_band_lakh",
            "ingested_at",
            "data_quality_notes",
        ],
        [
            [
                "SRC-001",
                "GST",
                "GST Department",
                "ENT-1",
                "Ravi Food Processing",
                "",
                "",
                "Peenya Industrial Area Bengaluru",
                "Peenya",
                "Bengaluru Urban",
                "BLRU",
                "560058",
                "",
                "",
                "Food Processing",
                "Manufacturing",
                "",
                "orange",
                "HASH_PAN_001",
                "HASH_GST_001",
                "",
                "9876543210",
                "",
                "2023-01-01",
                "2025-11-20",
                "ACTIVE",
                "18",
                "",
                "2026-05-01",
                "",
            ],
            [
                "SRC-002",
                "SHOP",
                "Shop Department",
                "ENT-2",
                "Anu Retail",
                "",
                "",
                "Mysuru Main Road",
                "Mysuru",
                "Mysuru",
                "MYS",
                "570001",
                "",
                "",
                "Retail Store",
                "Service",
                "",
                "",
                "",
                "",
                "",
                "9988776655",
                "",
                "2023-01-01",
                "2025-10-01",
                "ACTIVE",
                "5",
                "",
                "2026-05-01",
                "",
            ],
        ],
    )
    _write_csv(data_dir / "raw" / "shop_establishments.csv", ["source_record_id"], [["SHOP-1"]])
    _write_csv(data_dir / "raw" / "factories_act_registrations.csv", ["source_record_id"], [["FAC-1"]])
    _write_csv(data_dir / "raw" / "kspcb_consent_register.csv", ["source_record_id"], [["PCB-1"]])
    _write_csv(data_dir / "raw" / "labour_registrations.csv", ["source_record_id"], [["LAB-1"]])
    _write_csv(data_dir / "raw" / "bbmp_trade_licenses.csv", ["source_record_id"], [["BBMP-1"]])
    _write_csv(data_dir / "raw" / "gst_taxpayer_records.csv", ["source_record_id"], [["GST-1"]])
    _write_csv(data_dir / "raw" / "udyam_msme_records.csv", ["source_record_id"], [["UDYAM-1"]])
    _write_csv(data_dir / "processed" / "candidate_match_pairs.csv", ["candidate_pair_id"], [["CMP-1"]])
    return data_dir


@pytest.fixture()
def client(test_data_dir: Path) -> TestClient:
    os.environ["DATA_DIR"] = str(test_data_dir)
    os.environ["OPENROUTER_API_KEY"] = ""
    import app.core.config as config_module
    reload(config_module)
    main_module = import_module("app.main")
    reload(main_module)
    app = main_module.app

    with TestClient(app) as test_client:
        yield test_client
