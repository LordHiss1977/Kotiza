"""SQLite storage: schema, connection helper and sample seed data.

Cost hierarchy stored here:

    Resources   labor trades, equipment, materials & consumables (unit costs)
    Crews       a mix of labor + equipment with a combined hourly cost
    Tasks       a measured work item: quantity x (crew at a production rate
                + materials + consumables per unit of measure)
    Indirects   site overheads, lump sums, and percentages of direct cost
    Markups     contingency, overhead, profit, bond, tax -> contract price

All percentages are stored as plain numbers (55 means 55%).
"""

import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS units (
    id      INTEGER PRIMARY KEY,
    code    TEXT NOT NULL UNIQUE,
    name    TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS labor (
    id          INTEGER PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    trade       TEXT NOT NULL,
    base_rate   REAL NOT NULL DEFAULT 0,   -- wage per hour
    burden_pct  REAL NOT NULL DEFAULT 0    -- social charges, benefits, etc.
);

CREATE TABLE IF NOT EXISTS equipment (
    id           INTEGER PRIMARY KEY,
    code         TEXT NOT NULL UNIQUE,
    description  TEXT NOT NULL,
    hourly_rate  REAL NOT NULL DEFAULT 0   -- owning/rental + operating per hour
);

CREATE TABLE IF NOT EXISTS materials (
    id           INTEGER PRIMARY KEY,
    code         TEXT NOT NULL UNIQUE,
    description  TEXT NOT NULL,
    kind         TEXT NOT NULL DEFAULT 'material'
                 CHECK (kind IN ('material', 'consumable')),
    category     TEXT NOT NULL DEFAULT '',
    unit         TEXT NOT NULL DEFAULT 'ea',
    unit_cost    REAL NOT NULL DEFAULT 0,
    waste_pct    REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS crews (
    id           INTEGER PRIMARY KEY,
    code         TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS crew_labor (
    id        INTEGER PRIMARY KEY,
    crew_id   INTEGER NOT NULL REFERENCES crews(id) ON DELETE CASCADE,
    labor_id  INTEGER NOT NULL REFERENCES labor(id) ON DELETE RESTRICT,
    qty       REAL NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS crew_equipment (
    id            INTEGER PRIMARY KEY,
    crew_id       INTEGER NOT NULL REFERENCES crews(id) ON DELETE CASCADE,
    equipment_id  INTEGER NOT NULL REFERENCES equipment(id) ON DELETE RESTRICT,
    qty           REAL NOT NULL DEFAULT 1
);

-- Reusable task templates ("standard tasks" / assemblies)
CREATE TABLE IF NOT EXISTS task_library (
    id               INTEGER PRIMARY KEY,
    code             TEXT NOT NULL UNIQUE,
    description      TEXT NOT NULL,
    category         TEXT NOT NULL DEFAULT '',
    unit             TEXT NOT NULL DEFAULT 'ea',
    crew_id          INTEGER REFERENCES crews(id) ON DELETE SET NULL,
    production_rate  REAL NOT NULL DEFAULT 0,   -- units per crew-day
    notes            TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS task_library_resources (
    id            INTEGER PRIMARY KEY,
    task_id       INTEGER NOT NULL REFERENCES task_library(id) ON DELETE CASCADE,
    material_id   INTEGER NOT NULL REFERENCES materials(id) ON DELETE RESTRICT,
    qty_per_unit  REAL NOT NULL DEFAULT 0
);

-- Reusable indirect-cost templates
CREATE TABLE IF NOT EXISTS indirect_library (
    id           INTEGER PRIMARY KEY,
    description  TEXT NOT NULL,
    category     TEXT NOT NULL DEFAULT '',
    method       TEXT NOT NULL DEFAULT 'lump'
                 CHECK (method IN ('lump', 'pct_direct', 'pct_labor')),
    unit         TEXT NOT NULL DEFAULT 'ls',
    rate         REAL NOT NULL DEFAULT 0,
    percent      REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS estimates (
    id               INTEGER PRIMARY KEY,
    name             TEXT NOT NULL,
    client           TEXT NOT NULL DEFAULT '',
    location         TEXT NOT NULL DEFAULT '',
    estimate_date    TEXT NOT NULL DEFAULT '',
    currency         TEXT NOT NULL DEFAULT 'USD',
    status           TEXT NOT NULL DEFAULT 'draft',
    hours_per_day    REAL NOT NULL DEFAULT 8,
    contingency_pct  REAL NOT NULL DEFAULT 0,
    overhead_pct     REAL NOT NULL DEFAULT 0,
    profit_pct       REAL NOT NULL DEFAULT 0,
    bond_pct         REAL NOT NULL DEFAULT 0,
    tax_pct          REAL NOT NULL DEFAULT 0,
    notes            TEXT NOT NULL DEFAULT '',
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS estimate_tasks (
    id               INTEGER PRIMARY KEY,
    estimate_id      INTEGER NOT NULL REFERENCES estimates(id) ON DELETE CASCADE,
    seq              INTEGER NOT NULL DEFAULT 0,
    code             TEXT NOT NULL DEFAULT '',
    description      TEXT NOT NULL,
    unit             TEXT NOT NULL DEFAULT 'ea',
    quantity         REAL NOT NULL DEFAULT 0,
    crew_id          INTEGER REFERENCES crews(id) ON DELETE RESTRICT,
    production_rate  REAL NOT NULL DEFAULT 0,   -- units per crew-day
    notes            TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS estimate_task_resources (
    id            INTEGER PRIMARY KEY,
    task_id       INTEGER NOT NULL REFERENCES estimate_tasks(id) ON DELETE CASCADE,
    material_id   INTEGER NOT NULL REFERENCES materials(id) ON DELETE RESTRICT,
    qty_per_unit  REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS estimate_indirects (
    id           INTEGER PRIMARY KEY,
    estimate_id  INTEGER NOT NULL REFERENCES estimates(id) ON DELETE CASCADE,
    seq          INTEGER NOT NULL DEFAULT 0,
    description  TEXT NOT NULL,
    category     TEXT NOT NULL DEFAULT '',
    method       TEXT NOT NULL DEFAULT 'lump'
                 CHECK (method IN ('lump', 'pct_direct', 'pct_labor')),
    unit         TEXT NOT NULL DEFAULT 'ls',
    quantity     REAL NOT NULL DEFAULT 1,
    rate         REAL NOT NULL DEFAULT 0,
    percent      REAL NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_tasks_estimate ON estimate_tasks(estimate_id, seq);
CREATE INDEX IF NOT EXISTS ix_task_res_task ON estimate_task_resources(task_id);
CREATE INDEX IF NOT EXISTS ix_indirects_estimate ON estimate_indirects(estimate_id, seq);
"""

DEFAULT_DB = os.environ.get(
    "KOTIZA_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kotiza.db"),
)


def connect(path=None):
    conn = sqlite3.connect(path or DEFAULT_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn, seed=True):
    """Create tables; load sample data if the database is empty."""
    conn.executescript(SCHEMA)
    empty = conn.execute("SELECT COUNT(*) FROM labor").fetchone()[0] == 0
    if seed and empty:
        seed_sample_data(conn)
    conn.commit()


# --------------------------------------------------------------------------
# Sample data (illustrative Panama-style USD rates - replace with your own)
# --------------------------------------------------------------------------

def seed_sample_data(conn):
    c = conn.cursor()

    units = [
        ("ea", "each"), ("m", "linear metre"), ("m2", "square metre"),
        ("m3", "cubic metre"), ("kg", "kilogram"), ("bag", "bag"),
        ("sheet", "sheet"), ("bf", "board foot"), ("gal", "gallon"),
        ("hr", "hour"), ("day", "day"), ("month", "month"), ("ls", "lump sum"),
    ]
    c.executemany("INSERT INTO units(code, name) VALUES (?, ?)", units)

    labor = [
        ("FOR", "Foreman (capataz)", 8.00, 55),
        ("MAS", "Mason (albañil)", 5.50, 55),
        ("CAR", "Carpenter (carpintero)", 5.50, 55),
        ("IRW", "Ironworker (armador)", 5.50, 55),
        ("HLP", "Helper (ayudante)", 3.75, 55),
        ("OPR", "Equipment operator", 6.75, 55),
        ("ELE", "Electrician", 6.50, 55),
        ("PLU", "Plumber (plomero)", 6.00, 55),
    ]
    c.executemany(
        "INSERT INTO labor(code, trade, base_rate, burden_pct) VALUES (?,?,?,?)", labor)

    equipment = [
        ("MIX", "Concrete mixer, 1 bag", 4.00),
        ("VIB", "Concrete vibrator", 2.50),
        ("BHL", "Backhoe loader", 45.00),
        ("CMP", "Plate compactor", 6.00),
        ("DTR", "Dump truck 12 m3", 35.00),
    ]
    c.executemany(
        "INSERT INTO equipment(code, description, hourly_rate) VALUES (?,?,?)", equipment)

    materials = [
        # code, description, kind, category, unit, cost, waste%
        ("CEM", "Portland cement 42.5 kg", "material", "Concrete", "bag", 8.75, 3),
        ("SND", "Sand", "material", "Aggregates", "m3", 28.00, 10),
        ("GRV", "Gravel 3/4\"", "material", "Aggregates", "m3", 32.00, 10),
        ("RMX", "Ready-mix concrete 3000 psi", "material", "Concrete", "m3", 135.00, 5),
        ("RB4", "Rebar #4 grade 60", "material", "Steel", "kg", 1.10, 5),
        ("BLK4", "Concrete block 4\"", "material", "Masonry", "ea", 0.75, 5),
        ("PLY", "Plywood 3/4\" 4x8", "material", "Formwork", "sheet", 32.00, 0),
        ("LUM", "Lumber 2x4 (pine)", "material", "Formwork", "bf", 1.25, 10),
        ("TIE", "Tie wire #16", "consumable", "Steel", "kg", 2.20, 0),
        ("NAI", "Nails, assorted", "consumable", "Formwork", "kg", 2.50, 0),
        ("OIL", "Form release oil", "consumable", "Formwork", "gal", 12.00, 0),
        ("WAT", "Water", "consumable", "General", "m3", 1.50, 0),
        ("DSC", "Cutting disc 7\"", "consumable", "General", "ea", 4.00, 0),
    ]
    c.executemany(
        "INSERT INTO materials(code, description, kind, category, unit, unit_cost, waste_pct)"
        " VALUES (?,?,?,?,?,?,?)", materials)

    lab = {r["code"]: r["id"] for r in c.execute("SELECT id, code FROM labor")}
    eqp = {r["code"]: r["id"] for r in c.execute("SELECT id, code FROM equipment")}
    mat = {r["code"]: r["id"] for r in c.execute("SELECT id, code FROM materials")}

    crews = [
        ("C-MAS", "Masonry crew", "1 mason + 1 helper, part-time foreman",
         [("FOR", 0.1), ("MAS", 1), ("HLP", 1)], []),
        ("C-CON", "Concrete crew", "Placing & finishing concrete",
         [("FOR", 1), ("MAS", 2), ("HLP", 4)], [("MIX", 1), ("VIB", 1)]),
        ("C-RBR", "Rebar crew", "Cut, bend and tie reinforcement",
         [("IRW", 1), ("HLP", 1)], []),
        ("C-EXC", "Excavation crew", "Backhoe with spotter",
         [("OPR", 1), ("HLP", 1)], [("BHL", 1)]),
        ("C-FRM", "Formwork crew", "Carpentry for forms",
         [("CAR", 2), ("HLP", 1)], []),
    ]
    crew_ids = {}
    for code, name, desc, members, equip in crews:
        c.execute("INSERT INTO crews(code, name, description) VALUES (?,?,?)", (code, name, desc))
        cid = c.lastrowid
        crew_ids[code] = cid
        for lc, q in members:
            c.execute("INSERT INTO crew_labor(crew_id, labor_id, qty) VALUES (?,?,?)",
                      (cid, lab[lc], q))
        for ec, q in equip:
            c.execute("INSERT INTO crew_equipment(crew_id, equipment_id, qty) VALUES (?,?,?)",
                      (cid, eqp[ec], q))

    tasks = [
        # code, description, category, unit, crew, rate/day, [(material, qty/unit)]
        ("EXC-01", "Machine excavation for footings", "Earthwork", "m3", "C-EXC", 120, []),
        ("FRM-01", "Formwork for footings and grade beams", "Concrete", "m2", "C-FRM", 12,
         [("PLY", 0.15), ("LUM", 3.0), ("NAI", 0.15), ("OIL", 0.02)]),
        ("RBR-01", "Reinforcing steel, cut/bend/place", "Concrete", "kg", "C-RBR", 250,
         [("RB4", 1.0), ("TIE", 0.02)]),
        ("CON-01", "Concrete 3000 psi, ready-mix, placed", "Concrete", "m3", "C-CON", 12,
         [("RMX", 1.0), ("WAT", 0.05)]),
        ("MAS-01", "Block wall 4\", mortar joints", "Masonry", "m2", "C-MAS", 10,
         [("BLK4", 12.5), ("CEM", 0.12), ("SND", 0.012), ("WAT", 0.01), ("DSC", 0.02)]),
    ]
    for code, desc, cat, unit, crew, rate, res in tasks:
        c.execute(
            "INSERT INTO task_library(code, description, category, unit, crew_id, production_rate)"
            " VALUES (?,?,?,?,?,?)", (code, desc, cat, unit, crew_ids[crew], rate))
        tid = c.lastrowid
        for mc, q in res:
            c.execute(
                "INSERT INTO task_library_resources(task_id, material_id, qty_per_unit)"
                " VALUES (?,?,?)", (tid, mat[mc], q))

    indirects = [
        ("Site superintendent", "Site staff", "lump", "month", 3500, 0),
        ("Site engineer", "Site staff", "lump", "month", 2200, 0),
        ("Security guard", "Site staff", "lump", "month", 1100, 0),
        ("Temporary site office & storage", "Facilities", "lump", "month", 600, 0),
        ("Temporary utilities", "Facilities", "lump", "month", 350, 0),
        ("Mobilization / demobilization", "General", "lump", "ls", 2500, 0),
        ("Small tools & PPE", "General", "pct_labor", "%", 0, 3),
        ("Contractor's all-risk insurance", "Insurance", "pct_direct", "%", 0, 0.8),
    ]
    c.executemany(
        "INSERT INTO indirect_library(description, category, method, unit, rate, percent)"
        " VALUES (?,?,?,?,?,?)", indirects)

    # A small sample estimate so the app is not empty on first launch.
    c.execute(
        "INSERT INTO estimates(name, client, location, estimate_date, currency, hours_per_day,"
        " contingency_pct, overhead_pct, profit_pct, bond_pct, tax_pct, notes)"
        " VALUES (?,?,?,date('now'),?,?,?,?,?,?,?,?)",
        ("SAMPLE - Warehouse foundations", "Sample client", "Panama City", "USD", 8,
         3, 8, 10, 1.5, 7, "Sample estimate created on first launch. Safe to delete."))
    eid = c.lastrowid
    qtys = {"EXC-01": 180, "FRM-01": 140, "RBR-01": 4200, "CON-01": 65, "MAS-01": 220}
    for seq, row in enumerate(c.execute("SELECT * FROM task_library ORDER BY id").fetchall(), 1):
        c.execute(
            "INSERT INTO estimate_tasks(estimate_id, seq, code, description, unit, quantity,"
            " crew_id, production_rate) VALUES (?,?,?,?,?,?,?,?)",
            (eid, seq, row["code"], row["description"], row["unit"], qtys[row["code"]],
             row["crew_id"], row["production_rate"]))
        tid = c.lastrowid
        c.execute(
            "INSERT INTO estimate_task_resources(task_id, material_id, qty_per_unit)"
            " SELECT ?, material_id, qty_per_unit FROM task_library_resources WHERE task_id = ?",
            (tid, row["id"]))
    sample_ind = [
        ("Site superintendent", "Site staff", "lump", "month", 2, 3500, 0),
        ("Security guard", "Site staff", "lump", "month", 2, 1100, 0),
        ("Temporary site office & storage", "Facilities", "lump", "month", 2, 600, 0),
        ("Mobilization / demobilization", "General", "lump", "ls", 1, 2500, 0),
        ("Small tools & PPE", "General", "pct_labor", "%", 1, 0, 3),
        ("Contractor's all-risk insurance", "Insurance", "pct_direct", "%", 1, 0, 0.8),
    ]
    for seq, (d, cat, m, u, q, r, p) in enumerate(sample_ind, 1):
        c.execute(
            "INSERT INTO estimate_indirects(estimate_id, seq, description, category, method,"
            " unit, quantity, rate, percent) VALUES (?,?,?,?,?,?,?,?,?)",
            (eid, seq, d, cat, m, u, q, r, p))
