# Data Dictionary

## raw/source_records_all_departments.csv

Unified source table across all department files.

- source_record_id: department-specific synthetic licence/record number
- source_system: SHOP, FACTORY, KSPCB, LABOUR, BBMP, GST, UDYAM
- business_name: messy/raw name as seen in source registry
- trade_name: optional alternate business/trade name
- owner_name_masked: synthetic masked owner/occupier label
- address: messy/raw address
- district, district_code, pin_code, ward, zone: geography fields
- business_type: business domain such as Food Processing or Machine Tools
- business_category: Manufacturing, Service, Retail
- nic_code: synthetic NIC-like activity code
- pollution_category: Green, Orange, Red
- pan_hash, gstin_hash, udyam_hash: fake hashed-like identifiers, not real identifiers
- phone, email: synthetic contact fields, often blank
- registration_date, last_event_date, status: lifecycle signals
- data_quality_notes: missing identifiers, PIN drift, etc.
- entity_id_ground_truth: evaluation-only synthetic true entity ID

## processed/ubid_registry.csv

Canonical UBID registry output.

- ubid: generated ID like KA-BLRU-560058-000001
- canonical_business_name: selected canonical name
- canonical_address: selected canonical address
- activity_status: ACTIVE, DORMANT, CLOSED inferred from events
- confidence: confidence in UBID resolution
- source_record_count: number of linked source records
- linked_departments: pipe-delimited source systems
- audit_policy: reminder of privacy/review policy

## processed/candidate_match_pairs.csv

Pairwise entity-resolution candidates.

- left/right_*: records being compared
- match_score: 0-100 weighted score
- decision: AUTO_LINK, HUMAN_REVIEW, NO_MATCH
- name_score, address_score, identifier_score, phone_score: evidence breakdown
- same_entity_ground_truth: evaluation flag only
- explanation: human-readable reason

## processed/risk_assessment.csv

Dashboard/compliance risk scoring.

- risk_score: 0-100
- risk_level: Low, Medium, High
- risk_reasons: pipe-delimited explainable risk reasons
- activity_status: ACTIVE, DORMANT, CLOSED

## processed/recommendation_rules.csv

Rule table for your AI/backend recommendation engine.

- business_type
- required_registrations
- risk_flags
- primary_departments
