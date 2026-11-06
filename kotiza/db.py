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

import json
import os
import sqlite3

from . import rates_pa

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
    category    TEXT NOT NULL DEFAULT '',  -- e.g. convention wage category
    base_rate   REAL NOT NULL DEFAULT 0,   -- wage per hour (private works)
    public_rate REAL NOT NULL DEFAULT 0,   -- wage per hour on public works (0 = same)
    special_rate REAL NOT NULL DEFAULT 0,  -- special projects, Cl. 127 (0 = private + 11%)
    use_standard_burden INTEGER NOT NULL DEFAULT 1,  -- 1 = use burden calculator
    burden_pct  REAL NOT NULL DEFAULT 0    -- custom burden when not standard
);

-- Standard labor burden (cargas sociales y prestaciones) - see rates_pa.py
CREATE TABLE IF NOT EXISTS burden_components (
    id       INTEGER PRIMARY KEY,
    sort     INTEGER NOT NULL DEFAULT 0,
    name     TEXT NOT NULL,
    kind     TEXT NOT NULL DEFAULT 'charge' CHECK (kind IN ('leave', 'charge', 'fixed')),
    percent  REAL NOT NULL DEFAULT 0,      -- % for leave/charge, B/. per hour for fixed
    active   INTEGER NOT NULL DEFAULT 1,
    notes    TEXT NOT NULL DEFAULT ''
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
    waste_pct    REAL NOT NULL DEFAULT 0,
    source       TEXT NOT NULL DEFAULT '',  -- where the price came from (quote, list, CGR…)
    price_date   TEXT NOT NULL DEFAULT '',  -- YYYY-MM-DD
    notes        TEXT NOT NULL DEFAULT ''
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
    wage_scale       TEXT NOT NULL DEFAULT 'private'
                     CHECK (wage_scale IN ('private', 'public', 'special')),
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


# Columns added after the first release: (table, column, definition).
# Existing databases get them via ALTER TABLE on startup.
MIGRATIONS = [
    ("labor", "category", "TEXT NOT NULL DEFAULT ''"),
    ("labor", "public_rate", "REAL NOT NULL DEFAULT 0"),
    # Existing trades keep their own burden % until switched to standard.
    ("labor", "use_standard_burden", "INTEGER NOT NULL DEFAULT 0"),
    ("estimates", "wage_scale", "TEXT NOT NULL DEFAULT 'private'"),
    ("labor", "special_rate", "REAL NOT NULL DEFAULT 0"),
    ("materials", "source", "TEXT NOT NULL DEFAULT ''"),
    ("materials", "price_date", "TEXT NOT NULL DEFAULT ''"),
    ("materials", "notes", "TEXT NOT NULL DEFAULT ''"),
]

# Tables whose CHECK constraints were widened: (table, text the current definition contains).
# Older databases are rebuilt with the current definition, keeping all rows.
REBUILDS = [
    ("burden_components", "'fixed'"),
    ("estimates", "'special'"),
]


def _table_ddl(table):
    start = SCHEMA.index(f"CREATE TABLE IF NOT EXISTS {table} (")
    return SCHEMA[start:SCHEMA.index(");", start) + 2]


def rebuild_outdated_tables(conn):
    todo = []
    for table, marker in REBUILDS:
        row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                           (table,)).fetchone()
        if row and "CHECK" in row[0] and marker not in row[0]:
            todo.append(table)
    if not todo:
        return
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        for table in todo:
            old_cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
            conn.execute(_table_ddl(table).replace(
                f"CREATE TABLE IF NOT EXISTS {table} (", f"CREATE TABLE {table}__new ("))
            new_cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table}__new)")}
            cols = ", ".join(c for c in old_cols if c in new_cols)
            conn.execute(f"INSERT INTO {table}__new ({cols}) SELECT {cols} FROM {table}")
            conn.execute(f"DROP TABLE {table}")
            conn.execute(f"ALTER TABLE {table}__new RENAME TO {table}")
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def migrate(conn):
    for table, col, ddl in MIGRATIONS:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")


def init_db(conn, seed=True):
    """Create tables, upgrade older databases, load sample data if empty."""
    conn.executescript(SCHEMA)
    migrate(conn)
    rebuild_outdated_tables(conn)
    conn.executescript(SCHEMA)  # recreate indexes dropped with rebuilt tables
    if conn.execute("SELECT COUNT(*) FROM burden_components").fetchone()[0] == 0:
        seed_burden(conn)
    empty = conn.execute("SELECT COUNT(*) FROM labor").fetchone()[0] == 0
    if seed and empty:
        seed_sample_data(conn)
    conn.commit()


def seed_burden(conn):
    conn.executemany(
        "INSERT INTO burden_components(sort, name, kind, percent, notes) VALUES (?,?,?,?,?)",
        rates_pa.BURDEN_COMPONENTS)


def standard_burden(conn):
    """Returns (burden %, fixed B/. per hour) from the burden calculator."""
    comps = [dict(r) for r in conn.execute("SELECT kind, percent, active FROM burden_components")]
    _, _, pct, fixed = rates_pa.total_burden(comps)
    return pct, fixed


def _ensure_units(conn, codes):
    names = {"ml": "metro lineal", "und": "unidad", "saco": "saco", "pza": "pieza", "gal": "galón",
             "rollo": "rollo", "lb": "libra", "ft": "pie", "ft3": "pie cúbico", "lt": "litro"}
    for code in codes:
        conn.execute("INSERT OR IGNORE INTO units(code, name) VALUES (?, ?)", (code, names.get(code, code)))
    return None


def load_capac_rates(conn):
    """Insert or update the convention trades (matched by code), plus the
    convention's indirect items. Returns (inserted, updated)."""
    ins = upd = 0
    for code, trade, group, priv, pub, special in rates_pa.TRADES:
        row = conn.execute("SELECT id FROM labor WHERE code = ?", (code,)).fetchone()
        if row:
            conn.execute(
                "UPDATE labor SET trade = ?, category = ?, base_rate = ?, public_rate = ?,"
                " special_rate = ?, use_standard_burden = 1 WHERE id = ?",
                (trade, group, priv, pub, special, row[0]))
            upd += 1
        else:
            conn.execute(
                "INSERT INTO labor(code, trade, category, base_rate, public_rate, special_rate,"
                " use_standard_burden, burden_pct) VALUES (?,?,?,?,?,?,1,0)",
                (code, trade, group, priv, pub, special))
            ins += 1
    for desc, cat, method, unit, rate, pct in rates_pa.INDIRECT_ITEMS:
        if not conn.execute("SELECT 1 FROM indirect_library WHERE description = ?", (desc,)).fetchone():
            conn.execute(
                "INSERT INTO indirect_library(description, category, method, unit, rate, percent)"
                " VALUES (?,?,?,?,?,?)", (desc, cat, method, unit, rate, pct))
    return ins, upd


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CGR_MATERIALS = os.path.join(DATA_DIR, "materiales_cgr_2025.json")


def load_cgr_materials(conn, path=CGR_MATERIALS):
    """Load the Contraloría reference material prices. Rows are matched by
    code: rows that came from the same source are updated, rows with that code
    from any other source (your own prices) are left alone and reported.
    Returns (inserted, updated, skipped_codes)."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    src = data["source_short"]
    ins = upd = 0
    skipped = []
    units = set()
    for m in data["materials"]:
        notes = f"Used in {m['uses']} CGR analyses, e.g. {m['example']}"
        row = conn.execute("SELECT id, source FROM materials WHERE code = ?", (m["code"],)).fetchone()
        vals = (m["description"], m["kind"], m["category"], m["unit"], m["unit_cost"], src,
                data["price_date"], notes)
        if row and row["source"] != src:
            skipped.append(m["code"])
            continue
        if row:
            conn.execute("UPDATE materials SET description = ?, kind = ?, category = ?, unit = ?,"
                         " unit_cost = ?, source = ?, price_date = ?, notes = ? WHERE id = ?",
                         (*vals, row["id"]))
            upd += 1
        else:
            conn.execute("INSERT INTO materials(code, description, kind, category, unit, unit_cost,"
                         " source, price_date, notes) VALUES (?,?,?,?,?,?,?,?,?)", (m["code"], *vals))
            ins += 1
        units.add(m["unit"])
    _ensure_units(conn, units)
    return ins, upd, skipped


def load_capac_rendimientos(conn):
    """Add the Anexo IA productivity table as crews + standard tasks (matched
    by code; existing ones are updated). Returns (tasks added, tasks updated)."""
    lab = {r[0]: r[1] for r in conn.execute("SELECT code, id FROM labor")}
    needed = {c for _, _, members in rates_pa.RENDIMIENTO_CREWS for c, _ in members}
    if needed - lab.keys():
        load_capac_rates(conn)
        lab = {r[0]: r[1] for r in conn.execute("SELECT code, id FROM labor")}
    crew_ids = {}
    for code, name, members in rates_pa.RENDIMIENTO_CREWS:
        row = conn.execute("SELECT id FROM crews WHERE code = ?", (code,)).fetchone()
        if row:
            cid = row[0]
        else:
            cid = conn.execute(
                "INSERT INTO crews(code, name, description) VALUES (?,?,?)",
                (code, name, "Personal base del Anexo IA, Convención CAPAC-SUNTRACS")).lastrowid
            for lc, qty in members:
                conn.execute("INSERT INTO crew_labor(crew_id, labor_id, qty) VALUES (?,?,?)",
                             (cid, lab[lc], qty))
        crew_ids[code] = cid
    _ensure_units(conn, {r[5] for r in rates_pa.RENDIMIENTOS})
    ins = upd = 0
    for code, cat, desc, cond, crew, unit, rate, bonus in rates_pa.RENDIMIENTOS:
        notes = " ".join(x for x in (
            f"Anexo IA CAPAC-SUNTRACS: rendimiento MÍNIMO de {rate:.2f} {unit} por jornada de 8 h"
            f" (umbral de prima de producción: {bonus:.2f}).",
            f"{cond.rstrip('.')}." if cond else "",
            "Your crews usually exceed the minimum; adjust from your own records.",
            "Labor only: add materials and consumables.") if x)
        row = conn.execute("SELECT id FROM task_library WHERE code = ?", (code,)).fetchone()
        vals = (desc, f"Rendimientos {cat}", unit, crew_ids[crew], round(rate, 3), notes)
        if row:
            conn.execute("UPDATE task_library SET description = ?, category = ?, unit = ?,"
                         " crew_id = ?, production_rate = ?, notes = ? WHERE id = ?", (*vals, row[0]))
            upd += 1
        else:
            conn.execute("INSERT INTO task_library(code, description, category, unit, crew_id,"
                         " production_rate, notes) VALUES (?,?,?,?,?,?,?)", (code, *vals))
            ins += 1
    return ins, upd


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

    # Foreman is not a convention category - set your own rate.
    c.execute(
        "INSERT INTO labor(code, trade, category, base_rate, public_rate, use_standard_burden,"
        " burden_pct) VALUES ('FOR', 'Capataz (foreman)', 'Fuera de convención', 8.00, 8.00, 1, 0)")
    load_capac_rates(conn)

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
        "INSERT INTO materials(code, description, kind, category, unit, unit_cost, waste_pct, source)"
        " VALUES (?,?,?,?,?,?,?,'Sample data')", materials)

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

    # Productivity library from the convention (Anexo IA).
    load_capac_rendimientos(conn)

    # Reference material prices from the Contraloría (public works, July 2025).
    load_cgr_materials(conn)
