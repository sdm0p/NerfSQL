-- ============================================
-- PERSONAL CARBON FOOTPRINT CALCULATOR SCHEMA
-- ============================================

PRAGMA foreign_keys = ON;

-- =====================
-- USERS & HOUSEHOLDS
-- =====================

CREATE TABLE users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    country_code TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE households (
    household_id INTEGER PRIMARY KEY AUTOINCREMENT,
    household_name TEXT NOT NULL,
    country_code TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE household_members (
    household_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (household_id, user_id),
    FOREIGN KEY (household_id) REFERENCES households(household_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- =====================
-- EMISSION FACTORS
-- =====================

CREATE TABLE emission_factors (
    factor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,              -- travel, electricity, food, waste, purchases
    subcategory TEXT,                   -- car, bus, flight, grid, beef, etc.
    region_code TEXT,                   -- IN, EU, US, etc.
    unit TEXT NOT NULL,                 -- km, kwh, kg, meal, rupee
    co2e_per_unit REAL NOT NULL,
    source_name TEXT,
    source_url TEXT,
    valid_from TEXT,
    valid_to TEXT,
    is_active INTEGER NOT NULL DEFAULT 1
);

-- =====================
-- CALCULATION RUNS
-- =====================

CREATE TABLE calculation_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    household_id INTEGER,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    total_co2e_kg REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (household_id) REFERENCES households(household_id)
);

-- =====================
-- ACTIVITY TABLES
-- =====================

CREATE TABLE travel_entries (
    travel_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    household_id INTEGER,
    travel_date TEXT NOT NULL,
    mode TEXT NOT NULL,
    distance_km REAL NOT NULL,
    passenger_count INTEGER DEFAULT 1,
    emission_factor_id INTEGER,
    co2e_kg REAL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (household_id) REFERENCES households(household_id),
    FOREIGN KEY (emission_factor_id) REFERENCES emission_factors(factor_id)
);

CREATE TABLE electricity_entries (
    electricity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    household_id INTEGER,
    billing_start TEXT NOT NULL,
    billing_end TEXT NOT NULL,
    kwh REAL NOT NULL,
    grid_region TEXT,
    emission_factor_id INTEGER,
    co2e_kg REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (household_id) REFERENCES households(household_id),
    FOREIGN KEY (emission_factor_id) REFERENCES emission_factors(factor_id)
);

CREATE TABLE food_entries (
    food_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    household_id INTEGER,
    entry_date TEXT NOT NULL,
    food_type TEXT NOT NULL,
    quantity REAL NOT NULL,
    unit TEXT NOT NULL,
    emission_factor_id INTEGER,
    co2e_kg REAL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (household_id) REFERENCES households(household_id),
    FOREIGN KEY (emission_factor_id) REFERENCES emission_factors(factor_id)
);

CREATE TABLE waste_entries (
    waste_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    household_id INTEGER,
    entry_date TEXT NOT NULL,
    waste_type TEXT NOT NULL,
    quantity_kg REAL NOT NULL,
    treatment_method TEXT,
    emission_factor_id INTEGER,
    co2e_kg REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (household_id) REFERENCES households(household_id),
    FOREIGN KEY (emission_factor_id) REFERENCES emission_factors(factor_id)
);

CREATE TABLE purchase_entries (
    purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    household_id INTEGER,
    purchase_date TEXT NOT NULL,
    category TEXT NOT NULL,
    item_name TEXT,
    amount_spent REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'INR',
    emission_factor_id INTEGER,
    co2e_kg REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (household_id) REFERENCES households(household_id),
    FOREIGN KEY (emission_factor_id) REFERENCES emission_factors(factor_id)
);

-- =====================
-- GOALS & RECOMMENDATIONS
-- =====================

CREATE TABLE goals (
    goal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    household_id INTEGER,
    goal_type TEXT NOT NULL,
    target_value REAL NOT NULL,
    unit TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (household_id) REFERENCES households(household_id)
);

CREATE TABLE recommendations (
    recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    household_id INTEGER,
    run_id INTEGER,
    recommendation_text TEXT NOT NULL,
    category TEXT,
    impact_estimate_kg REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (household_id) REFERENCES households(household_id),
    FOREIGN KEY (run_id) REFERENCES calculation_runs(run_id)
);

-- =====================
-- INDEXES (PERFORMANCE)
-- =====================

CREATE INDEX idx_travel_user_date
ON travel_entries(user_id, travel_date);

CREATE INDEX idx_electricity_user_period
ON electricity_entries(user_id, billing_start, billing_end);

CREATE INDEX idx_food_user_date
ON food_entries(user_id, entry_date);

CREATE INDEX idx_waste_user_date
ON waste_entries(user_id, entry_date);

CREATE INDEX idx_purchase_user_date
ON purchase_entries(user_id, purchase_date);

CREATE INDEX idx_factor_category_region
ON emission_factors(category, region_code);

-- ============================================
-- END OF SCHEMA
-- ============================================