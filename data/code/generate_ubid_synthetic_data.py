#!/usr/bin/env python3
"""
Generate synthetic, Karnataka-style UBID/entity-resolution demo datasets.
No real personal/business data is used. The data is deliberately messy to test matching:
- name variants, abbreviations, typos
- partial/missing PAN/GSTIN/phone fields
- address variations and PIN drift
- stale/expired compliance events
- hard-negative lookalikes in the same PIN and business category
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
import re
import string
from collections import defaultdict
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path

SEED = 260504
random.seed(SEED)
TODAY = date(2026, 5, 4)

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "raw"
PROCESSED_DIR = BASE_DIR / "processed"
EVENTS_DIR = BASE_DIR / "events"
SCHEMAS_DIR = BASE_DIR / "schemas"
SAMPLES_DIR = BASE_DIR / "samples"
DOCS_DIR = BASE_DIR / "docs"
for d in [RAW_DIR, PROCESSED_DIR, EVENTS_DIR, SCHEMAS_DIR, SAMPLES_DIR, DOCS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

DISTRICTS = [
    ("Bengaluru Urban", "BLRU", [
        ("560001", "MG Road", "East", "Ward-111"),
        ("560024", "Hebbal", "Yelahanka", "Ward-021"),
        ("560029", "BTM Layout", "South", "Ward-176"),
        ("560034", "Koramangala", "South-East", "Ward-151"),
        ("560037", "Whitefield", "Mahadevapura", "Ward-085"),
        ("560043", "Kalyan Nagar", "East", "Ward-025"),
        ("560058", "Peenya Industrial Area", "Dasarahalli", "Ward-038"),
        ("560059", "Rajajinagar Industrial Suburb", "West", "Ward-067"),
        ("560064", "Yelahanka", "Yelahanka", "Ward-004"),
        ("560066", "Whitefield Main Road", "Mahadevapura", "Ward-083"),
        ("560068", "Bommanahalli", "South", "Ward-175"),
        ("560076", "Bannerghatta Road", "South", "Ward-177"),
        ("560078", "Jayanagar", "South", "Ward-168"),
        ("560085", "Banashankari", "South", "Ward-182"),
        ("560100", "Electronic City", "Bommanahalli", "Ward-192"),
        ("560102", "HSR Layout", "Bommanahalli", "Ward-174"),
    ]),
    ("Bengaluru Rural", "BLRR", [
        ("562110", "Devanahalli", "Bengaluru Rural", "Ward-R01"),
        ("562114", "Hoskote", "Bengaluru Rural", "Ward-R04"),
        ("562157", "Bagalur", "Bengaluru Rural", "Ward-R07"),
        ("561203", "Doddaballapura", "Bengaluru Rural", "Ward-R09"),
    ]),
    ("Mysuru", "MYS", [
        ("570001", "Devaraja Mohalla", "Central", "Ward-M01"),
        ("570016", "Hebbal Industrial Area", "North", "Ward-M21"),
        ("570018", "Nanjangud Road", "South", "Ward-M32"),
    ]),
    ("Tumakuru", "TUM", [
        ("572101", "BH Road", "Tumakuru", "Ward-T01"),
        ("572106", "Antharasanahalli Industrial Area", "Tumakuru", "Ward-T12"),
    ]),
]

BUSINESS_TYPES = [
    {
        "type": "Food Processing",
        "nic": "1030",
        "category": "Manufacturing",
        "pollution": "Orange",
        "keywords": ["Foods", "Agro", "Snacks", "Bakery", "Milling", "Spices"],
        "dept_probs": {"SHOP": .78, "FACTORY": .46, "KSPCB": .62, "LABOUR": .52, "BBMP": .50, "GST": .76, "UDYAM": .55},
    },
    {
        "type": "Restaurant / Cafe",
        "nic": "5610",
        "category": "Service",
        "pollution": "Green",
        "keywords": ["Cafe", "Kitchen", "Biryani", "Meals", "Dine", "Bites"],
        "dept_probs": {"SHOP": .90, "FACTORY": .04, "KSPCB": .12, "LABOUR": .34, "BBMP": .88, "GST": .67, "UDYAM": .30},
    },
    {
        "type": "Machine Tools",
        "nic": "2819",
        "category": "Manufacturing",
        "pollution": "Orange",
        "keywords": ["Tools", "Machining", "Precision", "Works", "CNC", "Industries"],
        "dept_probs": {"SHOP": .58, "FACTORY": .74, "KSPCB": .68, "LABOUR": .65, "BBMP": .28, "GST": .80, "UDYAM": .61},
    },
    {
        "type": "Textile / Garments",
        "nic": "1410",
        "category": "Manufacturing",
        "pollution": "Green",
        "keywords": ["Textiles", "Garments", "Fashions", "Apparels", "Stitch", "Wear"],
        "dept_probs": {"SHOP": .78, "FACTORY": .52, "KSPCB": .30, "LABOUR": .64, "BBMP": .48, "GST": .74, "UDYAM": .58},
    },
    {
        "type": "Electronics Assembly",
        "nic": "2610",
        "category": "Manufacturing",
        "pollution": "Orange",
        "keywords": ["Electronics", "Circuits", "Devices", "Systems", "Components", "Tech"],
        "dept_probs": {"SHOP": .55, "FACTORY": .70, "KSPCB": .56, "LABOUR": .52, "BBMP": .34, "GST": .86, "UDYAM": .60},
    },
    {
        "type": "Logistics / Warehouse",
        "nic": "5210",
        "category": "Service",
        "pollution": "Green",
        "keywords": ["Logistics", "Warehouse", "Cargo", "Supply", "Trans", "Stores"],
        "dept_probs": {"SHOP": .64, "FACTORY": .08, "KSPCB": .10, "LABOUR": .50, "BBMP": .48, "GST": .82, "UDYAM": .42},
    },
    {
        "type": "Plastic Moulding",
        "nic": "2220",
        "category": "Manufacturing",
        "pollution": "Red",
        "keywords": ["Plastics", "Moulding", "Polymers", "Injection", "Mold", "Packaging"],
        "dept_probs": {"SHOP": .42, "FACTORY": .82, "KSPCB": .84, "LABOUR": .70, "BBMP": .18, "GST": .78, "UDYAM": .66},
    },
    {
        "type": "Chemical Blending",
        "nic": "2029",
        "category": "Manufacturing",
        "pollution": "Red",
        "keywords": ["Chem", "Solvents", "Coatings", "Resins", "Industrial", "Labs"],
        "dept_probs": {"SHOP": .34, "FACTORY": .76, "KSPCB": .94, "LABOUR": .58, "BBMP": .12, "GST": .74, "UDYAM": .55},
    },
    {
        "type": "Pharmacy / Medical Retail",
        "nic": "4772",
        "category": "Retail",
        "pollution": "Green",
        "keywords": ["Pharma", "Medical", "Health", "Clinic", "Meds", "Care"],
        "dept_probs": {"SHOP": .92, "FACTORY": .02, "KSPCB": .02, "LABOUR": .20, "BBMP": .72, "GST": .68, "UDYAM": .28},
    },
    {
        "type": "Printing / Packaging",
        "nic": "1811",
        "category": "Manufacturing",
        "pollution": "Orange",
        "keywords": ["Print", "Printers", "Packaging", "Labels", "Graphics", "Press"],
        "dept_probs": {"SHOP": .62, "FACTORY": .44, "KSPCB": .54, "LABOUR": .38, "BBMP": .40, "GST": .76, "UDYAM": .52},
    },
]

FIRST_NAMES = [
    "Ravi", "Sharma", "Nandi", "Kaveri", "Sri", "Vijaya", "Bharath", "Aarohi", "Nisarga", "Aditya",
    "Sahana", "Meghana", "Prakruthi", "Ananya", "Veda", "Varun", "Asha", "Naveen", "Harsha", "Siddhi",
    "Mysore", "Bangalore", "Deccan", "Srinidhi", "Ganesh", "Lakshmi", "Omkar", "Sree", "Navya", "Udupi",
]
LEGAL_SUFFIXES = ["Pvt Ltd", "LLP", "Enterprises", "Industries", "Traders", "Works", "Associates", "Solutions", "Company", "Co"]
ROAD_PARTS = ["1st Cross", "2nd Main", "3rd Phase", "Industrial Layout", "Service Road", "Main Road", "Near Bus Stop", "Behind Metro", "Extension", "Sector"]

DEPARTMENTS = ["SHOP", "FACTORY", "KSPCB", "LABOUR", "BBMP", "GST", "UDYAM"]
DEPT_NAMES = {
    "SHOP": "Karnataka Shops and Commercial Establishments",
    "FACTORY": "Factories, Boilers, Industrial Safety and Health",
    "KSPCB": "Karnataka State Pollution Control Board",
    "LABOUR": "Labour Department",
    "BBMP": "BBMP Trade Licence",
    "GST": "GST Taxpayer Registry",
    "UDYAM": "Udyam / MSME Registry",
}


def sha(value: str | None, prefix: str) -> str:
    if not value:
        return ""
    return f"{prefix}_" + hashlib.sha256(value.encode()).hexdigest()[:16].upper()


def fake_pan(idx: int) -> str:
    letters = ''.join(random.choice(string.ascii_uppercase) for _ in range(5))
    return f"{letters}{1000 + idx % 9000}{random.choice(string.ascii_uppercase)}"


def fake_gstin(pan: str, idx: int) -> str:
    return f"29{pan}{(idx % 9) + 1}Z{random.choice('123456789')}"


def fake_phone(idx: int) -> str:
    return str(9000000000 + ((idx * 7919 + 137) % 999999999))[:10]


def normalize_name(name: str) -> str:
    x = name.upper()
    x = re.sub(r"\b(M/S|MS|M\.S\.|PVT|PRIVATE|LTD|LIMITED|LLP|CO|COMPANY|THE)\b", " ", x)
    x = re.sub(r"[^A-Z0-9 ]+", " ", x)
    x = re.sub(r"\s+", " ", x).strip()
    return x


def normalize_address(addr: str) -> str:
    x = addr.upper()
    repl = {" ROAD": " RD", " MAIN": " MN", " CROSS": " CRS", " INDUSTRIAL": " IND", " AREA": " AREA", " BENGALURU": " BANGALORE"}
    for a, b in repl.items():
        x = x.replace(a, b)
    x = re.sub(r"[^A-Z0-9 ]+", " ", x)
    x = re.sub(r"\s+", " ", x).strip()
    return x


def sim(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio() * 100


def weighted_match_score(a: dict, b: dict) -> tuple[int, dict]:
    name_score = sim(normalize_name(a.get("business_name", "")), normalize_name(b.get("business_name", "")))
    address_score = sim(normalize_address(a.get("address", "")), normalize_address(b.get("address", "")))
    pin_bonus = 10 if a.get("pin_code") and a.get("pin_code") == b.get("pin_code") else 0
    address_score = min(100, address_score + pin_bonus)
    id_score = 0
    if a.get("pan_hash") and a.get("pan_hash") == b.get("pan_hash"):
        id_score = max(id_score, 95)
    if a.get("gstin_hash") and a.get("gstin_hash") == b.get("gstin_hash"):
        id_score = max(id_score, 100)
    if a.get("udyam_hash") and a.get("udyam_hash") == b.get("udyam_hash"):
        id_score = max(id_score, 80)
    # Partial identifier hint: same business category and same PIN gives weak signal, not real ID proof.
    if id_score == 0 and a.get("business_category") == b.get("business_category") and a.get("pin_code") == b.get("pin_code"):
        id_score = 25
    phone_score = 100 if a.get("phone") and a.get("phone") == b.get("phone") else 0
    score = round((name_score * 0.30) + (address_score * 0.25) + (id_score * 0.35) + (phone_score * 0.10))
    evidence = {
        "name_score": round(name_score, 1),
        "address_score": round(address_score, 1),
        "identifier_score": round(id_score, 1),
        "phone_score": round(phone_score, 1),
    }
    return int(score), evidence


def choose_location():
    # Bias toward Bengaluru Urban because the pitch scenario is Bengaluru Urban.
    r = random.random()
    if r < .68:
        district, code, pins = DISTRICTS[0]
    elif r < .82:
        district, code, pins = DISTRICTS[1]
    elif r < .93:
        district, code, pins = DISTRICTS[2]
    else:
        district, code, pins = DISTRICTS[3]
    pin, locality, zone, ward = random.choice(pins)
    return district, code, pin, locality, zone, ward


def make_base_name(btype: dict, idx: int) -> str:
    first = random.choice(FIRST_NAMES)
    key = random.choice(btype["keywords"])
    suffix = random.choice(LEGAL_SUFFIXES)
    # Some names naturally include business keyword; some do not.
    if random.random() < .78:
        return f"{first} {key} {suffix}"
    return f"{first} {suffix}"


def mess_name(name: str, dept: str) -> str:
    x = name
    # Introduce government registry style variants.
    if random.random() < .22:
        x = "M/S " + x
    if random.random() < .18:
        x = x.replace("Private Limited", "Pvt Ltd").replace("Pvt Ltd", "Pvt. Ltd.")
    if random.random() < .15:
        x = x.replace("Industries", "Inds").replace("Enterprises", "Entp").replace("Company", "Co")
    if random.random() < .10:
        x = x.replace("Processing", "Proc").replace("Electronics", "Elec")
    if random.random() < .08 and len(x) > 9:
        pos = random.randint(1, len(x) - 2)
        x = x[:pos] + x[pos + 1:]  # typo/drop char
    if dept in ["GST", "UDYAM"] and random.random() < .25:
        x = x.upper()
    return re.sub(r"\s+", " ", x).strip()


def make_address(locality: str, pin: str, district: str) -> str:
    no = random.randint(1, 299)
    road = random.choice(ROAD_PARTS)
    block = random.choice(["A", "B", "C", "D", "", "Plot", "Shed"])
    return f"No {no}, {block} {road}, {locality}, {district}, Karnataka - {pin}".replace("  ", " ")


def mess_address(addr: str) -> str:
    x = addr
    replacements = {
        "Bengaluru": random.choice(["Bangalore", "B'luru", "Bengaluru"]),
        "Karnataka": random.choice(["KA", "Karnataka", "K'taka"]),
        "No ": random.choice(["No. ", "#", "No ", ""]),
        "Industrial Area": random.choice(["Indl Area", "Industrial Area", "Industrial Estate"]),
        "Main Road": random.choice(["Main Rd", "Main Road", "Mn Rd"]),
        "Cross": random.choice(["Cr", "Cross", "Crs"]),
    }
    for k, v in replacements.items():
        x = x.replace(k, v)
    if random.random() < .08:
        x = re.sub(r" - \d{6}", "", x)
    return re.sub(r"\s+", " ", x).strip()


def random_date_between(start_year: int, end_year: int) -> date:
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    return start + timedelta(days=random.randint(0, (end - start).days))


def status_from_dates(last_event: date, expired: bool = False) -> str:
    age_months = (TODAY.year - last_event.year) * 12 + TODAY.month - last_event.month
    if expired or age_months > 36:
        return "CLOSED"
    if age_months > 12:
        return "DORMANT"
    return "ACTIVE"


def license_no(dept: str, district_code: str, idx: int, year: int, zone: str = "") -> str:
    if dept == "SHOP":
        return f"KAR-SHOP-{district_code}-{year}-{idx:06d}"
    if dept == "FACTORY":
        return f"KFBIS-FAC-{district_code}-{year}-{idx:06d}"
    if dept == "KSPCB":
        return f"PCB/{district_code}/{random.choice(['CTE','CTO'])}/{year}/{idx:05d}"
    if dept == "LABOUR":
        return f"LAB-KA-{district_code}-{year}-{idx:06d}"
    if dept == "BBMP":
        z = re.sub(r"[^A-Z]", "", zone.upper())[:4] or district_code
        return f"BBMP-TL-{z}-{year}-{idx:06d}"
    if dept == "GST":
        return f"GST-KA-{district_code}-{year}-{idx:06d}"
    if dept == "UDYAM":
        return f"UDYAM-KR-{district_code}-{year}-{idx:06d}"
    return f"{dept}-{idx:06d}"


def make_entities(n: int = 325):
    entities = []
    used_names = set()
    for i in range(1, n + 1):
        btype = random.choice(BUSINESS_TYPES)
        district, dcode, pin, locality, zone, ward = choose_location()
        name = make_base_name(btype, i)
        # Force some lookalike names in same PIN to create hard negatives.
        if i % 41 == 0 and entities:
            ref = random.choice(entities)
            name = ref["legal_name"].replace("Pvt Ltd", "Enterprises").replace("Industries", "Works")
            pin = ref["pin_code"]
            locality = ref["locality"]
            district = ref["district"]
            dcode = ref["district_code"]
            zone = ref["zone"]
            ward = ref["ward"]
        pan = fake_pan(i) if random.random() < .72 else ""
        gstin = fake_gstin(pan, i) if pan and random.random() < .75 else ""
        udyam_no = f"UDYAM-KR-{dcode}-{i:07d}" if random.random() < .56 else ""
        phone = fake_phone(i) if random.random() < .68 else ""
        email = f"contact{i:04d}@examplebiz.in" if random.random() < .55 else ""
        address = make_address(locality, pin, district)
        incorporation = random_date_between(2012, 2025)
        entities.append({
            "entity_id": f"ENT-{i:05d}",
            "legal_name": name,
            "trade_name": name.replace("Pvt Ltd", "").replace("LLP", "").strip(),
            "business_type": btype["type"],
            "business_category": btype["category"],
            "nic_code": btype["nic"],
            "pollution_category": btype["pollution"],
            "district": district,
            "district_code": dcode,
            "pin_code": pin,
            "locality": locality,
            "zone": zone,
            "ward": ward,
            "canonical_address": address,
            "pan_hash": sha(pan, "PAN"),
            "gstin_hash": sha(gstin, "GSTIN"),
            "udyam_hash": sha(udyam_no, "UDYAM"),
            "phone": phone,
            "email": email,
            "incorporation_date": incorporation.isoformat(),
            "employee_count": random.choice([2, 3, 4, 5, 8, 10, 12, 18, 25, 36, 52, 85, 120, 180]),
            "turnover_band_lakh": random.choice(["0-10", "10-25", "25-50", "50-100", "100-500", "500+"]),
        })
    return entities


def make_source_records(entities):
    source_records = []
    dept_rows = {d: [] for d in DEPARTMENTS}
    counter = {d: 1 for d in DEPARTMENTS}

    for e in entities:
        btype = next(x for x in BUSINESS_TYPES if x["type"] == e["business_type"])
        chosen_depts = []
        for dept, p in btype["dept_probs"].items():
            if random.random() < p:
                chosen_depts.append(dept)
        if not chosen_depts:
            chosen_depts.append("SHOP")
        # ensure entities with manufacturing often have at least two records
        if e["business_category"] == "Manufacturing" and len(chosen_depts) == 1 and random.random() < .75:
            chosen_depts.append(random.choice(["FACTORY", "KSPCB", "GST", "UDYAM"]))

        for dept in sorted(set(chosen_depts)):
            idx = counter[dept]
            counter[dept] += 1
            reg_date = random_date_between(2015, 2025)
            last_event = reg_date + timedelta(days=random.randint(30, max(40, (TODAY - reg_date).days)))
            if last_event > TODAY:
                last_event = TODAY - timedelta(days=random.randint(1, 90))
            expired = random.random() < .08
            status = status_from_dates(last_event, expired)
            # missing fields vary by department
            pan_hash = e["pan_hash"] if random.random() < {"GST": .94, "UDYAM": .75, "FACTORY": .48, "KSPCB": .45, "SHOP": .38, "LABOUR": .35, "BBMP": .30}[dept] else ""
            gst_hash = e["gstin_hash"] if random.random() < {"GST": .98, "UDYAM": .40, "FACTORY": .42, "KSPCB": .38, "SHOP": .30, "LABOUR": .26, "BBMP": .34}[dept] else ""
            udyam_hash = e["udyam_hash"] if random.random() < {"UDYAM": .98, "GST": .20, "SHOP": .12, "FACTORY": .16, "KSPCB": .10, "LABOUR": .08, "BBMP": .06}[dept] else ""
            phone = e["phone"] if random.random() < .58 else ""
            # Sometimes one department has pin drift / nearby PIN.
            pin = e["pin_code"]
            if random.random() < .045:
                same_dist_pins = [p for d, code, pins in DISTRICTS if d == e["district"] for p, *_ in pins]
                pin = random.choice(same_dist_pins)
            source_id = license_no(dept, e["district_code"], idx, reg_date.year, e["zone"])
            base = {
                "source_record_id": source_id,
                "source_system": dept,
                "source_system_name": DEPT_NAMES[dept],
                "entity_id_ground_truth": e["entity_id"],
                "business_name": mess_name(e["legal_name"], dept),
                "trade_name": mess_name(e["trade_name"], dept) if random.random() < .75 else "",
                "owner_name_masked": random.choice(["Owner A", "Owner B", "Partner 1", "Managing Partner", "Director Masked", ""]),
                "address": mess_address(e["canonical_address"]),
                "locality": e["locality"],
                "district": e["district"],
                "district_code": e["district_code"],
                "pin_code": pin,
                "ward": e["ward"],
                "zone": e["zone"],
                "business_type": e["business_type"],
                "business_category": e["business_category"],
                "nic_code": e["nic_code"],
                "pollution_category": e["pollution_category"],
                "pan_hash": pan_hash,
                "gstin_hash": gst_hash,
                "udyam_hash": udyam_hash,
                "phone": phone,
                "email": e["email"] if random.random() < .42 else "",
                "registration_date": reg_date.isoformat(),
                "last_event_date": last_event.isoformat(),
                "status": status,
                "employee_count": e["employee_count"] if random.random() < .70 else "",
                "turnover_band_lakh": e["turnover_band_lakh"] if random.random() < .46 else "",
                "ingested_at": (TODAY - timedelta(days=random.randint(0, 180))).isoformat(),
                "data_quality_notes": "",
            }
            missing = []
            for f in ["pan_hash", "gstin_hash", "phone", "email"]:
                if not base[f]:
                    missing.append(f)
            if pin != e["pin_code"]:
                missing.append("pin_drift")
            if missing:
                base["data_quality_notes"] = ";".join(missing)

            source_records.append(base)
            # Department-specific projection.
            if dept == "SHOP":
                dept_rows[dept].append({
                    "shop_license_no": source_id,
                    "establishment_name": base["business_name"],
                    "owner_name_masked": base["owner_name_masked"],
                    "address": base["address"],
                    "district": base["district"],
                    "pin_code": base["pin_code"],
                    "registration_date": base["registration_date"],
                    "renewal_due_date": (datetime.fromisoformat(base["registration_date"]).date() + timedelta(days=365 * random.choice([1, 3, 5]))).isoformat(),
                    "employee_count": base["employee_count"],
                    "status": base["status"],
                    "phone": base["phone"],
                    "pan_hash": base["pan_hash"],
                    "gstin_hash": base["gstin_hash"],
                    "source_record_id": source_id,
                    "entity_id_ground_truth": e["entity_id"],
                })
            elif dept == "FACTORY":
                dept_rows[dept].append({
                    "factory_license_no": source_id,
                    "factory_name": base["business_name"],
                    "occupier_name_masked": base["owner_name_masked"],
                    "factory_address": base["address"],
                    "district": base["district"],
                    "pin_code": base["pin_code"],
                    "industry_type": base["business_type"],
                    "nic_code": base["nic_code"],
                    "workers_count": base["employee_count"],
                    "registration_year": base["registration_date"][:4],
                    "last_inspection_date": base["last_event_date"],
                    "status": base["status"],
                    "pan_hash": base["pan_hash"],
                    "gstin_hash": base["gstin_hash"],
                    "source_record_id": source_id,
                    "entity_id_ground_truth": e["entity_id"],
                })
            elif dept == "KSPCB":
                dept_rows[dept].append({
                    "consent_no": source_id,
                    "industry_name": base["business_name"],
                    "industry_address": base["address"],
                    "district": base["district"],
                    "pin_code": base["pin_code"],
                    "industry_colour": base["pollution_category"],
                    "regional_office": random.choice(["Bengaluru North", "Bengaluru South", "Peenya", "Mysuru", "Tumakuru"]),
                    "inward_type": random.choice(["CTE", "CTO", "Renewal", "Expansion"]),
                    "inward_status": random.choice(["Approved", "Pending", "Returned for Clarification", "Rejected"]),
                    "validity_date": (TODAY + timedelta(days=random.randint(-900, 900))).isoformat(),
                    "last_event_date": base["last_event_date"],
                    "pan_hash": base["pan_hash"],
                    "gstin_hash": base["gstin_hash"],
                    "source_record_id": source_id,
                    "entity_id_ground_truth": e["entity_id"],
                })
            elif dept == "LABOUR":
                dept_rows[dept].append({
                    "labour_registration_no": source_id,
                    "establishment_name": base["business_name"],
                    "principal_employer_masked": base["owner_name_masked"],
                    "address": base["address"],
                    "district": base["district"],
                    "pin_code": base["pin_code"],
                    "worker_count": base["employee_count"],
                    "registration_date": base["registration_date"],
                    "last_return_filed_date": base["last_event_date"],
                    "status": base["status"],
                    "phone": base["phone"],
                    "pan_hash": base["pan_hash"],
                    "gstin_hash": base["gstin_hash"],
                    "source_record_id": source_id,
                    "entity_id_ground_truth": e["entity_id"],
                })
            elif dept == "BBMP":
                dept_rows[dept].append({
                    "trade_license_no": source_id,
                    "business_name": base["business_name"],
                    "trade_type": base["business_type"],
                    "address": base["address"],
                    "ward": base["ward"],
                    "zone": base["zone"],
                    "pin_code": base["pin_code"],
                    "application_status": random.choice(["Approved", "Renewal Due", "Pending Inspection", "Expired"]),
                    "valid_from": base["registration_date"],
                    "valid_to": (TODAY + timedelta(days=random.randint(-600, 730))).isoformat(),
                    "phone": base["phone"],
                    "gstin_hash": base["gstin_hash"],
                    "source_record_id": source_id,
                    "entity_id_ground_truth": e["entity_id"],
                })
            elif dept == "GST":
                dept_rows[dept].append({
                    "gst_record_id": source_id,
                    "legal_name": base["business_name"],
                    "trade_name": base["trade_name"],
                    "principal_place_address": base["address"],
                    "district": base["district"],
                    "pin_code": base["pin_code"],
                    "state_code": "29",
                    "taxpayer_type": random.choice(["Regular", "Composition", "SEZ Unit", "Casual Taxable Person"]),
                    "registration_date": base["registration_date"],
                    "gst_status": random.choice(["Active", "Cancelled", "Suspended"]) if base["status"] != "ACTIVE" else "Active",
                    "pan_hash": base["pan_hash"],
                    "gstin_hash": base["gstin_hash"],
                    "source_record_id": source_id,
                    "entity_id_ground_truth": e["entity_id"],
                })
            elif dept == "UDYAM":
                dept_rows[dept].append({
                    "udyam_record_id": source_id,
                    "enterprise_name": base["business_name"],
                    "organisation_type": random.choice(["Proprietorship", "Partnership", "Private Limited", "LLP"]),
                    "activity_type": base["business_category"],
                    "nic_code": base["nic_code"],
                    "district": base["district"],
                    "pin_code": base["pin_code"],
                    "employment_count": base["employee_count"],
                    "registration_date": base["registration_date"],
                    "status": base["status"],
                    "pan_hash": base["pan_hash"],
                    "udyam_hash": base["udyam_hash"],
                    "source_record_id": source_id,
                    "entity_id_ground_truth": e["entity_id"],
                })
    return source_records, dept_rows


def make_ubid_registry(entities, source_records):
    by_entity = defaultdict(list)
    for r in source_records:
        by_entity[r["entity_id_ground_truth"]].append(r)
    registry = []
    links = []
    for idx, e in enumerate(entities, 1):
        rows = by_entity[e["entity_id"]]
        if not rows:
            continue
        ubid = f"KA-{e['district_code']}-{e['pin_code']}-{idx:06d}"
        events = [datetime.fromisoformat(r["last_event_date"]).date() for r in rows if r.get("last_event_date")]
        last_event = max(events) if events else datetime.fromisoformat(e["incorporation_date"]).date()
        activity_status = status_from_dates(last_event, expired=all(r["status"] == "CLOSED" for r in rows))
        confidence = min(99, 62 + 5 * len(rows) + (12 if any(r.get("pan_hash") for r in rows) else 0) + (12 if any(r.get("gstin_hash") for r in rows) else 0))
        registry.append({
            "ubid": ubid,
            "canonical_business_name": e["legal_name"],
            "canonical_address": e["canonical_address"],
            "district": e["district"],
            "pin_code": e["pin_code"],
            "business_type": e["business_type"],
            "business_category": e["business_category"],
            "activity_status": activity_status,
            "confidence": confidence,
            "source_record_count": len(rows),
            "linked_departments": "|".join(sorted({r["source_system"] for r in rows})),
            "created_at": (TODAY - timedelta(days=random.randint(0, 60))).isoformat(),
            "last_activity_date": last_event.isoformat(),
            "audit_policy": "append_only; raw identifiers hashed; human-review for score 60-84",
            "entity_id_ground_truth": e["entity_id"],
        })
        for r in rows:
            links.append({
                "ubid": ubid,
                "source_system": r["source_system"],
                "source_record_id": r["source_record_id"],
                "link_type": "AUTO_LINK" if confidence >= 85 else "HUMAN_APPROVED",
                "link_confidence": confidence,
                "linked_at": (TODAY - timedelta(days=random.randint(0, 45))).isoformat(),
                "entity_id_ground_truth": e["entity_id"],
            })
    return registry, links


def make_candidates(source_records, max_pairs=3600):
    by_block = defaultdict(list)
    for r in source_records:
        # Block by PIN + first normalized token, fallback by PIN + category.
        n = normalize_name(r["business_name"])
        token = n.split()[0] if n else r["business_category"][:4]
        by_block[(r["pin_code"], token[:4])].append(r)
        by_block[(r["pin_code"], r["business_category"][:4])].append(r)

    seen = set()
    candidates = []

    def add_pair(a, b):
        if a["source_record_id"] == b["source_record_id"] or a["source_system"] == b["source_system"]:
            return
        key = tuple(sorted([a["source_record_id"], b["source_record_id"]]))
        if key in seen:
            return
        seen.add(key)
        score, evidence = weighted_match_score(a, b)
        decision = "AUTO_LINK" if score >= 85 else "HUMAN_REVIEW" if score >= 60 else "NO_MATCH"
        candidates.append({
            "candidate_pair_id": f"PAIR-{len(candidates)+1:06d}",
            "left_source_system": a["source_system"],
            "left_record_id": a["source_record_id"],
            "left_business_name": a["business_name"],
            "right_source_system": b["source_system"],
            "right_record_id": b["source_record_id"],
            "right_business_name": b["business_name"],
            "pin_code": a["pin_code"] if a["pin_code"] == b["pin_code"] else f"{a['pin_code']}|{b['pin_code']}",
            "match_score": score,
            "decision": decision,
            "name_score": evidence["name_score"],
            "address_score": evidence["address_score"],
            "identifier_score": evidence["identifier_score"],
            "phone_score": evidence["phone_score"],
            "same_entity_ground_truth": a["entity_id_ground_truth"] == b["entity_id_ground_truth"],
            "explanation": explain_match(a, b, score, evidence),
        })

    # True pairs first.
    by_entity = defaultdict(list)
    for r in source_records:
        by_entity[r["entity_id_ground_truth"]].append(r)
    for rows in by_entity.values():
        if len(rows) >= 2:
            rows = rows[:]
            random.shuffle(rows)
            for i in range(min(len(rows) - 1, 5)):
                add_pair(rows[i], rows[i+1])
            # sometimes cross compare non-adjacent
            if len(rows) > 3 and random.random() < .55:
                add_pair(rows[0], rows[-1])

    # Hard negatives / ambiguous pairs by same PIN/category.
    blocks = list(by_block.values())
    random.shuffle(blocks)
    for rows in blocks:
        if len(rows) < 2:
            continue
        for _ in range(min(8, len(rows))):
            a, b = random.sample(rows, 2)
            if a["entity_id_ground_truth"] != b["entity_id_ground_truth"]:
                # More useful if names are somewhat close or same category.
                if sim(normalize_name(a["business_name"]), normalize_name(b["business_name"])) > 35 or a["business_category"] == b["business_category"]:
                    add_pair(a, b)
            if len(candidates) >= max_pairs:
                break
        if len(candidates) >= max_pairs:
            break
    # Sort by score descending for review/demo usefulness.
    candidates.sort(key=lambda x: x["match_score"], reverse=True)
    # Reassign IDs after sorting.
    for i, c in enumerate(candidates, 1):
        c["candidate_pair_id"] = f"PAIR-{i:06d}"
    return candidates[:max_pairs]


def explain_match(a, b, score, e):
    reasons = []
    if e["name_score"] >= 80:
        reasons.append(f"high name similarity ({e['name_score']})")
    elif e["name_score"] >= 55:
        reasons.append(f"medium name similarity ({e['name_score']})")
    else:
        reasons.append(f"weak name similarity ({e['name_score']})")
    if e["address_score"] >= 75:
        reasons.append(f"similar address/PIN ({e['address_score']})")
    if e["identifier_score"] >= 80:
        reasons.append("strong hashed PAN/GSTIN/Udyam match")
    elif e["identifier_score"] == 0:
        reasons.append("no shared identifier available")
    if e["phone_score"] == 100:
        reasons.append("same phone number")
    if score >= 85:
        verdict = "auto-link candidate"
    elif score >= 60:
        verdict = "requires human review"
    else:
        verdict = "reject/no-match candidate"
    return verdict + ": " + "; ".join(reasons)


def make_events(registry, links, source_records):
    source_by_id = {r["source_record_id"]: r for r in source_records}
    events = []
    event_types = ["RENEWAL", "INSPECTION", "TAX_FILING", "COMPLAINT", "CONSENT_APPROVAL", "ADDRESS_UPDATE", "DEREGISTRATION"]
    event_id = 1
    by_ubid = defaultdict(list)
    for l in links:
        by_ubid[l["ubid"]].append(l)

    for reg in registry:
        rows = by_ubid[reg["ubid"]]
        count = random.randint(2, 8)
        if reg["activity_status"] == "ACTIVE":
            base_start = TODAY - timedelta(days=random.randint(10, 340))
        elif reg["activity_status"] == "DORMANT":
            base_start = TODAY - timedelta(days=random.randint(380, 1000))
        else:
            base_start = TODAY - timedelta(days=random.randint(1100, 2200))
        for _ in range(count):
            link = random.choice(rows)
            src = source_by_id[link["source_record_id"]]
            dept = src["source_system"]
            possible = ["RENEWAL", "INSPECTION", "TAX_FILING", "COMPLAINT", "ADDRESS_UPDATE"]
            if dept == "KSPCB":
                possible += ["CONSENT_APPROVAL", "INSPECTION"]
            if reg["activity_status"] == "CLOSED" and random.random() < .25:
                possible += ["DEREGISTRATION"]
            typ = random.choice(possible)
            ev_date = base_start - timedelta(days=random.randint(0, 850)) if random.random() < .45 else base_start + timedelta(days=random.randint(0, 90))
            if ev_date > TODAY:
                ev_date = TODAY - timedelta(days=random.randint(1, 30))
            outcome = random.choice(["OK", "NOTICE", "PENDING", "APPROVED", "EXPIRED", "RESOLVED"])
            if typ == "COMPLAINT":
                outcome = random.choice(["OPEN", "RESOLVED", "NOTICE"])
            if typ == "DEREGISTRATION":
                outcome = "CLOSED"
            events.append({
                "event_id": f"EVT-{event_id:07d}",
                "ubid": reg["ubid"],
                "source_system": dept,
                "source_record_id": link["source_record_id"],
                "event_type": typ,
                "event_date": ev_date.isoformat(),
                "event_outcome": outcome,
                "event_note": event_note(typ, outcome),
            })
            event_id += 1
    events.sort(key=lambda x: x["event_date"], reverse=True)
    return events


def event_note(typ, outcome):
    notes = {
        "RENEWAL": "licence/registration renewal event captured",
        "INSPECTION": "department inspection or site verification event",
        "TAX_FILING": "tax return or filing activity signal",
        "COMPLAINT": "citizen/department complaint signal",
        "CONSENT_APPROVAL": "pollution consent application/approval signal",
        "ADDRESS_UPDATE": "address correction or amendment signal",
        "DEREGISTRATION": "closure/deregistration signal",
    }
    return f"{notes.get(typ, 'compliance activity')} - {outcome}"


def make_risk_scores(registry, links, events):
    events_by_ubid = defaultdict(list)
    for e in events:
        events_by_ubid[e["ubid"]].append(e)
    link_depts = defaultdict(set)
    for l in links:
        link_depts[l["ubid"]].add(l["source_system"])
    risks = []
    for reg in registry:
        ubid = reg["ubid"]
        evs = events_by_ubid[ubid]
        last_date = max((datetime.fromisoformat(e["event_date"]).date() for e in evs), default=TODAY - timedelta(days=9999))
        months = (TODAY.year - last_date.year) * 12 + TODAY.month - last_date.month
        depts = link_depts[ubid]
        score = 0
        reasons = []
        if months > 36:
            score += 40; reasons.append("No compliance activity for more than 36 months")
        elif months > 18:
            score += 25; reasons.append("No compliance activity for more than 18 months")
        elif months > 12:
            score += 15; reasons.append("No compliance activity in the last 12 months")
        if "KSPCB" not in depts and reg["business_category"] == "Manufacturing":
            score += 20; reasons.append("Manufacturing business has no linked KSPCB consent record")
        if "FACTORY" not in depts and reg["business_category"] == "Manufacturing":
            score += 18; reasons.append("Manufacturing business has no linked Factories Act record")
        if "GST" not in depts:
            score += 10; reasons.append("No linked GST registry signal")
        complaints = [e for e in evs if e["event_type"] == "COMPLAINT" and e["event_outcome"] in ["OPEN", "NOTICE"]]
        if complaints:
            score += min(25, len(complaints) * 8); reasons.append(f"{len(complaints)} unresolved/notice complaint signals")
        if reg["activity_status"] == "CLOSED":
            score += 30; reasons.append("Closed/deregistered or long-inactive status")
        elif reg["activity_status"] == "DORMANT":
            score += 15; reasons.append("Dormant status inferred from event stream")
        score = max(0, min(100, score + random.randint(-4, 6)))
        level = "Low" if score < 35 else "Medium" if score < 70 else "High"
        if not reasons:
            reasons = ["Recent compliance activity and sufficient cross-department linkage"]
        risks.append({
            "ubid": ubid,
            "business_name": reg["canonical_business_name"],
            "risk_score": score,
            "risk_level": level,
            "activity_status": reg["activity_status"],
            "last_activity_date": last_date.isoformat(),
            "linked_departments": "|".join(sorted(depts)),
            "risk_reasons": " | ".join(reasons),
        })
    risks.sort(key=lambda r: r["risk_score"], reverse=True)
    return risks


def make_recommendations_rules():
    rows = [
        {"business_type": "Food Processing", "required_registrations": "Shop Establishment|GST|FSSAI|KSPCB if processing/effluent|Labour if employees", "risk_flags": "KSPCB consent missing|FSSAI missing|duplicate names across PIN", "primary_departments": "SHOP|GST|KSPCB|LABOUR"},
        {"business_type": "Restaurant / Cafe", "required_registrations": "Shop Establishment|BBMP Trade Licence|GST if threshold met|FSSAI", "risk_flags": "trade licence expired|complaint open|GST cancelled", "primary_departments": "SHOP|BBMP|GST"},
        {"business_type": "Machine Tools", "required_registrations": "Factories Act|KSPCB|Labour|GST|Udyam optional", "risk_flags": "no inspection in 18 months|factory record missing|KSPCB missing", "primary_departments": "FACTORY|KSPCB|LABOUR|GST"},
        {"business_type": "Textile / Garments", "required_registrations": "Shop Establishment|Factories Act if manufacturing unit|Labour|GST|Udyam", "risk_flags": "worker count missing|labour return stale|duplicate trade names", "primary_departments": "SHOP|FACTORY|LABOUR|GST|UDYAM"},
        {"business_type": "Electronics Assembly", "required_registrations": "Factories Act|KSPCB depending process|Labour|GST|Udyam", "risk_flags": "manufacturing without factory licence|no KSPCB signal", "primary_departments": "FACTORY|KSPCB|LABOUR|GST"},
        {"business_type": "Logistics / Warehouse", "required_registrations": "Shop Establishment|GST|Labour if employees|BBMP trade licence where applicable", "risk_flags": "warehouse active but no shop licence|address mismatch", "primary_departments": "SHOP|GST|LABOUR|BBMP"},
        {"business_type": "Plastic Moulding", "required_registrations": "Factories Act|KSPCB|Labour|GST|Udyam", "risk_flags": "Red category without KSPCB|inspection stale|factory licence expired", "primary_departments": "FACTORY|KSPCB|LABOUR|GST"},
        {"business_type": "Chemical Blending", "required_registrations": "Factories Act|KSPCB|Labour|GST|hazard handling if applicable", "risk_flags": "Red category|KSPCB consent expired|complaint open", "primary_departments": "FACTORY|KSPCB|LABOUR|GST"},
        {"business_type": "Pharmacy / Medical Retail", "required_registrations": "Shop Establishment|BBMP Trade Licence|GST|drug licence outside UBID scope", "risk_flags": "trade licence expired|GST suspended", "primary_departments": "SHOP|BBMP|GST"},
        {"business_type": "Printing / Packaging", "required_registrations": "Shop Establishment|Factories Act depending scale|KSPCB depending inks/effluent|GST", "risk_flags": "KSPCB missing for printing unit|duplicate address", "primary_departments": "SHOP|FACTORY|KSPCB|GST"},
    ]
    return rows


def make_api_samples(registry, risks, candidates):
    sample_reg = registry[0]
    risk = next(r for r in risks if r["ubid"] == sample_reg["ubid"])
    pair = next((c for c in candidates if c["decision"] == "HUMAN_REVIEW"), candidates[0])
    return {
        "post_api_chat": {
            "request": {"message": "I want to start a food processing business in Peenya, Bengaluru with 18 workers"},
            "response": {
                "reply": "For a food processing business in Peenya, you likely need Shop Establishment, GST, FSSAI, Labour registration if workers are employed, and KSPCB consent depending on processing/effluent.",
                "structured_output": {
                    "business_type": "Food Processing",
                    "location": "Peenya Industrial Area, Bengaluru Urban",
                    "recommended_departments": ["SHOP", "GST", "KSPCB", "LABOUR"],
                    "required_registrations": ["Shop Establishment", "GST", "FSSAI", "KSPCB consent if applicable", "Labour registration if employees are hired"],
                    "next_steps": ["Confirm business name", "Check duplicate records", "Collect hashed PAN/GSTIN", "Generate or link UBID"],
                    "risk_flags": ["KSPCB may be required", "Duplicate record possible if already registered"],
                    "confidence": 84,
                },
                "needs_confirmation": True,
                "confirmation_question": "Should I check existing department records before creating a new UBID?",
            },
        },
        "post_api_resolve": {
            "request": {"records": [pair["left_record_id"], pair["right_record_id"]]},
            "response": pair,
        },
        "post_api_ubid_generate": {
            "request": {"business_name": sample_reg["canonical_business_name"], "pin_code": sample_reg["pin_code"]},
            "response": {
                "ubid": sample_reg["ubid"],
                "status": sample_reg["activity_status"],
                "confidence": sample_reg["confidence"],
                "linked_records": sample_reg["source_record_count"],
            },
        },
        "get_api_dashboard_ubid": {
            "request_path": f"/api/dashboard/{sample_reg['ubid']}",
            "response": {
                "ubid": sample_reg["ubid"],
                "business_name": sample_reg["canonical_business_name"],
                "status": sample_reg["activity_status"],
                "progress": {
                    "identity_verified": sample_reg["confidence"] >= 85,
                    "department_records_linked": sample_reg["source_record_count"] >= 2,
                    "human_review_required": sample_reg["confidence"] < 85,
                    "compliance_checked": True,
                },
                "risk_score": risk["risk_score"],
                "risk_level": risk["risk_level"],
                "matched_departments": sample_reg["linked_departments"].split("|"),
                "risk_reasons": risk["risk_reasons"].split(" | "),
            },
        },
    }


def make_intake_examples(rules):
    examples = []
    locs = ["Peenya", "Whitefield", "Electronic City", "HSR Layout", "Mysuru", "Tumakuru", "Devanahalli"]
    sizes = [3, 8, 12, 18, 45, 90]
    for i, r in enumerate(rules, 1):
        for difficulty in ["easy", "edge"]:
            loc = random.choice(locs)
            employees = random.choice(sizes)
            prompt = f"I want to start a {r['business_type'].lower()} business in {loc} with {employees} workers"
            if difficulty == "edge":
                prompt += random.choice([
                    ", but I already have GST from another address",
                    ", and my old shop licence may be expired",
                    ", but I do not have PAN details right now",
                    ", and we may shift from 560058 to 560059",
                ])
            examples.append({
                "example_id": f"INTAKE-{len(examples)+1:03d}",
                "difficulty": difficulty,
                "user_message": prompt,
                "expected_business_type": r["business_type"],
                "expected_departments": r["primary_departments"].split("|"),
                "expected_confirmation_required": difficulty == "edge",
                "expected_risk_flags": r["risk_flags"].split("|"),
            })
    return examples


def write_csv(path: Path, rows: list[dict]):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    # stable field order from first row plus any extras
    fields = list(rows[0].keys())
    for r in rows[1:]:
        for k in r.keys():
            if k not in fields:
                fields.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def write_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def schema_for(name: str, rows: list[dict], description: str):
    props = {}
    sample = rows[0] if rows else {}
    for k, v in sample.items():
        typ = "string"
        if isinstance(v, bool):
            typ = "boolean"
        elif isinstance(v, int):
            typ = "integer"
        elif isinstance(v, float):
            typ = "number"
        props[k] = {"type": typ}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": name,
        "description": description,
        "type": "object",
        "properties": props,
        "additionalProperties": True,
    }


def main():
    entities = make_entities(325)
    source_records, dept_rows = make_source_records(entities)
    registry, links = make_ubid_registry(entities, source_records)
    candidates = make_candidates(source_records)
    events = make_events(registry, links, source_records)
    risks = make_risk_scores(registry, links, events)
    rules = make_recommendations_rules()
    review_queue = [c for c in candidates if c["decision"] == "HUMAN_REVIEW"]
    auto_links = [c for c in candidates if c["decision"] == "AUTO_LINK"]
    no_match = [c for c in candidates if c["decision"] == "NO_MATCH"]

    # Processed normalized record table.
    normalized = []
    for r in source_records:
        normalized.append({
            "source_record_id": r["source_record_id"],
            "source_system": r["source_system"],
            "business_name_raw": r["business_name"],
            "business_name_normalized": normalize_name(r["business_name"]),
            "address_raw": r["address"],
            "address_normalized": normalize_address(r["address"]),
            "district": r["district"],
            "pin_code": r["pin_code"],
            "business_type": r["business_type"],
            "business_category": r["business_category"],
            "pan_hash_present": bool(r["pan_hash"]),
            "gstin_hash_present": bool(r["gstin_hash"]),
            "phone_present": bool(r["phone"]),
            "blocking_key_pin_category": f"{r['pin_code']}::{r['business_category']}",
            "blocking_key_pin_name4": f"{r['pin_code']}::{normalize_name(r['business_name'])[:4]}",
            "status": r["status"],
            "last_event_date": r["last_event_date"],
            "entity_id_ground_truth": r["entity_id_ground_truth"],
        })

    # Dashboard mock compact view.
    risk_by_ubid = {r["ubid"]: r for r in risks}
    dashboard = []
    for reg in registry:
        risk = risk_by_ubid[reg["ubid"]]
        dashboard.append({
            "ubid": reg["ubid"],
            "business_name": reg["canonical_business_name"],
            "district": reg["district"],
            "pin_code": reg["pin_code"],
            "status": reg["activity_status"],
            "linked_departments": reg["linked_departments"],
            "progress_identity_verified_pct": min(100, reg["confidence"]),
            "progress_department_linkage_pct": min(100, reg["source_record_count"] * 18),
            "risk_score": risk["risk_score"],
            "risk_level": risk["risk_level"],
            "human_review_required": reg["confidence"] < 85,
        })

    # Write raw department files.
    file_map = {
        RAW_DIR / "shop_establishments.csv": dept_rows["SHOP"],
        RAW_DIR / "factories_act_registrations.csv": dept_rows["FACTORY"],
        RAW_DIR / "kspcb_consent_register.csv": dept_rows["KSPCB"],
        RAW_DIR / "labour_registrations.csv": dept_rows["LABOUR"],
        RAW_DIR / "bbmp_trade_licenses.csv": dept_rows["BBMP"],
        RAW_DIR / "gst_taxpayer_records.csv": dept_rows["GST"],
        RAW_DIR / "udyam_msme_records.csv": dept_rows["UDYAM"],
        RAW_DIR / "source_records_all_departments.csv": source_records,
        RAW_DIR / "ground_truth_entities.csv": entities,
        PROCESSED_DIR / "normalized_business_records.csv": normalized,
        PROCESSED_DIR / "ubid_registry.csv": registry,
        PROCESSED_DIR / "source_to_ubid_links.csv": links,
        PROCESSED_DIR / "candidate_match_pairs.csv": candidates,
        PROCESSED_DIR / "human_review_queue.csv": review_queue,
        PROCESSED_DIR / "auto_link_candidates.csv": auto_links,
        PROCESSED_DIR / "no_match_candidates.csv": no_match[:1200],
        PROCESSED_DIR / "risk_assessment.csv": risks,
        PROCESSED_DIR / "dashboard_mock.csv": dashboard,
        PROCESSED_DIR / "recommendation_rules.csv": rules,
        EVENTS_DIR / "compliance_events.csv": events,
    }
    for path, rows in file_map.items():
        write_csv(path, rows)

    api_samples = make_api_samples(registry, risks, candidates)
    intake_examples = make_intake_examples(rules)
    write_json(SAMPLES_DIR / "api_samples.json", api_samples)
    with (SAMPLES_DIR / "business_intake_examples.jsonl").open("w", encoding="utf-8") as f:
        for e in intake_examples:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    # Schemas for important datasets.
    schema_targets = {
        "source_records_all_departments.schema.json": (source_records, "Unified raw source record format after department-specific ingestion."),
        "ubid_registry.schema.json": (registry, "Canonical UBID registry output."),
        "candidate_match_pairs.schema.json": (candidates, "Pairwise matching evidence and decision output."),
        "risk_assessment.schema.json": (risks, "UBID risk-score output for dashboard."),
        "api_samples.schema.json": ([api_samples], "Sample REST API contract payloads."),
    }
    for fname, (rows, desc) in schema_targets.items():
        write_json(SCHEMAS_DIR / fname, schema_for(fname.replace(".schema.json", ""), rows, desc))

    stats = {
        "generated_at": TODAY.isoformat(),
        "seed": SEED,
        "synthetic_only": True,
        "entities": len(entities),
        "source_records_total": len(source_records),
        "department_counts": {dept: len(rows) for dept, rows in dept_rows.items()},
        "ubids": len(registry),
        "candidate_pairs": len(candidates),
        "auto_link_candidates": len(auto_links),
        "human_review_candidates": len(review_queue),
        "no_match_candidates": len(no_match),
        "events": len(events),
        "risk_levels": {level: sum(1 for r in risks if r["risk_level"] == level) for level in ["Low", "Medium", "High"]},
        "notes": [
            "Identifiers are fake and hashed-like strings. No real PAN/GSTIN/person data is included.",
            "entity_id_ground_truth is included only for evaluation; hide it from demo UI.",
            "Candidate scores use name 30%, address 25%, identifier 35%, phone 10%. Thresholds: >=85 auto-link, 60-84 human review, <60 no match.",
        ],
    }
    write_json(BASE_DIR / "dataset_manifest.json", stats)

    README = f"""# UBID Synthetic Data Package - Enhanced

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

- Synthetic entities: {len(entities)}
- Source records: {len(source_records)}
- UBIDs: {len(registry)}
- Candidate pairs: {len(candidates)}
- Human-review pairs: {len(review_queue)}
- Compliance events: {len(events)}

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
"""
    (BASE_DIR / "README.md").write_text(README, encoding="utf-8")

    data_dictionary = """# Data Dictionary

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
"""
    (DOCS_DIR / "data_dictionary.md").write_text(data_dictionary, encoding="utf-8")

    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
