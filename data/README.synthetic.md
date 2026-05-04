# UBID Synthetic Data Package - Enhanced

This package contains synthetic, Karnataka-style datasets for a UBID / entity-resolution prototype.
It is designed to look and behave like messy government department data without using real business or personal data.

## Why this exists

Your UBID prototype needs to show that one real-world business can appear differently across Shop Establishment, Factories Act, Labour, KSPCB, BBMP, GST, and Udyam/MSME records. This package gives you that mess:

- spelling variants: `M/S`, `Pvt. Ltd.`, dropped characters, abbreviations
- address variants: `Bengaluru`, `Bangalore`, `B'luru`, missing PINs, PIN drift
- missing identifiers: some rows lack PAN/GSTIN/phone
- duplicate-looking businesses: hard negatives in same PIN and category
- event stream: renewals, inspections, complaints, tax filing, deregistration
- computed UBID registry, match candidates, risk scores, review queue, dashboard rows

## Dataset size

- Synthetic entities: 325
- Source records: 1223
- UBIDs: 325
- Candidate pairs: 1443
- Human-review pairs: 640
- Compliance events: 1583

## Folder layout

```txt
raw/
  shop_establishments.csv
  factories_act_registrations.csv
  kspcb_consent_register.csv
  labour_registrations.csv
  bbmp_trade_licenses.csv
  gst_taxpayer_records.csv
  udyam_msme_records.csv
  source_records_all_departments.csv
  ground_truth_entities.csv

processed/
  normalized_business_records.csv
  ubid_registry.csv
  source_to_ubid_links.csv
  candidate_match_pairs.csv
  human_review_queue.csv
  auto_link_candidates.csv
  no_match_candidates.csv
  risk_assessment.csv
  dashboard_mock.csv
  recommendation_rules.csv

events/
  compliance_events.csv

samples/
  api_samples.json
  business_intake_examples.jsonl

schemas/
  *.schema.json

code/
  generate_ubid_synthetic_data.py
```

## Important demo warning

`entity_id_ground_truth` is included so you can evaluate matching accuracy. Do not show it in the UI. In a real system, ground truth does not exist. That is the whole problem, because apparently departments are allergic to shared identifiers.

## Matching logic

Candidate pair score follows the pitch logic:

```txt
name similarity       30%
address similarity    25%
PAN/GSTIN/Udyam       35%
phone                 10%
```

Decision thresholds:

```txt
>= 85   AUTO_LINK
60-84   HUMAN_REVIEW
< 60    NO_MATCH
```

## Use in backend

Start with:

```python
import pandas as pd
records = pd.read_csv("raw/source_records_all_departments.csv")
registry = pd.read_csv("processed/ubid_registry.csv")
pairs = pd.read_csv("processed/candidate_match_pairs.csv")
risk = pd.read_csv("processed/risk_assessment.csv")
```

Frontend dashboard should consume:

```txt
processed/dashboard_mock.csv
processed/risk_assessment.csv
processed/ubid_registry.csv
samples/api_samples.json
```

## Regenerate

```bash
cd ubid_synthetic_data_enhanced
python code/generate_ubid_synthetic_data.py
```

Change `make_entities(325)` in the script if you want more rows.
