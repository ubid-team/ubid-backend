"""Compatibility routes for the existing UBID neo-glow frontend.

The frontend was wired against an earlier API surface (/upload, /matches,
/stats, /registry, /matches/{id}/approve|reject). These routes adapt the
current deterministic backend so the demo UI works end-to-end without UI
rewrites. They reuse the in-memory `DataRepository` and existing services.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel

from app.data.normalizer import without_ground_truth
from app.models.business import BusinessRecord


router = APIRouter(tags=["compat"])


class MatchActionRequest(BaseModel):
    reviewer_id: str | None = None
    evidence: dict[str, Any] | None = None


def _pair_int_id(pair_id: str) -> int:
    digits = "".join(ch for ch in str(pair_id) if ch.isdigit())
    return int(digits) if digits else 0


def _normalized_block(rec: dict[str, Any]) -> dict[str, Any]:
    phone = str(rec.get("phone") or "").strip()
    return {
        "name_clean": str(rec.get("business_name") or "").upper(),
        "address_clean": str(rec.get("address") or "").upper(),
        "pincode": str(rec.get("pin_code") or ""),
        "pan": rec.get("pan_hash") or None,
        "gstin": rec.get("gstin_hash") or None,
        "phone_last8": phone[-8:] if phone else None,
    }


def _record_block(
    source: str,
    record_id: str,
    fallback_name: str,
    sm_lookup: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    raw = sm_lookup.get((source, record_id))
    if raw is None:
        raw = {
            "source_system": source,
            "source_record_id": record_id,
            "business_name": fallback_name,
        }
    raw_clean = without_ground_truth(raw)
    return {
        "source": source,
        "record_id": record_id,
        "normalized": _normalized_block(raw),
        "raw": raw_clean,
    }


def _safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@router.post("/reset")
def reset_demo(request: Request) -> dict[str, Any]:
    """Wipe all in-memory data so the dashboard shows 0/0/0 until next upload.

    Files on disk are untouched; calling /api/data/reload (or POST /upload) will
    re-ingest them.
    """
    repo = request.app.state.repository
    repo.clear()
    return {
        "ok": True,
        "message": "in-memory data cleared",
        "data_loaded": repo.data_loaded,
    }


@router.get("/stats")
def stats(request: Request) -> dict[str, Any]:
    repo = request.app.state.repository
    pairs_df = repo.get_dataframe("candidate_match_pairs")
    registry_df = repo.get_dataframe("ubid_registry")
    source_master = repo.get_dataframe("source_records_all_departments")

    auto_linked = 0
    pending_review = 0
    rejected = 0
    if not pairs_df.empty and {"candidate_pair_id", "decision"}.issubset(pairs_df.columns):
        for row in pairs_df[["candidate_pair_id", "decision"]].to_dict(orient="records"):
            decision = str(row.get("decision") or "").upper()
            status = repo.match_status_for(str(row.get("candidate_pair_id") or ""), decision)
            if status == "approved":
                auto_linked += 1
            elif status == "rejected":
                rejected += 1
            else:
                pending_review += 1

    return {
        "total_records": int(len(source_master.index)),
        "auto_linked": auto_linked,
        "pending_review": pending_review,
        "rejected": rejected,
        "ubids_assigned": int(len(registry_df.index)),
    }


@router.get("/matches")
def list_matches(
    request: Request,
    tier: str | None = Query(default=None),
    limit: int = Query(default=5000, ge=1, le=10000),
) -> dict[str, Any]:
    repo = request.app.state.repository
    pairs_df = repo.get_dataframe("candidate_match_pairs")
    if pairs_df.empty:
        return {"matches": [], "count": 0}

    source_master = repo.get_dataframe("source_records_all_departments")
    sm_lookup: dict[tuple[str, str], dict[str, Any]] = {}
    if not source_master.empty and {"source_system", "source_record_id"}.issubset(source_master.columns):
        for row in source_master.to_dict(orient="records"):
            sm_lookup[(str(row.get("source_system", "")), str(row.get("source_record_id", "")))] = row

    tier_upper = tier.upper() if tier else None
    matches: list[dict[str, Any]] = []
    for row in pairs_df.to_dict(orient="records"):
        decision = str(row.get("decision") or "").upper()
        if tier_upper and decision != tier_upper:
            continue
        pair_id = str(row.get("candidate_pair_id") or "")
        left_src = str(row.get("left_source_system") or "")
        left_id = str(row.get("left_record_id") or "")
        right_src = str(row.get("right_source_system") or "")
        right_id = str(row.get("right_record_id") or "")
        record_a = _record_block(left_src, left_id, str(row.get("left_business_name") or ""), sm_lookup)
        record_b = _record_block(right_src, right_id, str(row.get("right_business_name") or ""), sm_lookup)
        score = _safe_float(row.get("match_score"))
        tier_val = decision if decision in {"AUTO_LINK", "HUMAN_REVIEW", "NO_MATCH"} else "NO_MATCH"
        status = repo.match_status_for(pair_id, tier_val)
        matches.append(
            {
                "id": _pair_int_id(pair_id),
                "record_a": record_a,
                "record_b": record_b,
                "score": score,
                "breakdown": {
                    "name_jaro_winkler": _safe_float(row.get("name_score")) / 100.0,
                    "address_token_sort": _safe_float(row.get("address_score")) / 100.0,
                    "pan": _safe_float(row.get("identifier_score")) / 100.0,
                    "phone_last8": _safe_float(row.get("phone_score")) / 100.0,
                    "weights": {"name": 0.30, "address": 0.25, "pan": 0.35, "phone": 0.10},
                },
                "tier": tier_val,
                "status": status,
            }
        )

    matches.sort(key=lambda m: m["score"], reverse=True)
    total = len(matches)
    return {"matches": matches[:limit], "count": total}


@router.get("/registry")
def registry(
    request: Request,
    limit: int = Query(default=5000, ge=1, le=10000),
) -> dict[str, Any]:
    repo = request.app.state.repository
    registry_df = repo.get_dataframe("ubid_registry")
    if registry_df.empty:
        return {"ubids": [], "count": 0}

    rows: list[dict[str, Any]] = []
    for row in registry_df.head(limit).to_dict(orient="records"):
        ubid = str(row.get("ubid") or "")
        if not ubid:
            continue
        links = repo.find_links(ubid)
        sources = [
            {
                "source": str(link.get("source_system") or ""),
                "id": str(link.get("source_record_id") or ""),
            }
            for link in links
        ]
        rows.append(
            {
                "ubid": ubid,
                "created_at": str(row.get("created_at") or ""),
                "status": str(row.get("activity_status") or ""),
                "confidence_score": _safe_int(row.get("confidence")),
                "source_records": sources,
            }
        )
    return {"ubids": rows, "count": int(len(registry_df.index))}


@router.post("/matches/{match_id}/approve")
def approve_match(
    request: Request,
    match_id: int,
    body: MatchActionRequest | None = None,
) -> dict[str, Any]:
    repo = request.app.state.repository
    pair = repo.find_pair_by_int_id(match_id)
    if not pair:
        raise HTTPException(status_code=404, detail=f"match {match_id} not found")
    pair_id = str(pair.get("candidate_pair_id") or "")

    left_src = str(pair.get("left_source_system") or "")
    left_id = str(pair.get("left_record_id") or "")
    right_src = str(pair.get("right_source_system") or "")
    right_id = str(pair.get("right_record_id") or "")

    ubid = repo.find_ubid_for_link(left_src, left_id) or repo.find_ubid_for_link(right_src, right_id)

    if not ubid:
        ubid_service = request.app.state.ubid_service
        district = "Bengaluru Urban"
        pin_code = str(pair.get("pin_code") or "560000")
        ubid = ubid_service._next_ubid(district, pin_code)
        record = BusinessRecord(
            business_name=str(pair.get("left_business_name") or pair.get("right_business_name") or "Unknown"),
            district=district,
            pin_code=pin_code,
            source="HUMAN_REVIEW",
        )
        repo.add_registry_entry(ubid, record.model_dump(), source_count=2)
        for src, rid in ((left_src, left_id), (right_src, right_id)):
            if src and rid:
                repo.add_source_link(ubid, {"source": src, "source_record_id": rid})

    repo.set_match_status(pair_id, "approved")
    return {"ok": True, "ubid": ubid, "match_id": match_id, "status": "approved"}


@router.post("/matches/{match_id}/reject")
def reject_match(
    request: Request,
    match_id: int,
    body: MatchActionRequest | None = None,
) -> dict[str, Any]:
    repo = request.app.state.repository
    pair = repo.find_pair_by_int_id(match_id)
    if not pair:
        raise HTTPException(status_code=404, detail=f"match {match_id} not found")
    pair_id = str(pair.get("candidate_pair_id") or "")
    repo.set_match_status(pair_id, "rejected")
    return {"ok": True, "match_id": match_id, "status": "rejected"}


@router.post("/upload")
async def upload_pair(
    request: Request,
    dept_a: UploadFile = File(...),
    dept_b: UploadFile = File(...),
) -> dict[str, Any]:
    repo = request.app.state.repository
    raw_dir = Path(repo.settings.data_dir) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    saved_rows: dict[str, int] = {}
    for label, upload in (("dept_a", dept_a), ("dept_b", dept_b)):
        if not upload.filename:
            raise HTTPException(status_code=400, detail=f"{label} filename missing")
        if not upload.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail=f"{label} must be a .csv file")
        target = raw_dir / upload.filename
        with target.open("wb") as out:
            shutil.copyfileobj(upload.file, out)
        try:
            with target.open("r", encoding="utf-8", errors="replace") as fh:
                saved_rows[label] = max(0, sum(1 for _ in fh) - 1)
        except OSError:
            saved_rows[label] = 0

    repo.reload()

    pairs_df = repo.get_dataframe("candidate_match_pairs")
    tier_counts: dict[str, int] = {"AUTO_LINK": 0, "HUMAN_REVIEW": 0, "NO_MATCH": 0}
    if not pairs_df.empty and "decision" in pairs_df.columns:
        for key, value in pairs_df["decision"].value_counts().to_dict().items():
            tier_counts[str(key).upper()] = int(value)

    source_master = repo.get_dataframe("source_records_all_departments")
    return {
        "ok": True,
        "total_records": int(len(source_master.index)),
        "dept_a_rows": saved_rows.get("dept_a", 0),
        "dept_b_rows": saved_rows.get("dept_b", 0),
        "candidate_pairs": int(len(pairs_df.index)),
        "tier_counts": tier_counts,
        "blocking": "PIN code + business category (deterministic, MVP)",
    }
