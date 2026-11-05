"""Cost engine.

Bottom-up build of a contract price:

  Crew hourly cost   = sum(labor qty x base_rate x (1 + burden%))
                     + sum(equipment qty x hourly_rate)

  Task (per estimate line, quantity Q in its unit of measure):
      crew-days      = Q / production_rate           (units per crew-day)
      crew-hours     = crew-days x hours_per_day
      labor          = crew-hours x crew labor $/hr
      equipment      = crew-hours x crew equipment $/hr
      materials      = sum(Q x qty_per_unit x unit_cost x (1 + waste%))
      consumables    = same, for items flagged as consumables
      direct cost    = labor + equipment + materials + consumables
      unit cost      = direct cost / Q

  Indirect costs:
      lump           = quantity x rate        (e.g. 3 months x $3,500)
      pct_direct     = % x total direct cost
      pct_labor      = % x total direct labor

  Markups (each applied to the running total, in this order):
      cost = direct + indirect
      + contingency% -> + overhead% -> + profit% -> + bond%  = price before tax
      + tax%                                                  = contract price

  Bid unit prices spread everything except tax over the tasks pro-rata to
  direct cost:  K = price_before_tax / direct;  bid unit price = unit cost x K.

The compute_* functions are pure (plain dicts in, plain dicts out).
load_* functions read the database and feed them.
"""

MARKUP_ORDER = (
    ("contingency", "contingency_pct", "Contingency"),
    ("overhead", "overhead_pct", "Overhead (home office)"),
    ("profit", "profit_pct", "Profit"),
    ("bond", "bond_pct", "Bonds"),
)


def _f(x):
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


# --------------------------------------------------------------------------
# Pure computations
# --------------------------------------------------------------------------

def compute_crew(crew):
    """crew = {labor: [{qty, base_rate, burden_pct}], equipment: [{qty, hourly_rate}]}"""
    labor_hr = 0.0
    headcount = 0.0
    for m in crew.get("labor", []):
        m["loaded_rate"] = _f(m.get("base_rate")) * (1 + _f(m.get("burden_pct")) / 100)
        m["cost_hr"] = _f(m.get("qty")) * m["loaded_rate"]
        labor_hr += m["cost_hr"]
        headcount += _f(m.get("qty"))
    equip_hr = 0.0
    for e in crew.get("equipment", []):
        e["cost_hr"] = _f(e.get("qty")) * _f(e.get("hourly_rate"))
        equip_hr += e["cost_hr"]
    crew["labor_hourly"] = labor_hr
    crew["equipment_hourly"] = equip_hr
    crew["hourly_cost"] = labor_hr + equip_hr
    crew["headcount"] = headcount
    return crew


def compute_task(task, crew, hours_per_day):
    """task = {quantity, production_rate, resources: [{qty_per_unit, unit_cost, waste_pct, kind}]}
    crew = computed crew dict or None."""
    q = _f(task.get("quantity"))
    rate = _f(task.get("production_rate"))
    hpd = _f(hours_per_day) or 8.0
    warnings = []

    crew_days = q / rate if rate > 0 else 0.0
    crew_hours = crew_days * hpd
    if crew and rate <= 0 and q > 0:
        warnings.append("Crew assigned but production rate is zero - no labor costed.")
    if not crew and rate > 0:
        warnings.append("Production rate set but no crew assigned.")

    labor = crew_hours * crew["labor_hourly"] if crew else 0.0
    equipment = crew_hours * crew["equipment_hourly"] if crew else 0.0
    man_hours = crew_hours * crew["headcount"] if crew else 0.0

    material = consumable = 0.0
    for r in task.get("resources", []):
        r["total_qty"] = q * _f(r.get("qty_per_unit")) * (1 + _f(r.get("waste_pct")) / 100)
        r["unit_cost_per_task_unit"] = (
            _f(r.get("qty_per_unit")) * (1 + _f(r.get("waste_pct")) / 100) * _f(r.get("unit_cost")))
        r["amount"] = r["total_qty"] * _f(r.get("unit_cost"))
        if r.get("kind") == "consumable":
            consumable += r["amount"]
        else:
            material += r["amount"]

    direct = labor + equipment + material + consumable
    task["calc"] = {
        "crew_days": crew_days,
        "crew_hours": crew_hours,
        "man_hours": man_hours,
        "labor": labor,
        "equipment": equipment,
        "material": material,
        "consumable": consumable,
        "direct": direct,
        "unit_cost": direct / q if q else 0.0,
        "unit_labor": labor / q if q else 0.0,
        "unit_equipment": equipment / q if q else 0.0,
        "unit_material": material / q if q else 0.0,
        "unit_consumable": consumable / q if q else 0.0,
        "crew_hourly": crew["hourly_cost"] if crew else 0.0,
        "warnings": warnings,
    }
    return task


def compute_indirect(item, direct_total, labor_total):
    m = item.get("method")
    if m == "pct_direct":
        amount = direct_total * _f(item.get("percent")) / 100
    elif m == "pct_labor":
        amount = labor_total * _f(item.get("percent")) / 100
    else:
        amount = _f(item.get("quantity")) * _f(item.get("rate"))
    item["amount"] = amount
    return item


def compute_estimate(estimate, tasks, crews, indirects):
    """estimate: header dict with markup percentages and hours_per_day.
    tasks: list of task dicts (with resources) referencing crew_id.
    crews: {crew_id: crew dict (raw, will be computed)}.
    indirects: list of indirect item dicts.
    Returns a summary dict; tasks and indirects are annotated in place."""
    for c in crews.values():
        compute_crew(c)

    hpd = estimate.get("hours_per_day") or 8
    totals = dict(labor=0.0, equipment=0.0, material=0.0, consumable=0.0,
                  direct=0.0, crew_hours=0.0, man_hours=0.0)
    for t in tasks:
        compute_task(t, crews.get(t.get("crew_id")), hpd)
        for k in totals:
            totals[k] += t["calc"][k]

    for i in indirects:
        compute_indirect(i, totals["direct"], totals["labor"])
    indirect_total = sum(i["amount"] for i in indirects)

    cost = totals["direct"] + indirect_total
    running = cost
    markups = []
    for key, field, label in MARKUP_ORDER:
        pct = _f(estimate.get(field))
        amt = running * pct / 100
        markups.append({"key": key, "label": label, "percent": pct, "base": running, "amount": amt})
        running += amt
    price_before_tax = running
    tax_pct = _f(estimate.get("tax_pct"))
    tax = price_before_tax * tax_pct / 100
    contract_price = price_before_tax + tax

    k = price_before_tax / totals["direct"] if totals["direct"] else 0.0
    for t in tasks:
        c = t["calc"]
        c["bid_unit_price"] = c["unit_cost"] * k
        c["bid_total"] = c["direct"] * k

    return {
        **totals,
        "indirect": indirect_total,
        "cost": cost,
        "markups": markups,
        "price_before_tax": price_before_tax,
        "tax_pct": tax_pct,
        "tax": tax,
        "contract_price": contract_price,
        "k_factor": k,
        "duration_crew_days": totals["crew_hours"] / hpd if hpd else 0.0,
    }


# --------------------------------------------------------------------------
# Database loaders
# --------------------------------------------------------------------------

def load_crew(conn, crew_id):
    row = conn.execute("SELECT * FROM crews WHERE id = ?", (crew_id,)).fetchone()
    if not row:
        return None
    crew = dict(row)
    crew["labor"] = [dict(r) for r in conn.execute(
        "SELECT cl.id, cl.labor_id, cl.qty, l.code, l.trade, l.base_rate, l.burden_pct"
        " FROM crew_labor cl JOIN labor l ON l.id = cl.labor_id"
        " WHERE cl.crew_id = ? ORDER BY cl.id", (crew_id,))]
    crew["equipment"] = [dict(r) for r in conn.execute(
        "SELECT ce.id, ce.equipment_id, ce.qty, e.code, e.description, e.hourly_rate"
        " FROM crew_equipment ce JOIN equipment e ON e.id = ce.equipment_id"
        " WHERE ce.crew_id = ? ORDER BY ce.id", (crew_id,))]
    return compute_crew(crew)


def load_all_crews(conn):
    ids = [r[0] for r in conn.execute("SELECT id FROM crews ORDER BY code")]
    return [load_crew(conn, i) for i in ids]


def _task_resources(conn, table, task_id):
    return [dict(r) for r in conn.execute(
        f"SELECT tr.id, tr.material_id, tr.qty_per_unit, m.code, m.description, m.kind,"
        f" m.unit, m.unit_cost, m.waste_pct"
        f" FROM {table} tr JOIN materials m ON m.id = tr.material_id"
        f" WHERE tr.task_id = ? ORDER BY m.kind DESC, tr.id", (task_id,))]


def load_library_task(conn, task_id):
    row = conn.execute("SELECT * FROM task_library WHERE id = ?", (task_id,)).fetchone()
    if not row:
        return None
    t = dict(row)
    t["resources"] = _task_resources(conn, "task_library_resources", task_id)
    crew = load_crew(conn, t["crew_id"]) if t["crew_id"] else None
    # Preview cost per unit of measure (quantity 1, 8 h/day).
    preview = compute_task({**t, "quantity": 1, "resources": [dict(r) for r in t["resources"]]},
                           crew, 8)
    t["crew_name"] = crew["name"] if crew else ""
    t["unit_cost_preview"] = preview["calc"]["unit_cost"]
    return t


def load_estimate(conn, estimate_id):
    row = conn.execute("SELECT * FROM estimates WHERE id = ?", (estimate_id,)).fetchone()
    if not row:
        return None
    est = dict(row)
    tasks = [dict(r) for r in conn.execute(
        "SELECT * FROM estimate_tasks WHERE estimate_id = ? ORDER BY seq, id", (estimate_id,))]
    for t in tasks:
        t["resources"] = _task_resources(conn, "estimate_task_resources", t["id"])
    crews = {}
    for t in tasks:
        cid = t["crew_id"]
        if cid and cid not in crews:
            crews[cid] = load_crew(conn, cid)
    for t in tasks:
        c = crews.get(t["crew_id"])
        t["crew_code"] = c["code"] if c else ""
        t["crew_name"] = c["name"] if c else ""
    indirects = [dict(r) for r in conn.execute(
        "SELECT * FROM estimate_indirects WHERE estimate_id = ? ORDER BY seq, id", (estimate_id,))]
    summary = compute_estimate(est, tasks, crews, indirects)
    return {"estimate": est, "tasks": tasks, "indirects": indirects,
            "crews": list(crews.values()), "summary": summary}
