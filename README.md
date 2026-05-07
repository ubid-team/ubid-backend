# UBID Backend MVP

FastAPI backend MVP for UBID: Unified Business Identity Resolution for Karnataka. The backend ingests synthetic multi-department CSV exports, normalizes messy business records, resolves likely duplicate entities, works with or generates UBIDs, calculates deterministic risk, and returns structured business guidance for a frontend over REST APIs.

## Architecture

- `app/data`: CSV loader, normalization helpers, repository/index layer
- `app/services`: deterministic business logic for resolution, UBID flow, risk, dashboard, recommendations, and optional LLM phrasing
- `app/api`: REST routes grouped by concern
- `app/models`: request and response models with Pydantic v2
- `tests`: pytest coverage for health, loader, resolution, risk, and chat fallback

## Data Files Expected

The loader scans `DATA_DIR` recursively and maps known datasets when these CSVs are present:

- `shop_establishments.csv`
- `factories_act_registrations.csv`
- `kspcb_consent_register.csv`
- `labour_registrations.csv`
- `bbmp_trade_licenses.csv`
- `gst_taxpayer_records.csv`
- `udyam_msme_records.csv`
- `normalized_business_records.csv`
- `ubid_registry.csv`
- `candidate_match_pairs.csv`
- `risk_assessment.csv`
- `dashboard_mock.csv`
- `recommendation_rules.csv`
- `compliance_events.csv`
- `source_to_ubid_links.csv`
- `source_records_all_departments.csv`

If a file is missing, the backend logs a warning and continues with available data. If no CSVs are found, the API stays up but data-dependent endpoints return a clear error telling you to place the synthetic dataset under `DATA_DIR`.

## Setup

Linux / macOS:

```bash
cd ubid-backend
cp .env.example .env
uv venv .venv
uv pip install -r requirements.txt
uv run uvicorn app.main:app --reload
# or
./run.sh
```

Windows (PowerShell):

```powershell
cd ubid-backend
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
# or
.\run.ps1
```

## OpenRouter Setup

Set these environment variables in `.env` when you want natural-language phrasing from OpenRouter:

```env
OPENROUTER_API_KEY=
OPENROUTER_MODEL=openrouter/free
```

The backend always keeps core entity resolution, risk scoring, dashboard aggregation, and recommendations deterministic. If the API key is missing, the model fails, or the model returns invalid JSON, `/api/chat` falls back to deterministic replies.

## Data Layout

The backend expects the active dataset directly under `data/`:

- `data/raw/*.csv`
- `data/processed/*.csv`
- `data/events/*.csv`
- `data/samples/*`
- `data/schemas/*`

Reference bundle metadata can also live under `data/docs`, `data/code`, and `data/dataset_manifest.json`.

## API Examples

Health:

```bash
curl http://127.0.0.1:8000/health
```

Loaded sources:

```bash
curl http://127.0.0.1:8000/api/data/sources
```

Reload CSVs:

```bash
curl -X POST http://127.0.0.1:8000/api/data/reload
```

Business search:

```bash
curl "http://127.0.0.1:8000/api/business/search?q=food%20processing&limit=5"
```

Entity resolution:

```bash
curl -X POST http://127.0.0.1:8000/api/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "record": {
      "business_name": "Ravi Food Processing",
      "address": "Peenya Industrial Area Bengaluru",
      "pin_code": "560058",
      "phone": "9876543210",
      "pan_hash": "HASH_PAN_001",
      "gstin_hash": "HASH_GST_001",
      "source": "USER_INTAKE"
    },
    "limit": 10
  }'
```

UBID generation:

```bash
curl -X POST http://127.0.0.1:8000/api/ubid/generate \
  -H "Content-Type: application/json" \
  -d '{
    "business_name": "New Food Unit",
    "district": "Bengaluru Urban",
    "pin_code": "560058",
    "business_type": "Food Processing",
    "source": "USER_INTAKE"
  }'
```

Dashboard:

```bash
curl http://127.0.0.1:8000/api/dashboard/KA-BLRU-560058-000001
```

Risk calculation:

```bash
curl -X POST http://127.0.0.1:8000/api/risk/calculate \
  -H "Content-Type: application/json" \
  -d '{"ubid": "KA-BLRU-560058-000001"}'
```

Recommendations:

```bash
curl -X POST http://127.0.0.1:8000/api/recommendations/business \
  -H "Content-Type: application/json" \
  -d '{
    "business_type": "Food Processing",
    "district": "Bengaluru Urban",
    "employees": 18,
    "uses_machinery": true,
    "handles_food": true,
    "pollution_category": "orange"
  }'
```

Chat:

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I want to start a food processing business in Bengaluru with 20 employees"}'
```

## Frontend Compatibility Endpoints

For the existing `ubid-neo-glow` UI (built against an earlier draft API), the
backend also exposes these flat-prefix routes that proxy onto the same
in-memory dataset:

```bash
curl http://127.0.0.1:8000/stats
curl "http://127.0.0.1:8000/matches?tier=HUMAN_REVIEW&limit=50"
curl http://127.0.0.1:8000/registry
curl -X POST http://127.0.0.1:8000/matches/1/approve \
  -H "Content-Type: application/json" -d '{"reviewer_id":"demo"}'
curl -X POST http://127.0.0.1:8000/matches/1/reject \
  -H "Content-Type: application/json" -d '{"reviewer_id":"demo"}'
curl -X POST http://127.0.0.1:8000/upload \
  -F "dept_a=@./data/raw/shop_establishments.csv" \
  -F "dept_b=@./data/raw/factories_act_registrations.csv"
```

`POST /upload` saves the CSVs under `DATA_DIR/raw/` and reloads the
repository. The deterministic match pipeline runs against the synthetic
dataset already shipped under `data/`; the upload endpoint is wired so the
frontend's "Run pipeline" action shows a meaningful tier breakdown.

## Frontend Integration Contract

- All endpoints return JSON and keep response bodies machine-readable.
- The frontend should use `/api/data/sources` to display dataset readiness.
- Entity resolution and UBID generation are confirmation-aware. The frontend should surface `needs_confirmation` and `confirmation_question`.
- Chat responses always include `structured_output`, `llm_used`, and `fallback_used`.
- Ground-truth columns from synthetic evaluation files are never exposed in public API payloads.

## Known MVP Limitations

- Confirmation actions are kept in memory and do not persist across process restarts.
- CSVs are loaded into pandas in memory; there is no persistent SQLite layer in this MVP.
- Chat intent extraction uses lightweight heuristics before optional LLM phrasing.
- Recommendation logic is rule-driven with deterministic fallbacks, not a legal compliance engine.

## Replacing Synthetic Data Later

1. Export real department data into CSVs matching the expected domains.
2. Preserve source record IDs and hashed identifiers where possible.
3. Update the normalization logic in `app/data/normalizer.py` if department field names change.
4. Add new file aliases in `app/data/loader.py` if production filenames differ.
5. Move confirmation and registry mutation flows from in-memory state into SQLite or another transactional store.
