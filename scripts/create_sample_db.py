import os
import sqlite3

DB_PATH = "data/local.db"
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
        ("Alice Green", "alice@example.com", "hash_alice", "IN"),
        ("Bob Turner", "bob@example.com", "hash_bob", "IN"),
        ("Charlie Das", "charlie@example.com", "hash_charlie", "IN"),
    ]
    cursor.executemany(
        """
        INSERT INTO users (full_name, email, password_hash, country_code)
        VALUES (?, ?, ?, ?)
        """,
        users,
    )

    households = [
        ("Green Family", "IN"),
        ("Turner Home", "IN"),
    ]
    cursor.executemany(
        "INSERT INTO households (household_name, country_code) VALUES (?, ?)",
        households,
    )

    household_members = [
        (1, 1, "owner"),
        (1, 2, "member"),
        (2, 3, "owner"),
    ]
    cursor.executemany(
        "INSERT INTO household_members (household_id, user_id, role) VALUES (?, ?, ?)",
        household_members,
    )

    emission_factors = [
        ("travel", "car", "IN", "km", 0.18, "IPCC 2024", "https://example.org/ipcc"),
        ("travel", "bus", "IN", "km", 0.08, "IPCC 2024", "https://example.org/ipcc"),
        ("electricity", "grid", "IN", "kwh", 0.72, "CEA India", "https://example.org/cea"),
        ("food", "beef", "IN", "kg", 27.0, "FAO", "https://example.org/fao"),
        ("food", "vegetables", "IN", "kg", 2.0, "FAO", "https://example.org/fao"),
        ("waste", "mixed", "IN", "kg", 0.45, "EPA", "https://example.org/epa"),
        ("purchases", "electronics", "IN", "rupee", 0.005, "DEFRA", "https://example.org/defra"),
    ]
    cursor.executemany(
        """
        INSERT INTO emission_factors (category, subcategory, region_code, unit, co2e_per_unit, source_name, source_url)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        emission_factors,
    )

    travel_entries = [
        (1, 1, "2026-04-01", "car", 24.0, 1, 1, 4.32, "Office commute"),
        (2, 1, "2026-04-03", "bus", 12.0, 1, 2, 0.96, "Metro connector"),
        (3, 2, "2026-04-04", "car", 45.0, 1, 1, 8.10, "Airport drop"),
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
        (1, 1, "2026-03-01", "2026-03-31", 210.0, "IN", 3, 151.2),
        (3, 2, "2026-03-01", "2026-03-31", 165.0, "IN", 3, 118.8),
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
        (1, 1, "2026-04-01", "beef", 1.5, "kg", 4, 40.5, "Weekend barbecue"),
        (2, 1, "2026-04-02", "vegetables", 8.0, "kg", 5, 16.0, "Weekly groceries"),
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
        (1, 1, "2026-04-02", "mixed", 4.2, "landfill", 6, 1.89),
        (3, 2, "2026-04-03", "mixed", 3.1, "landfill", 6, 1.395),
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
        (1, 1, "2026-04-05", "electronics", "wireless headphones", 12000.0, "INR", 7, 60.0),
        (2, 1, "2026-04-05", "electronics", "phone charger", 1800.0, "INR", 7, 9.0),
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
        (3, 2, "electricity_co2e", 100.0, "kg", "2026-04-01", "2026-04-30", "active"),
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
        (1, 1, "2026-04-01", "2026-04-30", 273.87),
        (3, 2, "2026-04-01", "2026-04-30", 129.195),
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
        (1, 1, 1, "Shift 3 weekly car trips to bus to save ~18 kg CO2e/month", "travel", 18.0),
        (3, 2, 2, "Reduce AC usage by 10% to save ~12 kg CO2e/month", "electricity", 12.0),
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
    print("Seeded tables: users, households, emission_factors, activity tables, goals, runs, recommendations")


if __name__ == "__main__":
    main()
