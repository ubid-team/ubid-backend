"""
UBID — Unified Business Identity Resolution (hackathon prototype backend).
FastAPI + SQLite + pandas + jellyfish.
Run: uvicorn main:app --reload --port 8000
"""
from __future__ import annotations

import json
import re
import sqlite3
import uuid
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import jellyfish
import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Paths & app
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "ubid.db"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="UBID Registry API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS ubid_registry (
                ubid TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                confidence_score REAL NOT NULL,
                source_records TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ubid TEXT,
                action TEXT NOT NULL,
                reviewer_id TEXT,
                timestamp TEXT NOT NULL,
                evidence TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS match_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_a TEXT NOT NULL,
                record_b TEXT NOT NULL,
                score REAL NOT NULL,
                breakdown TEXT NOT NULL,
                tier TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
            );

            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uploaded_at TEXT NOT NULL,
                total_dept_a INTEGER NOT NULL,
                total_dept_b INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_match_tier ON match_queue(tier);
            CREATE INDEX IF NOT EXISTS idx_match_status ON match_queue(status);
            """
        )


# ---------------------------------------------------------------------------
# Normalization engine
# ---------------------------------------------------------------------------
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
# Prototype: 15-char uppercase alphanumeric (checksum not enforced).
GSTIN_RE = re.compile(r"^[0-9A-Z]{15}$")

NAME_NOISE_PATTERNS = [
    (re.compile(r"^\s*m/s\.?\s+", re.I), " "),
    (re.compile(r"\bm/s\.?\b", re.I), " "),
    (re.compile(r"\bms\.?\b", re.I), " "),
    (re.compile(r"\bpvt\.?\s*ltd\.?\b", re.I), " "),
    (re.compile(r"\bprivate\s+limited\b", re.I), " "),
    (re.compile(r"\blimited\b", re.I), " "),
    (re.compile(r"\bltd\.?\b", re.I), " "),
    (re.compile(r"\bllp\b", re.I), " "),
    (re.compile(r"\b&\s*co\.?\b", re.I), " "),
    (re.compile(r"\bco\.?\b", re.I), " "),
    (re.compile(r"\band\b", re.I), " "),
    (re.compile(r"\s*&\s*"), " "),
    (re.compile(r"\bsons\b", re.I), " "),
    (re.compile(r"\bunit\b", re.I), " "),
]

ADDR_ABBREVS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bblr\b", re.I), "bengaluru"),
    (re.compile(r"\bblore\b", re.I), "bengaluru"),
    (re.compile(r"\bbnglr\b", re.I), "bengaluru"),
    (re.compile(r"\bbangalore\b", re.I), "bengaluru"),
    (re.compile(r"\bmysore\b", re.I), "mysuru"),
    (re.compile(r"\bhubli\b", re.I), "hubballi"),
    (re.compile(r"\bdvg\b", re.I), "davangere"),
    (re.compile(r"\bdavanagere\b", re.I), "davangere"),
    (re.compile(r"\bmg\b", re.I), "mahatma gandhi"),
    (re.compile(r"\bind\.?\b", re.I), "industrial"),
    (re.compile(r"\bindustrial\s+area\b", re.I), "industrial area"),
    (re.compile(r"\bph\b", re.I), "phase"),
    (re.compile(r"\brd\b", re.I), "road"),
    (re.compile(r"\bst\b", re.I), "street"),
    (re.compile(r"\bcomm\b", re.I), "commercial"),
    (re.compile(r"\btp\b", re.I), "tech park"),
    (re.compile(r"\bka\b", re.I), "karnataka"),
    (re.compile(r"\bblk\b", re.I), "block"),
]


def clean_business_name(raw: str) -> str:
    s = (raw or "").strip().lower()
    for pat, repl in NAME_NOISE_PATTERNS:
        s = pat.sub(repl, s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def standardize_address(raw: str) -> str:
    s = (raw or "").strip().lower()
    for pat, repl in ADDR_ABBREVS:
        s = pat.sub(repl, s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_pan(value: str | None) -> Optional[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip().upper()
    if not s or s == "NAN":
        return None
    return s if PAN_RE.match(s) else None


def normalize_gstin(value: str | None) -> Optional[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = re.sub(r"\s+", "", str(value)).strip().upper()
    if not s or s == "NAN":
        return None
    if len(s) != 15 or not s.isalnum():
        return None
    return s if GSTIN_RE.match(s) else None


def phone_last_digits(value: str | None, n: int = 8) -> Optional[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    digits = re.sub(r"\D", "", str(value))
    if len(digits) < n:
        return None
    return digits[-n:]


def blocking_key(pincode: str, clean_name: str) -> tuple[str, str]:
    pc = re.sub(r"\D", "", str(pincode or ""))[:6].zfill(6)
    alnum = "".join(ch for ch in clean_name if ch.isalnum())
    prefix = (alnum[:2] if len(alnum) >= 2 else (alnum + "zz")[:2]).lower()
    return pc, prefix


# ---------------------------------------------------------------------------
# Similarity (token sort ratio + Jaro–Winkler ensemble)
# ---------------------------------------------------------------------------
def token_sort_ratio(s1: str, s2: str) -> float:
    """Fuzzywuzzy-style token sort: sort tokens, join, compare with Jaro–Winkler → 0–100."""
    t1 = " ".join(sorted((s1 or "").split()))
    t2 = " ".join(sorted((s2 or "").split()))
    if not t1 and not t2:
        return 100.0
    if not t1 or not t2:
        return 0.0
    return float(jellyfish.jaro_winkler_similarity(t1, t2)) * 100.0


def jw_percent(a: str, b: str) -> float:
    if not a and not b:
        return 100.0
    if not a or not b:
        return 0.0
    return float(jellyfish.jaro_winkler_similarity(a, b)) * 100.0


W_NAME = 0.30
W_ADDR = 0.25
W_PAN = 0.35
W_PHONE = 0.10


def pan_component(pan_a: Optional[str], pan_b: Optional[str]) -> float:
    if pan_a and pan_b and pan_a == pan_b:
        return 100.0
    return 0.0


def phone_component(p_a: Optional[str], p_b: Optional[str]) -> float:
    if p_a and p_b and p_a == p_b:
        return 100.0
    return 0.0


def match_tier(score: float) -> str:
    if score >= 85:
        return "AUTO_LINK"
    if score >= 60:
        return "HUMAN_REVIEW"
    return "NO_MATCH"


def score_pair(norm_a: dict[str, Any], norm_b: dict[str, Any]) -> dict[str, Any]:
    name_s = jw_percent(norm_a["name_clean"], norm_b["name_clean"])
    addr_s = token_sort_ratio(norm_a["address_clean"], norm_b["address_clean"])
    pan_s = pan_component(norm_a.get("pan"), norm_b.get("pan"))
    ph_s = phone_component(norm_a.get("phone8"), norm_b.get("phone8"))
    total = W_NAME * name_s + W_ADDR * addr_s + W_PAN * pan_s + W_PHONE * ph_s
    tier = match_tier(total)
    return {
        "score": round(total, 2),
        "breakdown": {
            "name_jaro_winkler": round(name_s, 2),
            "address_token_sort": round(addr_s, 2),
            "pan": round(pan_s, 2),
            "phone_last8": round(ph_s, 2),
            "weights": {"name": W_NAME, "address": W_ADDR, "pan": W_PAN, "phone": W_PHONE},
        },
        "tier": tier,
    }


# ---------------------------------------------------------------------------
# Ingest & pipeline
# ---------------------------------------------------------------------------
def _row_to_norm_shop(row: pd.Series, source: str) -> dict[str, Any]:
    name = str(row.get("business_name", row.get("name", "")))
    addr = str(row.get("address", ""))
    pan = normalize_pan(row.get("pan"))
    gstin = normalize_gstin(row.get("gstin"))
    phone_col = row.get("phone", row.get("contact", ""))
    rid = str(row.get("reg_id", row.get("factory_id", "")))
    nc = clean_business_name(name)
    return {
        "source": source,
        "record_id": rid,
        "raw": {k: (None if (isinstance(v, float) and pd.isna(v)) else v) for k, v in row.items()},
        "name_clean": nc,
        "address_clean": standardize_address(addr),
        "pincode": str(row.get("pincode", "")).strip(),
        "pan": pan,
        "gstin": gstin,
        "phone8": phone_last_digits(phone_col, 8),
    }


def _row_to_norm_factory(row: pd.Series, source: str) -> dict[str, Any]:
    name = str(row.get("name", row.get("business_name", "")))
    addr = str(row.get("address", ""))
    pan = normalize_pan(row.get("pan"))
    gstin = normalize_gstin(row.get("gstin"))
    phone_col = row.get("contact", row.get("phone", ""))
    rid = str(row.get("factory_id", row.get("reg_id", "")))
    nc = clean_business_name(name)
    return {
        "source": source,
        "record_id": rid,
        "raw": {k: (None if (isinstance(v, float) and pd.isna(v)) else v) for k, v in row.items()},
        "name_clean": nc,
        "address_clean": standardize_address(addr),
        "pincode": str(row.get("pincode", "")).strip(),
        "pan": pan,
        "gstin": gstin,
        "phone8": phone_last_digits(phone_col, 8),
    }


def _normalize_dataframe(df: pd.DataFrame, source: str, prefer: str) -> list[dict[str, Any]]:
    df = df.fillna("")
    out: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        if prefer == "shop":
            out.append(_row_to_norm_shop(row, source))
        else:
            out.append(_row_to_norm_factory(row, source))
    return out


def run_matching_pipeline(records_a: list[dict[str, Any]], records_b: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocks: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in records_a:
        k = blocking_key(r["pincode"], r["name_clean"])
        blocks.setdefault(k, []).append(("a", r))
    for r in records_b:
        k = blocking_key(r["pincode"], r["name_clean"])
        blocks.setdefault(k, []).append(("b", r))

    matches: list[dict[str, Any]] = []
    for bucket in blocks.values():
        as_ = [x for side, x in bucket if side == "a"]
        bs = [x for side, x in bucket if side == "b"]
        for ra in as_:
            for rb in bs:
                sc = score_pair(ra, rb)
                matches.append(
                    {
                        "record_a": {
                            "source": ra["source"],
                            "record_id": ra["record_id"],
                            "normalized": {
                                "name_clean": ra["name_clean"],
                                "address_clean": ra["address_clean"],
                                "pincode": ra["pincode"],
                                "pan": ra["pan"],
                                "gstin": ra["gstin"],
                                "phone_last8": ra["phone8"],
                            },
                            "raw": ra["raw"],
                        },
                        "record_b": {
                            "source": rb["source"],
                            "record_id": rb["record_id"],
                            "normalized": {
                                "name_clean": rb["name_clean"],
                                "address_clean": rb["address_clean"],
                                "pincode": rb["pincode"],
                                "pan": rb["pan"],
                                "gstin": rb["gstin"],
                                "phone_last8": rb["phone8"],
                            },
                            "raw": rb["raw"],
                        },
                        "score": sc["score"],
                        "breakdown": sc["breakdown"],
                        "tier": sc["tier"],
                    }
                )
    return matches


def persist_pipeline_run(conn: sqlite3.Connection, n_a: int, n_b: int) -> None:
    conn.execute(
        "INSERT INTO pipeline_runs (uploaded_at, total_dept_a, total_dept_b) VALUES (?,?,?)",
        (_utc_now_iso(), n_a, n_b),
    )


def replace_match_queue(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM match_queue")
    for m in rows:
        conn.execute(
            """
            INSERT INTO match_queue (record_a, record_b, score, breakdown, tier, status)
            VALUES (?,?,?,?,?,'pending')
            """,
            (
                json.dumps(m["record_a"], default=str),
                json.dumps(m["record_b"], default=str),
                m["score"],
                json.dumps(m["breakdown"]),
                m["tier"],
            ),
        )


# ---------------------------------------------------------------------------
# Pydantic models (request bodies)
# ---------------------------------------------------------------------------
class ReviewBody(BaseModel):
    reviewer_id: str = Field(default="anonymous_reviewer")
    evidence: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# FastAPI endpoints
# ---------------------------------------------------------------------------
@app.post("/upload")
async def upload(
    dept_a: UploadFile = File(..., description="CSV for department A (e.g. shop establishment)"),
    dept_b: UploadFile = File(..., description="CSV for department B (e.g. factories)"),
):
    """Accept two CSVs, normalize, block, score, refill match_queue; return summary."""
    try:
        df_a = pd.read_csv(dept_a.file)
        df_b = pd.read_csv(dept_b.file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {e}") from e

    # Infer row shape: shop register vs factory register
    def infer_prefer(df: pd.DataFrame) -> str:
        cols = set(df.columns.astype(str).str.lower())
        if "business_name" in cols:
            return "shop"
        if "factory_id" in cols and "name" in cols:
            return "factory"
        if "reg_id" in cols:
            return "shop"
        return "factory"

    prefer_a = infer_prefer(df_a)
    prefer_b = infer_prefer(df_b)

    rec_a = _normalize_dataframe(df_a, "dept_a", prefer_a)
    rec_b = _normalize_dataframe(df_b, "dept_b", prefer_b)

    all_matches = run_matching_pipeline(rec_a, rec_b)
    tier_counts: dict[str, int] = {}
    for m in all_matches:
        tier_counts[m["tier"]] = tier_counts.get(m["tier"], 0) + 1

    with get_db() as conn:
        persist_pipeline_run(conn, len(rec_a), len(rec_b))
        replace_match_queue(conn, all_matches)

    total_records = len(rec_a) + len(rec_b)
    return {
        "ok": True,
        "total_records": total_records,
        "dept_a_rows": len(rec_a),
        "dept_b_rows": len(rec_b),
        "candidate_pairs": len(all_matches),
        "tier_counts": tier_counts,
        "blocking": "pincode + first 2 alphanumeric chars of cleaned business name",
    }


@app.get("/matches")
def list_matches(tier: Optional[str] = Query(None, description="Filter: AUTO_LINK, HUMAN_REVIEW, NO_MATCH")):
    q = "SELECT id, record_a, record_b, score, breakdown, tier, status FROM match_queue"
    args: list[Any] = []
    if tier:
        q += " WHERE tier = ?"
        args.append(tier)
    q += " ORDER BY score DESC, id ASC"
    with get_db() as conn:
        cur = conn.execute(q, args)
        rows = cur.fetchall()
    out = []
    for r in rows:
        out.append(
            {
                "id": r["id"],
                "record_a": json.loads(r["record_a"]),
                "record_b": json.loads(r["record_b"]),
                "score": r["score"],
                "breakdown": json.loads(r["breakdown"]),
                "tier": r["tier"],
                "status": r["status"],
            }
        )
    return {"matches": out, "count": len(out)}


@app.post("/matches/{match_id}/approve")
def approve_match(match_id: int, body: ReviewBody | None = None):
    body = body or ReviewBody()
    with get_db() as conn:
        cur = conn.execute("SELECT * FROM match_queue WHERE id = ?", (match_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Match not found")
        if row["status"] != "pending":
            raise HTTPException(status_code=400, detail=f"Match already {row['status']}")

        ra = json.loads(row["record_a"])
        rb = json.loads(row["record_b"])
        new_ubid = str(uuid.uuid4())
        source_records = [
            {"source": ra["source"], "id": ra["record_id"]},
            {"source": rb["source"], "id": rb["record_id"]},
        ]
        evidence = {
            "match_id": match_id,
            "score": row["score"],
            "tier": row["tier"],
            "reviewer_notes": body.evidence,
        }
        conn.execute(
            """
            INSERT INTO ubid_registry (ubid, created_at, status, confidence_score, source_records)
            VALUES (?,?,?,?,?)
            """,
            (
                new_ubid,
                _utc_now_iso(),
                "active",
                float(row["score"]),
                json.dumps(source_records),
            ),
        )
        conn.execute(
            """
            INSERT INTO audit_log (ubid, action, reviewer_id, timestamp, evidence)
            VALUES (?,?,?,?,?)
            """,
            (new_ubid, "approved", body.reviewer_id, _utc_now_iso(), json.dumps(evidence)),
        )
        conn.execute("UPDATE match_queue SET status = 'approved' WHERE id = ?", (match_id,))

    return {"ok": True, "ubid": new_ubid, "match_id": match_id, "status": "approved"}


@app.post("/matches/{match_id}/reject")
def reject_match(match_id: int, body: ReviewBody | None = None):
    body = body or ReviewBody()
    with get_db() as conn:
        cur = conn.execute("SELECT * FROM match_queue WHERE id = ?", (match_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Match not found")
        if row["status"] != "pending":
            raise HTTPException(status_code=400, detail=f"Match already {row['status']}")

        evidence = {
            "match_id": match_id,
            "score": row["score"],
            "tier": row["tier"],
            "reviewer_notes": body.evidence,
        }
        conn.execute(
            """
            INSERT INTO audit_log (ubid, action, reviewer_id, timestamp, evidence)
            VALUES (?,?,?,?,?)
            """,
            (None, "rejected", body.reviewer_id, _utc_now_iso(), json.dumps(evidence)),
        )
        conn.execute("UPDATE match_queue SET status = 'rejected' WHERE id = ?", (match_id,))

    return {"ok": True, "match_id": match_id, "status": "rejected"}


@app.get("/registry")
def get_registry():
    with get_db() as conn:
        cur = conn.execute(
            "SELECT ubid, created_at, status, confidence_score, source_records FROM ubid_registry ORDER BY created_at DESC"
        )
        rows = cur.fetchall()
    reg = []
    for r in rows:
        reg.append(
            {
                "ubid": r["ubid"],
                "created_at": r["created_at"],
                "status": r["status"],
                "confidence_score": r["confidence_score"],
                "source_records": json.loads(r["source_records"]),
            }
        )
    return {"ubids": reg, "count": len(reg)}


@app.get("/stats")
def stats():
    with get_db() as conn:
        pr = conn.execute(
            "SELECT total_dept_a, total_dept_b FROM pipeline_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        total_records = int(pr["total_dept_a"] + pr["total_dept_b"]) if pr else 0

        auto_linked = conn.execute(
            "SELECT COUNT(*) AS c FROM match_queue WHERE tier = 'AUTO_LINK' AND status = 'approved'"
        ).fetchone()["c"]
        pending_review = conn.execute(
            "SELECT COUNT(*) AS c FROM match_queue WHERE tier = 'HUMAN_REVIEW' AND status = 'pending'"
        ).fetchone()["c"]
        rejected = conn.execute("SELECT COUNT(*) AS c FROM match_queue WHERE status = 'rejected'").fetchone()["c"]
        ubids_assigned = conn.execute("SELECT COUNT(*) AS c FROM ubid_registry").fetchone()["c"]

    return {
        "total_records": total_records,
        "auto_linked": auto_linked,
        "pending_review": pending_review,
        "rejected": rejected,
        "ubids_assigned": ubids_assigned,
    }


@app.get("/health")
def health():
    return {"status": "ok"}

