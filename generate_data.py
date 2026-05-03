"""
Synthetic CSV generator for UBID hackathon prototype.
Writes shop_establishment.csv and factories.csv (~50 rows each).
"""
from __future__ import annotations

import csv
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent / "data"
OUT_DIR.mkdir(exist_ok=True)

# Shared narrative: same legal entities appear under variant names across registers.
SHOP_ROWS = [
    # reg_id, business_name, address, pincode, pan, gstin, phone, status
    ("SH001", "M/S Ravi Foods", "No 12, Peenya Ind Area, Blr", "560058", "AABCR1234F", "29AABCR1234F1Z5", "9876543210", "active"),
    ("SH002", "Ravi Foods Pvt Ltd", "12 Peenya Industrial Area Bengaluru", "560058", "AABCR1234F", "29AABCR1234F1Z5", "08041234567", "active"),
    ("SH003", "Ravi Food Processing", "Plot 12, Peenya Ind. Area, Bangalore", "560058", "AABCR1234F", "", "9876543210", "active"),
    ("SH004", "Lakshmi Silk House", "MG Road, Mysuru", "570001", "AAAFL9999K", "29AAAFL9999K1Z1", "8212345678", "active"),
    ("SH005", "Lakshmi Silks", "M G Road Mysore", "570001", "", "29AAAFL9999K1Z1", "8212345600", "active"),
    ("SH006", "Kaveri Agro Traders", "Hubli Market Rd, Hubballi", "580020", "AAAFK1111L", "29AAAFK1111L1Z2", "8360123456", "active"),
    ("SH007", "Kaveri Agro & Traders", "Hubli Market Road Hubli", "580020", "AAAFK1111L", "", "8360123499", "active"),
    ("SH008", "Sri Venkateswara Bakery", "Tumkur Rd, Nelamangala", "562123", "AAABV2222M", "29AAABV2222M1Z3", "9448012345", "active"),
    ("SH009", "S V Bakery", "Tumkur Road Nelamangala", "562123", "", "29AAABV2222M1Z3", "9448012300", "dormant"),
    ("SH010", "Global Tech Solutions", "Manyata Tech Park, Nagavara", "560045", "AAAGT3333N", "29AAAGT3333N1Z4", "9900112233", "active"),
    ("SH011", "Global Tech Solns Pvt Ltd", "Manyata TP Nagavara Blr", "560045", "AAAGT3333N", "29AAAGT3333N1Z4", "9900112200", "active"),
    ("SH012", "Coastal Fisheries", "Mangalore Port Rd", "575001", "AAACF4444P", "29AAACF4444P1Z6", "8242223344", "active"),
    ("SH013", "Coastal Fishries", "Mangalore Port Road", "575001", "", "29AAACF4444P1Z6", "8242223300", "active"),
    ("SH014", "Nandi Granite Works", "Chikkaballapur", "562101", "AAANG5555Q", "29AAANG5555Q1Z7", "8150020020", "active"),
    ("SH015", "Nandi Granite", "Chikkaballapur KA", "562101", "AAANG5555Q", "", "8150020099", "active"),
    ("SH016", "GreenLeaf Organics", "Hennur Rd, Bengaluru", "560043", "AAAGL6666R", "29AAAGL6666R1Z8", "9988776655", "active"),
    ("SH017", "Green Leaf Organics LLP", "Hennur Road Bangalore", "560043", "", "29AAAGL6666R1Z8", "9988776600", "active"),
    ("SH018", "Prakash Motors", "Ring Road, Vijayanagar", "560040", "AAAPM7777S", "29AAAPM7777S1Z9", "9845011122", "active"),
    ("SH019", "Prakash Motors & Sons", "Ring Rd Vijayanagar Blr", "560040", "AAAPM7777S", "29AAAPM7777S1Z9", "9845011199", "active"),
    ("SH020", "Udupi Krishna Bhavan", "Car St, Udupi", "576101", "AAAKU8888T", "29AAAKU8888T1ZA", "8202501234", "active"),
    ("SH021", "Udupi Krishna Bhavan Hotel", "Car Street Udupi", "576101", "AAAKU8888T", "29AAAKU8888T1ZA", "8202501200", "active"),
    ("SH022", "Himalaya Hardware", "Shivaji Nagar", "560001", "AAAHM9999U", "29AAAHM9999U1ZB", "9886012345", "active"),
    ("SH023", "Himalaya Hardvare", "Shivajinagar Bengaluru", "560001", "AAAHM9999U", "", "9886012399", "active"),
    ("SH024", "Sahyadri Coffee Works", "Chikmagalur", "577101", "AAASC0001V", "29AAASC0001V1ZC", "8262223344", "active"),
    ("SH025", "Sahyadri Coffee", "Chikmagalur Town", "577101", "", "29AAASC0001V1ZC", "8262223300", "active"),
    ("SH026", "Deccan Logistics", "Whitefield", "560066", "AAADL0002W", "29AAADL0002W1ZD", "9035303030", "active"),
    ("SH027", "Deccan Logistics Pvt Ltd", "Whitefield ITPL Rd", "560066", "AAADL0002W", "29AAADL0002W1ZD", "9035303099", "active"),
    ("SH028", "Annapoorna Snacks", "Davangere", "577004", "AAAAS0003X", "29AAAAS0003X1ZE", "8192224455", "active"),
    ("SH029", "Annapoorna Snacks Centre", "Davanagere City", "577004", "AAAAS0003X", "", "8192224400", "active"),
    ("SH030", "Zenith Pharma Distributors", "Electronic City Phase 1", "560100", "AAAZP0004Y", "29AAAZP0004Y1ZF", "9844123456", "active"),
    ("SH031", "Zenith Pharma Dist", "Electronic City Ph-1 Blr", "560100", "", "29AAAZP0004Y1ZF", "9844123499", "active"),
    ("SH032", "BlueRiver Textiles", "Ramanagara", "562159", "AAABT0005Z", "29AAABT0005Z1ZG", "9449011122", "active"),
    ("SH033", "Blue River Textiles Ltd", "Ramanagara Ind Area", "562159", "AAABT0005Z", "29AAABT0005Z1ZG", "9449011199", "active"),
    ("SH034", "Everest Steel Traders", "Peenya 2nd Stage", "560058", "AAAES0006A", "29AAAES0006A1ZH", "9845088888", "active"),
    ("SH035", "Everest Steel", "Peenya II Stage Bangalore", "560058", "AAAES0006A", "", "9845088800", "active"),
    ("SH036", "Southern Spices Mart", "Gandhinagar, Ballari", "583101", "AAASS0007B", "29AAASS0007B1ZI", "8392225566", "active"),
    ("SH037", "Southern Spices", "Gandhinagar Ballari", "583101", "", "29AAASS0007B1ZI", "8392225500", "active"),
    ("SH038", "Metro Cold Storage", "Yeshwanthpur", "560022", "AAAMC0008C", "29AAAMC0008C1ZJ", "8023456789", "active"),
    ("SH039", "Metro Cold Storage Pvt Ltd", "Yeshwanthpur Ind Suburb", "560022", "AAAMC0008C", "29AAAMC0008C1ZJ", "8023456700", "active"),
    ("SH040", "Bright Future Education", "Jayanagar 4th Block", "560041", "AAABF0009D", "29AAABF0009D1ZK", "9845099999", "active"),
    ("SH041", "Bright Future Edu Services", "Jayanagar 4th Blk Blr", "560041", "AAABF0009D", "", "9845099900", "active"),
    ("SH042", "Crystal Glass Works", "Rajajinagar", "560010", "AAACG0010E", "29AAACG0010E1ZL", "9342123456", "active"),
    ("SH043", "Crystal Glass", "Rajajinagar 2nd Main", "560010", "", "29AAACG0010E1ZL", "9342123499", "active"),
    ("SH044", "Orchid Florists", "Koramangala 5th Block", "560095", "AAAOF0011F", "29AAAOF0011F1ZM", "9886767676", "active"),
    ("SH045", "Orchid Flowers", "Koramangala 5th Blk", "560095", "AAAOF0011F", "29AAAOF0011F1ZM", "9886767600", "active"),
    ("SH046", "Unrelated Pizza Corner", "Indiranagar", "560038", "AAAPZ0012G", "29AAAPZ0012G1ZN", "9986020202", "active"),
    ("SH047", "Northwind Automobiles", "Hebbal", "560024", "AAANA0013H", "29AAANA0013H1ZO", "9845012345", "active"),
    ("SH048", "Northwind Auto", "Hebbal Flyover Rd", "560024", "AAANA0013H", "", "9845012399", "active"),
    ("SH049", "Silverline Jewellers", "Commercial Street", "560001", "AAASJ0014I", "29AAASJ0014I1ZP", "8022223333", "active"),
    ("SH050", "Silverline Jewellers LLP", "Comm St Bangalore", "560001", "AAASJ0014I", "29AAASJ0014I1ZP", "8022223399", "active"),
]

FACTORY_ROWS = [
    # factory_id, name, address, pincode, pan, gstin, contact, licence_status
    ("FC001", "Ravi Food Processing Unit", "Peenya Ind Area Plot 12, Bengaluru", "560058", "AABCR1234F", "29AABCR1234F1Z5", "9876543200", "valid"),
    ("FC002", "Ravi Foods Pvt Ltd Factory", "12 Peenya Ind Area Bangalore", "560058", "AABCR1234F", "29AABCR1234F1Z5", "08041234500", "valid"),
    ("FC003", "Lakshmi Silk Weaving Unit", "MG Road Extension Mysuru", "570001", "AAAFL9999K", "29AAAFL9999K1Z1", "8212345670", "valid"),
    ("FC004", "Kaveri Agro Processing", "Hubli Market Road Dharwad Dist", "580020", "AAAFK1111L", "29AAAFK1111L1Z2", "8360123400", "valid"),
    ("FC005", "Sri Venkateswara Food Products", "Nelamangala Ind Area Tumkur Rd", "562123", "AAABV2222M", "29AAABV2222M1Z3", "9448012340", "valid"),
    ("FC006", "Global Tech Solutions India", "Nagavara Manyata", "560045", "AAAGT3333N", "29AAAGT3333N1Z4", "9900112230", "valid"),
    ("FC007", "Coastal Fisheries Cold Chain", "New Mangalore Port Area", "575001", "AAACF4444P", "29AAACF4444P1Z6", "8242223300", "valid"),
    ("FC008", "Nandi Granite Cutting", "IDH Chikkaballapur", "562101", "AAANG5555Q", "29AAANG5555Q1Z7", "8150020022", "valid"),
    ("FC009", "GreenLeaf Organics Processing", "Hennur Bangalore", "560043", "AAAGL6666R", "29AAAGL6666R1Z8", "9988776601", "valid"),
    ("FC010", "Prakash Motors Assembly", "Vijayanagar Ring Road", "560040", "AAAPM7777S", "29AAAPM7777S1Z9", "9845011100", "valid"),
    ("FC011", "Udupi Krishna Bhavan Central Kitchen", "Manipal-Udupi Rd", "576101", "AAAKU8888T", "29AAAKU8888T1ZA", "8202501200", "valid"),
    ("FC012", "Himalaya Hardware Forging", "Shivaji Nagar Ind Layout", "560001", "AAAHM9999U", "29AAAHM9999U1ZB", "9886012300", "valid"),
    ("FC013", "Sahyadri Coffee Roasters", "Chikmagalur Estate Rd", "577101", "AAASC0001V", "29AAASC0001V1ZC", "8262223301", "valid"),
    ("FC014", "Deccan Logistics Warehouse", "Whitefield", "560066", "AAADL0002W", "29AAADL0002W1ZD", "9035303000", "valid"),
    ("FC015", "Annapoorna Snacks Manufacturing", "Davangere Ind Estate", "577004", "AAAAS0003X", "29AAAAS0003X1ZE", "8192224401", "valid"),
    ("FC016", "Zenith Pharma Formulations", "Electronic City", "560100", "AAAZP0004Y", "29AAAZP0004Y1ZF", "9844123400", "valid"),
    ("FC017", "BlueRiver Textiles Mill", "Ramanagara", "562159", "AAABT0005Z", "29AAABT0005Z1ZG", "9449011100", "valid"),
    ("FC018", "Everest Steel Rolling", "Peenya Stage 2", "560058", "AAAES0006A", "29AAAES0006A1ZH", "9845088880", "valid"),
    ("FC019", "Southern Spices Grinding", "Ballari", "583101", "AAASS0007B", "29AAASS0007B1ZI", "8392225501", "valid"),
    ("FC020", "Metro Cold Chain Plant", "Yeshwanthpur Goods Shed", "560022", "AAAMC0008C", "29AAAMC0008C1ZJ", "8023456701", "valid"),
    ("FC021", "Bright Future Printing Press", "Jayanagar", "560041", "AAABF0009D", "29AAABF0009D1ZK", "9845099901", "valid"),
    ("FC022", "Crystal Glass Tempering", "Rajajinagar Ind Estate", "560010", "AAACG0010E", "29AAACG0010E1ZL", "9342123400", "valid"),
    ("FC023", "Orchid Florists Packaging", "Koramangala", "560095", "AAAOF0011F", "29AAAOF0011F1ZM", "9886767601", "valid"),
    ("FC024", "Completely Different Cement Co", "Kalaburagi", "585101", "AAADC9999J", "29AAADC9999J1ZQ", "8472221111", "valid"),
    ("FC025", "Unrelated Pizza Production", "Indiranagar", "560038", "AAAPZ0012G", "29AAAPZ0012G1ZN", "9986020200", "valid"),
    ("FC026", "Northwind Auto Components", "Hebbal Industrial", "560024", "AAANA0013H", "29AAANA0013H1ZO", "9845012300", "valid"),
    ("FC027", "Silverline Jewellery Casting", "Commercial Street", "560001", "AAASJ0014I", "29AAASJ0014I1ZP", "8022223390", "valid"),
    ("FC028", "Ravi Foods (Alternate GST)", "Peenya", "560058", "", "", "9876543211", "suspended"),
    ("FC029", "Lakshmi Silk House Unit-2", "Mysuru Outskirts", "570001", "", "29AAAFL9999K1Z1", "8212000000", "valid"),
    ("FC030", "Kaveri Agro Cold Storage", "Hubballi", "580020", "AAAFK1111L", "", "8360000000", "valid"),
    ("FC031", "S V Bakery Commissary", "Nelamangala", "562123", "", "29AAABV2222M1Z3", "9448000000", "valid"),
    ("FC032", "Global Tech R&D", "Nagavara", "560045", "", "29AAAGT3333N1Z4", "9900000000", "valid"),
    ("FC033", "Coastal Fisheries Canning", "Mangalore", "575001", "AAACF4444P", "", "8240000000", "valid"),
    ("FC034", "Nandi Granite Polishing", "Chikkaballapur", "562101", "", "29AAANG5555Q1Z7", "8150000000", "valid"),
    ("FC035", "GreenLeaf Organics Pack", "Hennur", "560043", "AAAGL6666R", "", "9988000000", "valid"),
    ("FC036", "Prakash Motors Paint Shop", "Vijayanagar", "560040", "", "29AAAPM7777S1Z9", "9845000000", "valid"),
    ("FC037", "Udupi Krishna Bhavan Masala", "Udupi", "576101", "", "", "8202000000", "valid"),
    ("FC038", "Himalaya Hardware Galvanizing", "Shivaji Nagar", "560001", "", "29AAAHM9999U1ZB", "9886000000", "valid"),
    ("FC039", "Sahyadri Coffee Exports", "Chikmagalur", "577101", "AAASC0001V", "29AAASC0001V1ZC", "8262000000", "valid"),
    ("FC040", "Deccan Logistics Fleet", "Whitefield", "560066", "", "", "9035000000", "valid"),
    ("FC041", "Annapoorna Snacks Fryer Line", "Davangere", "577004", "AAAAS0003X", "29AAAAS0003X1ZE", "8192000000", "valid"),
    ("FC042", "Zenith Pharma Blending", "Electronic City", "560100", "AAAZP0004Y", "", "9844000000", "valid"),
    ("FC043", "BlueRiver Textiles Dyeing", "Ramanagara", "562159", "", "29AAABT0005Z1ZG", "9449000000", "valid"),
    ("FC044", "Everest Steel Forging", "Peenya", "560058", "AAAES0006A", "29AAAES0006A1ZH", "9845000000", "valid"),
    ("FC045", "Southern Spices Oil Extract", "Ballari", "583101", "AAASS0007B", "", "8392000000", "valid"),
    ("FC046", "Metro Cold Storage Ice Plant", "Yeshwanthpur", "560022", "", "29AAAMC0008C1ZJ", "8023000000", "valid"),
    ("FC047", "Bright Future Books", "Jayanagar", "560041", "", "29AAABF0009D1ZK", "9845000001", "valid"),
    ("FC048", "Crystal Glass Toughening", "Rajajinagar", "560010", "AAACG0010E", "", "9342000000", "valid"),
    ("FC049", "Orchid Florists Cold Room", "Koramangala", "560095", "", "29AAAOF0011F1ZM", "9886000000", "valid"),
    ("FC050", "Standalone Tyre Retreading", "Mandya", "571401", "AAATY8888K", "29AAATY8888K1ZR", "8232223333", "valid"),
]


def main() -> None:
    shop_path = OUT_DIR / "shop_establishment.csv"
    fact_path = OUT_DIR / "factories.csv"

    shop_cols = ["reg_id", "business_name", "address", "pincode", "pan", "gstin", "phone", "status"]
    fact_cols = ["factory_id", "name", "address", "pincode", "pan", "gstin", "contact", "licence_status"]

    shops = SHOP_ROWS
    facts = FACTORY_ROWS

    with shop_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(shop_cols)
        w.writerows(shops)

    with fact_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(fact_cols)
        w.writerows(facts)

    print(f"Wrote {len(shops)} rows -> {shop_path}")
    print(f"Wrote {len(facts)} rows -> {fact_path}")


if __name__ == "__main__":
    main()
