import os
import sqlite3

DB_PATH = os.getenv("MOCK_DB_PATH", "data/local.db")
SCHEMA_PATH = "personal_sustainbilty.sql"


def main() -> None:
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())

    cursor = conn.cursor()

    users = [
        ("Alice Green",   "alice@example.com",   "hash_alice",   "IN"),
        ("Bob Turner",    "bob@example.com",     "hash_bob",     "IN"),
        ("Charlie Das",   "charlie@example.com", "hash_charlie", "IN"),
        ("Diana Mehta",   "diana@example.com",   "hash_diana",   "IN"),
        ("Ethan Roy",     "ethan@example.com",   "hash_ethan",   "IN"),
        ("Fatima Khan",   "fatima@example.com",  "hash_fatima",  "IN"),
    ]
    cursor.executemany(
        """
        INSERT INTO users (full_name, email, password_hash, country_code)
        VALUES (?, ?, ?, ?)
        """,
        users,
    )

    households = [
        ("Green Family",  "IN"),
        ("Turner Home",   "IN"),
        ("Das Residence", "IN"),
    ]
    cursor.executemany(
        "INSERT INTO households (household_name, country_code) VALUES (?, ?)",
        households,
    )

    household_members = [
        (1, 1, "owner"),
        (1, 2, "member"),
        (2, 3, "owner"),
        (2, 4, "member"),
        (3, 5, "owner"),
        (3, 6, "member"),
    ]
    cursor.executemany(
        "INSERT INTO household_members (household_id, user_id, role) VALUES (?, ?, ?)",
        household_members,
    )

    emission_factors = [
        ("travel",     "car",         "IN", "km",    0.18,  "IPCC 2024", "https://example.org/ipcc"),   # 1
        ("travel",     "bus",         "IN", "km",    0.08,  "IPCC 2024", "https://example.org/ipcc"),   # 2
        ("electricity","grid",        "IN", "kwh",   0.72,  "CEA India", "https://example.org/cea"),    # 3
        ("food",       "beef",        "IN", "kg",    27.0,  "FAO",       "https://example.org/fao"),    # 4
        ("food",       "vegetables",  "IN", "kg",    2.0,   "FAO",       "https://example.org/fao"),    # 5
        ("waste",      "mixed",       "IN", "kg",    0.45,  "EPA",       "https://example.org/epa"),    # 6
        ("purchases",  "electronics", "IN", "rupee", 0.005, "DEFRA",     "https://example.org/defra"),  # 7
        ("travel",     "flight",      "IN", "km",    0.255, "IPCC 2024", "https://example.org/ipcc"),   # 8
        ("travel",     "bike",        "IN", "km",    0.0,   "IPCC 2024", "https://example.org/ipcc"),   # 9
        ("food",       "chicken",     "IN", "kg",    6.9,   "FAO",       "https://example.org/fao"),    # 10
        ("purchases",  "clothing",    "IN", "rupee", 0.003, "DEFRA",     "https://example.org/defra"),  # 11
    ]
    cursor.executemany(
        """
        INSERT INTO emission_factors (category, subcategory, region_code, unit, co2e_per_unit, source_name, source_url)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        emission_factors,
    )

    travel_entries = [
        # user 1 — April
        (1, 1, "2026-04-01", "car",    24.0,  1, 1,  4.32,  "Office commute"),
        (1, 1, "2026-04-08", "car",    24.0,  1, 1,  4.32,  "Office commute"),
        (1, 1, "2026-04-15", "car",    24.0,  1, 1,  4.32,  "Office commute"),
        (1, 1, "2026-04-22", "car",    24.0,  1, 1,  4.32,  "Office commute"),
        (1, 1, "2026-04-10", "flight", 1200.0,1, 8,  306.0, "Mumbai to Delhi"),
        # user 2 — April
        (2, 1, "2026-04-03", "bus",    12.0,  1, 2,  0.96,  "Metro connector"),
        (2, 1, "2026-04-10", "bus",    15.0,  1, 2,  1.20,  "Weekend outing"),
        (2, 1, "2026-04-17", "car",    30.0,  1, 1,  5.40,  "Client visit"),
        # user 3 — April
        (3, 2, "2026-04-04", "car",    45.0,  1, 1,  8.10,  "Airport drop"),
        (3, 2, "2026-04-11", "bike",   8.0,   1, 9,  0.0,   "Cycling to market"),
        (3, 2, "2026-04-18", "car",    60.0,  1, 1,  10.80, "Outstation trip"),
        # user 4 — April
        (4, 2, "2026-04-05", "bus",    20.0,  1, 2,  1.60,  "Daily commute"),
        (4, 2, "2026-04-12", "car",    35.0,  1, 1,  6.30,  "Grocery run"),
        # user 5 — April
        (5, 3, "2026-04-06", "car",    50.0,  1, 1,  9.0,   "Work trip"),
        (5, 3, "2026-04-13", "flight", 800.0, 1, 8,  204.0, "Bangalore to Mumbai"),
        # user 6 — April
        (6, 3, "2026-04-07", "bus",    10.0,  1, 2,  0.80,  "Local commute"),
        (6, 3, "2026-04-14", "bike",   5.0,   1, 9,  0.0,   "Park ride"),
        # user 1 — March (historical)
        (1, 1, "2026-03-05", "car",    24.0,  1, 1,  4.32,  "Office commute"),
        (1, 1, "2026-03-12", "car",    24.0,  1, 1,  4.32,  "Office commute"),
        # user 2 — March
        (2, 1, "2026-03-08", "bus",    12.0,  1, 2,  0.96,  "Daily bus"),
        # user 5 — March
        (5, 3, "2026-03-20", "car",    40.0,  1, 1,  7.20,  "Weekend drive"),
    ]
    cursor.executemany(
        """
        INSERT INTO travel_entries
        (user_id, household_id, travel_date, mode, distance_km, passenger_count, emission_factor_id, co2e_kg, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        travel_entries,
    )

    electricity_entries = [
        # March bills
        (1, 1, "2026-03-01", "2026-03-31", 210.0, "IN", 3, 151.2),
        (2, 1, "2026-03-01", "2026-03-31", 180.0, "IN", 3, 129.6),
        (3, 2, "2026-03-01", "2026-03-31", 165.0, "IN", 3, 118.8),
        (4, 2, "2026-03-01", "2026-03-31", 140.0, "IN", 3, 100.8),
        (5, 3, "2026-03-01", "2026-03-31", 220.0, "IN", 3, 158.4),
        (6, 3, "2026-03-01", "2026-03-31", 95.0,  "IN", 3, 68.4),
        # April bills
        (1, 1, "2026-04-01", "2026-04-30", 230.0, "IN", 3, 165.6),
        (2, 1, "2026-04-01", "2026-04-30", 195.0, "IN", 3, 140.4),
        (3, 2, "2026-04-01", "2026-04-30", 175.0, "IN", 3, 126.0),
        (4, 2, "2026-04-01", "2026-04-30", 155.0, "IN", 3, 111.6),
        (5, 3, "2026-04-01", "2026-04-30", 240.0, "IN", 3, 172.8),
        (6, 3, "2026-04-01", "2026-04-30", 110.0, "IN", 3, 79.2),
    ]
    cursor.executemany(
        """
        INSERT INTO electricity_entries
        (user_id, household_id, billing_start, billing_end, kwh, grid_region, emission_factor_id, co2e_kg)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        electricity_entries,
    )

    food_entries = [
        (1, 1, "2026-04-01", "beef",       1.5,  "kg", 4,  40.5,  "Weekend barbecue"),
        (1, 1, "2026-04-08", "chicken",    2.0,  "kg", 10, 13.8,  "Weekly protein"),
        (1, 1, "2026-04-15", "vegetables", 5.0,  "kg", 5,  10.0,  "Salad week"),
        (2, 1, "2026-04-02", "vegetables", 8.0,  "kg", 5,  16.0,  "Weekly groceries"),
        (2, 1, "2026-04-09", "beef",       1.0,  "kg", 4,  27.0,  "Steak night"),
        (3, 2, "2026-04-03", "chicken",    3.0,  "kg", 10, 20.7,  "Family dinner"),
        (3, 2, "2026-04-10", "vegetables", 10.0, "kg", 5,  20.0,  "Veg week"),
        (4, 2, "2026-04-04", "beef",       2.0,  "kg", 4,  54.0,  "BBQ party"),
        (5, 3, "2026-04-05", "chicken",    1.5,  "kg", 10, 10.35, "Grilled chicken"),
        (5, 3, "2026-04-12", "vegetables", 6.0,  "kg", 5,  12.0,  "Healthy week"),
        (6, 3, "2026-04-06", "vegetables", 12.0, "kg", 5,  24.0,  "Vegan groceries"),
        # March
        (1, 1, "2026-03-10", "beef",       1.0,  "kg", 4,  27.0,  "March barbecue"),
        (3, 2, "2026-03-15", "chicken",    2.5,  "kg", 10, 17.25, "March dinner"),
    ]
    cursor.executemany(
        """
        INSERT INTO food_entries
        (user_id, household_id, entry_date, food_type, quantity, unit, emission_factor_id, co2e_kg, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        food_entries,
    )

    waste_entries = [
        (1, 1, "2026-04-02", "mixed", 4.2,  "landfill", 6, 1.89),
        (1, 1, "2026-04-16", "mixed", 3.8,  "landfill", 6, 1.71),
        (2, 1, "2026-04-05", "mixed", 5.0,  "landfill", 6, 2.25),
        (3, 2, "2026-04-03", "mixed", 3.1,  "landfill", 6, 1.395),
        (4, 2, "2026-04-07", "mixed", 6.5,  "landfill", 6, 2.925),
        (5, 3, "2026-04-08", "mixed", 4.0,  "landfill", 6, 1.80),
        (6, 3, "2026-04-09", "mixed", 2.5,  "landfill", 6, 1.125),
        # March
        (1, 1, "2026-03-18", "mixed", 4.0,  "landfill", 6, 1.80),
        (5, 3, "2026-03-22", "mixed", 3.5,  "landfill", 6, 1.575),
    ]
    cursor.executemany(
        """
        INSERT INTO waste_entries
        (user_id, household_id, entry_date, waste_type, quantity_kg, treatment_method, emission_factor_id, co2e_kg)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        waste_entries,
    )

    purchase_entries = [
        (1, 1, "2026-04-05", "electronics", "wireless headphones", 12000.0, "INR", 7,  60.0),
        (2, 1, "2026-04-05", "electronics", "phone charger",       1800.0,  "INR", 7,  9.0),
        (3, 2, "2026-04-06", "clothing",    "winter jacket",       4500.0,  "INR", 11, 13.5),
        (4, 2, "2026-04-07", "electronics", "smart watch",         25000.0, "INR", 7,  125.0),
        (5, 3, "2026-04-08", "clothing",    "running shoes",       6000.0,  "INR", 11, 18.0),
        (6, 3, "2026-04-09", "electronics", "bluetooth speaker",   3500.0,  "INR", 7,  17.5),
        (1, 1, "2026-04-20", "clothing",    "formal shirt",        2200.0,  "INR", 11, 6.6),
        # March
        (1, 1, "2026-03-14", "electronics", "laptop stand",        2500.0,  "INR", 7,  12.5),
        (5, 3, "2026-03-25", "electronics", "keyboard",            3000.0,  "INR", 7,  15.0),
    ]
    cursor.executemany(
        """
        INSERT INTO purchase_entries
        (user_id, household_id, purchase_date, category, item_name, amount_spent, currency, emission_factor_id, co2e_kg)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        purchase_entries,
    )

    goals = [
        (1, 1, "monthly_total_co2e", 250.0, "kg", "2026-04-01", "2026-04-30", "active"),
        (2, 1, "travel_co2e",        50.0,  "kg", "2026-04-01", "2026-04-30", "active"),
        (3, 2, "electricity_co2e",   100.0, "kg", "2026-04-01", "2026-04-30", "active"),
        (4, 2, "monthly_total_co2e", 300.0, "kg", "2026-04-01", "2026-04-30", "active"),
        (5, 3, "monthly_total_co2e", 400.0, "kg", "2026-04-01", "2026-04-30", "active"),
        (6, 3, "food_co2e",          30.0,  "kg", "2026-04-01", "2026-04-30", "active"),
    ]
    cursor.executemany(
        """
        INSERT INTO goals
        (user_id, household_id, goal_type, target_value, unit, start_date, end_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        goals,
    )

    calculation_runs = [
        (1, 1, "2026-03-01", "2026-03-31", 196.84),
        (1, 1, "2026-04-01", "2026-04-30", 560.86),
        (2, 1, "2026-04-01", "2026-04-30", 204.81),
        (3, 2, "2026-03-01", "2026-03-31", 157.47),
        (3, 2, "2026-04-01", "2026-04-30", 187.30),
        (4, 2, "2026-04-01", "2026-04-30", 299.83),
        (5, 3, "2026-04-01", "2026-04-30", 427.95),
        (6, 3, "2026-04-01", "2026-04-30", 121.63),
    ]
    cursor.executemany(
        """
        INSERT INTO calculation_runs
        (user_id, household_id, period_start, period_end, total_co2e_kg)
        VALUES (?, ?, ?, ?, ?)
        """,
        calculation_runs,
    )

    recommendations = [
        (1, 1, 2, "Shift 3 weekly car trips to bus to save ~18 kg CO2e/month",    "travel",      18.0),
        (1, 1, 2, "Reduce beef consumption by 50% to save ~54 kg CO2e/month",     "food",        54.0),
        (2, 1, 3, "Use public transport for client visits to save ~5 kg CO2e",     "travel",       5.0),
        (3, 2, 5, "Reduce AC usage by 10% to save ~12 kg CO2e/month",             "electricity", 12.0),
        (4, 2, 6, "Cut beef intake to save ~54 kg CO2e/month",                    "food",        54.0),
        (5, 3, 7, "Replace one flight with train to save ~200 kg CO2e",           "travel",     200.0),
        (6, 3, 8, "Switch to LED lighting to save ~8 kg CO2e/month",              "electricity",  8.0),
    ]
    cursor.executemany(
        """
        INSERT INTO recommendations
        (user_id, household_id, run_id, recommendation_text, category, impact_estimate_kg)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        recommendations,
    )

    conn.commit()
    conn.close()

    print("Created data/local.db using personal_sustainbilty.sql")
    print("Seeded: 6 users, 3 households, 11 emission factors")
    print("        21 travel | 12 electricity | 13 food | 9 waste | 9 purchase entries")
    print("        6 goals | 8 calculation runs | 7 recommendations")


if __name__ == "__main__":
    main()
