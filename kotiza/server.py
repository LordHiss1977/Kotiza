"""HTTP server: JSON API + static single-page UI. Standard library only."""

import csv
import io
import json
import mimetypes
import os
import re
import sqlite3
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from . import calc, db, rates_pa

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


# --------------------------------------------------------------------------
# Field validation
# --------------------------------------------------------------------------

def _num(v, name):
    if v in (None, ""):
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        raise ApiError(400, f"'{name}' must be a number")


def _ref(v, name):
    if v in (None, "", 0, "0"):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        raise ApiError(400, f"'{name}' must be an id")


def clean(body, spec, required=(), partial=False):
    """spec: {field: 'str' | 'num' | 'ref' | ('enum', values)}"""
    out = {}
    for f, kind in spec.items():
        if f not in body:
            continue
        v = body[f]
        if kind == "num":
            out[f] = _num(v, f)
        elif kind == "ref":
            out[f] = _ref(v, f)
        elif isinstance(kind, tuple) and kind[0] == "enum":
            if v not in kind[1]:
                raise ApiError(400, f"'{f}' must be one of {', '.join(kind[1])}")
            out[f] = v
        else:
            out[f] = "" if v is None else str(v).strip()
    if not partial:
        for r in required:
            if not out.get(r):
                raise ApiError(400, f"'{r}' is required")
    else:
        for r in required:
            if r in out and not out[r]:
                raise ApiError(400, f"'{r}' is required")
    return out


def insert(conn, table, data):
    cols = ", ".join(data)
    qs = ", ".join("?" for _ in data)
    cur = conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({qs})", list(data.values()))
    return cur.lastrowid


def update(conn, table, row_id, data):
    if not data:
        return
    sets = ", ".join(f"{k} = ?" for k in data)
    cur = conn.execute(f"UPDATE {table} SET {sets} WHERE id = ?", [*data.values(), row_id])
    if cur.rowcount == 0:
        raise ApiError(404, "Not found")


def delete(conn, table, row_id):
    cur = conn.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))
    if cur.rowcount == 0:
        raise ApiError(404, "Not found")


# --------------------------------------------------------------------------
# Simple resource tables (generic CRUD)
# --------------------------------------------------------------------------

METHODS = ("lump", "pct_direct", "pct_labor")

SIMPLE = {
    "units": ("units", {"code": "str", "name": "str"}, ("code",), "code"),
    "labor": ("labor", {"code": "str", "trade": "str", "category": "str", "base_rate": "num",
                        "public_rate": "num", "use_standard_burden": "num", "burden_pct": "num"},
              ("code", "trade"), "code"),
    "burden-components": ("burden_components", {"sort": "num", "name": "str",
                                                "kind": ("enum", ("leave", "charge")),
                                                "percent": "num", "active": "num",
                                                "notes": "str"},
                          ("name",), "sort, id"),
    "equipment": ("equipment", {"code": "str", "description": "str", "hourly_rate": "num"},
                  ("code", "description"), "code"),
    "materials": ("materials", {"code": "str", "description": "str",
                                "kind": ("enum", ("material", "consumable")),
                                "category": "str", "unit": "str",
                                "unit_cost": "num", "waste_pct": "num"},
                  ("code", "description"), "kind, category, code"),
    "indirect-library": ("indirect_library", {"description": "str", "category": "str",
                                              "method": ("enum", METHODS), "unit": "str",
                                              "rate": "num", "percent": "num"},
                         ("description",), "category, description"),
}

CREW_SPEC = {"code": "str", "name": "str", "description": "str"}
LIB_SPEC = {"code": "str", "description": "str", "category": "str", "unit": "str",
            "crew_id": "ref", "production_rate": "num", "notes": "str"}
EST_SPEC = {"name": "str", "client": "str", "location": "str", "estimate_date": "str",
            "currency": "str", "wage_scale": ("enum", ("private", "public")),
            "status": "str", "hours_per_day": "num",
            "contingency_pct": "num", "overhead_pct": "num", "profit_pct": "num",
            "bond_pct": "num", "tax_pct": "num", "notes": "str"}
TASK_SPEC = {"code": "str", "description": "str", "unit": "str", "quantity": "num",
             "crew_id": "ref", "production_rate": "num", "notes": "str"}
IND_SPEC = {"description": "str", "category": "str", "method": ("enum", METHODS),
            "unit": "str", "quantity": "num", "rate": "num", "percent": "num"}


def list_simple(conn, res):
    table, _, _, order = SIMPLE[res]
    rows = [dict(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY {order}")]
    if res == "labor":
        std = db.standard_burden_pct(conn)
        for r in rows:
            b = std if r["use_standard_burden"] else r["burden_pct"]
            pub = r["public_rate"] or r["base_rate"]
            r["effective_burden"] = b
            r["loaded_rate"] = r["base_rate"] * (1 + b / 100)
            r["loaded_public"] = pub * (1 + b / 100)
    return rows


def burden_summary(conn):
    comps = [dict(r) for r in conn.execute("SELECT * FROM burden_components ORDER BY sort, id")]
    leave, charge, total = rates_pa.total_burden(comps)
    return {"components": comps, "leave_pct": leave, "charge_pct": charge, "total_pct": total,
            "convention": rates_pa.CONVENTION, "category_rates": rates_pa.CATEGORY_RATES}


# --------------------------------------------------------------------------
# Composite resources
# --------------------------------------------------------------------------

def replace_children(conn, table, parent_col, parent_id, ref_col, qty_col, items):
    conn.execute(f"DELETE FROM {table} WHERE {parent_col} = ?", (parent_id,))
    for it in items or []:
        ref = _ref(it.get(ref_col), ref_col)
        if not ref:
            continue
        conn.execute(f"INSERT INTO {table} ({parent_col}, {ref_col}, {qty_col}) VALUES (?,?,?)",
                     (parent_id, ref, _num(it.get(qty_col), qty_col)))


def save_crew(conn, body, crew_id=None):
    data = clean(body, CREW_SPEC, ("code", "name"), partial=crew_id is not None)
    if crew_id is None:
        crew_id = insert(conn, "crews", data)
    else:
        update(conn, "crews", crew_id, data)
    if "labor" in body:
        replace_children(conn, "crew_labor", "crew_id", crew_id, "labor_id", "qty", body["labor"])
    if "equipment" in body:
        replace_children(conn, "crew_equipment", "crew_id", crew_id, "equipment_id", "qty",
                         body["equipment"])
    return calc.load_crew(conn, crew_id)


def save_library_task(conn, body, task_id=None):
    data = clean(body, LIB_SPEC, ("code", "description"), partial=task_id is not None)
    if task_id is None:
        task_id = insert(conn, "task_library", data)
    else:
        update(conn, "task_library", task_id, data)
    if "resources" in body:
        replace_children(conn, "task_library_resources", "task_id", task_id, "material_id",
                         "qty_per_unit", body["resources"])
    return calc.load_library_task(conn, task_id)


def touch(conn, estimate_id):
    conn.execute("UPDATE estimates SET updated_at = datetime('now') WHERE id = ?", (estimate_id,))


def estimate_of(conn, table, row_id):
    r = conn.execute(f"SELECT estimate_id FROM {table} WHERE id = ?", (row_id,)).fetchone()
    if not r:
        raise ApiError(404, "Not found")
    return r[0]


def next_seq(conn, table, estimate_id):
    return conn.execute(f"SELECT COALESCE(MAX(seq), 0) + 1 FROM {table} WHERE estimate_id = ?",
                        (estimate_id,)).fetchone()[0]


def add_task(conn, estimate_id, body):
    if not conn.execute("SELECT 1 FROM estimates WHERE id = ?", (estimate_id,)).fetchone():
        raise ApiError(404, "Estimate not found")
    seq = next_seq(conn, "estimate_tasks", estimate_id)
    lib_id = _ref(body.get("library_id"), "library_id")
    if lib_id:
        lib = conn.execute("SELECT * FROM task_library WHERE id = ?", (lib_id,)).fetchone()
        if not lib:
            raise ApiError(404, "Library task not found")
        tid = insert(conn, "estimate_tasks", {
            "estimate_id": estimate_id, "seq": seq, "code": lib["code"],
            "description": lib["description"], "unit": lib["unit"],
            "quantity": _num(body.get("quantity"), "quantity"),
            "crew_id": lib["crew_id"], "production_rate": lib["production_rate"],
            "notes": lib["notes"]})
        conn.execute(
            "INSERT INTO estimate_task_resources(task_id, material_id, qty_per_unit)"
            " SELECT ?, material_id, qty_per_unit FROM task_library_resources WHERE task_id = ?",
            (tid, lib_id))
    else:
        data = clean(body, TASK_SPEC, ("description",))
        tid = insert(conn, "estimate_tasks", {"estimate_id": estimate_id, "seq": seq, **data})
        if "resources" in body:
            replace_children(conn, "estimate_task_resources", "task_id", tid, "material_id",
                             "qty_per_unit", body["resources"])
    touch(conn, estimate_id)
    return {"id": tid}


def update_task(conn, task_id, body):
    eid = estimate_of(conn, "estimate_tasks", task_id)
    update(conn, "estimate_tasks", task_id, clean(body, TASK_SPEC, ("description",), partial=True))
    if "resources" in body:
        replace_children(conn, "estimate_task_resources", "task_id", task_id, "material_id",
                         "qty_per_unit", body["resources"])
    touch(conn, eid)
    return {"id": task_id}


def move_row(conn, table, row_id, direction):
    eid = estimate_of(conn, table, row_id)
    ids = [r[0] for r in conn.execute(
        f"SELECT id FROM {table} WHERE estimate_id = ? ORDER BY seq, id", (eid,))]
    i = ids.index(row_id)
    j = i + (1 if direction > 0 else -1)
    if 0 <= j < len(ids):
        ids[i], ids[j] = ids[j], ids[i]
    for seq, rid in enumerate(ids, 1):
        conn.execute(f"UPDATE {table} SET seq = ? WHERE id = ?", (seq, rid))
    touch(conn, eid)
    return {"ok": True}


def task_to_library(conn, task_id):
    t = conn.execute("SELECT * FROM estimate_tasks WHERE id = ?", (task_id,)).fetchone()
    if not t:
        raise ApiError(404, "Not found")
    code = t["code"] or f"T-{task_id}"
    base, n = code, 1
    while conn.execute("SELECT 1 FROM task_library WHERE code = ?", (code,)).fetchone():
        n += 1
        code = f"{base}-{n}"
    lid = insert(conn, "task_library", {
        "code": code, "description": t["description"], "unit": t["unit"],
        "crew_id": t["crew_id"], "production_rate": t["production_rate"], "notes": t["notes"]})
    conn.execute(
        "INSERT INTO task_library_resources(task_id, material_id, qty_per_unit)"
        " SELECT ?, material_id, qty_per_unit FROM estimate_task_resources WHERE task_id = ?",
        (lid, task_id))
    return {"id": lid, "code": code}


def add_indirect(conn, estimate_id, body):
    if not conn.execute("SELECT 1 FROM estimates WHERE id = ?", (estimate_id,)).fetchone():
        raise ApiError(404, "Estimate not found")
    seq = next_seq(conn, "estimate_indirects", estimate_id)
    lib_id = _ref(body.get("library_id"), "library_id")
    if lib_id:
        lib = conn.execute("SELECT * FROM indirect_library WHERE id = ?", (lib_id,)).fetchone()
        if not lib:
            raise ApiError(404, "Library item not found")
        data = {k: lib[k] for k in ("description", "category", "method", "unit", "rate", "percent")}
        data["quantity"] = 1
    else:
        data = clean(body, IND_SPEC, ("description",))
    iid = insert(conn, "estimate_indirects", {"estimate_id": estimate_id, "seq": seq, **data})
    touch(conn, estimate_id)
    return {"id": iid}


def list_estimates(conn):
    out = []
    for r in conn.execute("SELECT id FROM estimates ORDER BY updated_at DESC, id DESC"):
        full = calc.load_estimate(conn, r[0])
        e = full["estimate"]
        s = full["summary"]
        out.append({**e, "task_count": len(full["tasks"]), "direct": s["direct"],
                    "contract_price": s["contract_price"]})
    return out


def duplicate_estimate(conn, estimate_id):
    e = conn.execute("SELECT * FROM estimates WHERE id = ?", (estimate_id,)).fetchone()
    if not e:
        raise ApiError(404, "Not found")
    data = {k: e[k] for k in EST_SPEC}
    data["name"] = f"{e['name']} (copy)"
    data["status"] = "draft"
    new_id = insert(conn, "estimates", data)
    for t in conn.execute("SELECT * FROM estimate_tasks WHERE estimate_id = ? ORDER BY seq, id",
                          (estimate_id,)).fetchall():
        tid = insert(conn, "estimate_tasks", {
            "estimate_id": new_id, "seq": t["seq"],
            **{k: t[k] for k in TASK_SPEC}})
        conn.execute(
            "INSERT INTO estimate_task_resources(task_id, material_id, qty_per_unit)"
            " SELECT ?, material_id, qty_per_unit FROM estimate_task_resources WHERE task_id = ?",
            (tid, t["id"]))
    conn.execute(
        "INSERT INTO estimate_indirects(estimate_id, seq, description, category, method, unit,"
        " quantity, rate, percent) SELECT ?, seq, description, category, method, unit, quantity,"
        " rate, percent FROM estimate_indirects WHERE estimate_id = ?", (new_id, estimate_id))
    return {"id": new_id}


def export_csv(conn, estimate_id):
    full = calc.load_estimate(conn, estimate_id)
    if not full:
        raise ApiError(404, "Not found")
    e, s = full["estimate"], full["summary"]
    buf = io.StringIO()
    w = csv.writer(buf)
    r2 = lambda x: round(x, 2)
    w.writerow(["Estimate", e["name"]])
    w.writerow(["Client", e["client"]])
    w.writerow(["Location", e["location"]])
    w.writerow(["Date", e["estimate_date"]])
    w.writerow(["Currency", e["currency"]])
    w.writerow([])
    w.writerow(["BILL OF QUANTITIES"])
    w.writerow(["Item", "Code", "Description", "Unit", "Quantity", "Crew", "Rate/day",
                "Crew-days", "Labor", "Equipment", "Materials", "Consumables",
                "Direct cost", "Unit cost", "Bid unit price", "Bid total"])
    for n, t in enumerate(full["tasks"], 1):
        c = t["calc"]
        w.writerow([n, t["code"], t["description"], t["unit"], t["quantity"], t["crew_code"],
                    t["production_rate"], round(c["crew_days"], 2), r2(c["labor"]),
                    r2(c["equipment"]), r2(c["material"]), r2(c["consumable"]), r2(c["direct"]),
                    r2(c["unit_cost"]), r2(c["bid_unit_price"]), r2(c["bid_total"])])
    w.writerow([])
    w.writerow(["INDIRECT COSTS"])
    w.writerow(["Description", "Category", "Method", "Unit", "Quantity", "Rate", "Percent",
                "Amount"])
    for i in full["indirects"]:
        w.writerow([i["description"], i["category"], i["method"], i["unit"], i["quantity"],
                    i["rate"], i["percent"], r2(i["amount"])])
    w.writerow([])
    w.writerow(["SUMMARY"])
    for label, key in (("Labor", "labor"), ("Equipment", "equipment"),
                       ("Materials", "material"), ("Consumables", "consumable"),
                       ("Total direct cost", "direct"), ("Indirect costs", "indirect"),
                       ("Total cost", "cost")):
        w.writerow([label, r2(s[key])])
    for m in s["markups"]:
        w.writerow([f"{m['label']} ({m['percent']}%)", r2(m["amount"])])
    w.writerow(["Price before tax", r2(s["price_before_tax"])])
    w.writerow([f"Tax ({s['tax_pct']}%)", r2(s["tax"])])
    w.writerow(["CONTRACT PRICE", r2(s["contract_price"])])
    w.writerow(["K factor (price before tax / direct)", round(s["k_factor"], 4)])
    return buf.getvalue()


# --------------------------------------------------------------------------
# Routing
# --------------------------------------------------------------------------

ROUTES = []


def route(method, pattern):
    def deco(fn):
        ROUTES.append((method, re.compile("^" + pattern + "$"), fn))
        return fn
    return deco


SIMPLE_RE = "(" + "|".join(re.escape(k) for k in SIMPLE) + ")"


@route("GET", "/api/" + SIMPLE_RE)
def _list_simple(conn, body, res):
    return list_simple(conn, res)


@route("POST", "/api/" + SIMPLE_RE)
def _create_simple(conn, body, res):
    table, spec, req, _ = SIMPLE[res]
    return {"id": insert(conn, table, clean(body, spec, req))}


@route("PUT", "/api/" + SIMPLE_RE + r"/(\d+)")
def _update_simple(conn, body, res, rid):
    table, spec, req, _ = SIMPLE[res]
    update(conn, table, int(rid), clean(body, spec, req, partial=True))
    return {"id": int(rid)}


@route("DELETE", "/api/" + SIMPLE_RE + r"/(\d+)")
def _delete_simple(conn, body, res, rid):
    delete(conn, SIMPLE[res][0], int(rid))
    return {"ok": True}


@route("GET", "/api/burden")
def _burden(conn, body):
    return burden_summary(conn)


@route("POST", "/api/burden/reset")
def _burden_reset(conn, body):
    conn.execute("DELETE FROM burden_components")
    db.seed_burden(conn)
    return burden_summary(conn)


@route("POST", "/api/labor/load-capac")
def _load_capac(conn, body):
    ins, upd = db.load_capac_rates(conn)
    return {"inserted": ins, "updated": upd}


@route("GET", "/api/crews")
def _crews(conn, body):
    return calc.load_all_crews(conn)


@route("GET", r"/api/crews/(\d+)")
def _crew(conn, body, cid):
    c = calc.load_crew(conn, int(cid))
    if not c:
        raise ApiError(404, "Not found")
    return c


@route("POST", "/api/crews")
def _crew_create(conn, body):
    return save_crew(conn, body)


@route("PUT", r"/api/crews/(\d+)")
def _crew_update(conn, body, cid):
    return save_crew(conn, body, int(cid))


@route("DELETE", r"/api/crews/(\d+)")
def _crew_delete(conn, body, cid):
    delete(conn, "crews", int(cid))
    return {"ok": True}


@route("GET", "/api/library")
def _library(conn, body):
    ids = [r[0] for r in conn.execute("SELECT id FROM task_library ORDER BY category, code")]
    return [calc.load_library_task(conn, i) for i in ids]


@route("GET", r"/api/library/(\d+)")
def _library_one(conn, body, tid):
    t = calc.load_library_task(conn, int(tid))
    if not t:
        raise ApiError(404, "Not found")
    return t


@route("POST", "/api/library")
def _library_create(conn, body):
    return save_library_task(conn, body)


@route("PUT", r"/api/library/(\d+)")
def _library_update(conn, body, tid):
    return save_library_task(conn, body, int(tid))


@route("DELETE", r"/api/library/(\d+)")
def _library_delete(conn, body, tid):
    delete(conn, "task_library", int(tid))
    return {"ok": True}


@route("GET", "/api/estimates")
def _estimates(conn, body):
    return list_estimates(conn)


@route("POST", "/api/estimates")
def _estimate_create(conn, body):
    data = clean(body, EST_SPEC, ("name",))
    data.setdefault("hours_per_day", 8)
    return {"id": insert(conn, "estimates", data)}


@route("GET", r"/api/estimates/(\d+)")
def _estimate(conn, body, eid):
    e = calc.load_estimate(conn, int(eid))
    if not e:
        raise ApiError(404, "Not found")
    return e


@route("PUT", r"/api/estimates/(\d+)")
def _estimate_update(conn, body, eid):
    data = clean(body, EST_SPEC, ("name",), partial=True)
    if "hours_per_day" in data and data["hours_per_day"] <= 0:
        raise ApiError(400, "Hours per day must be greater than zero")
    update(conn, "estimates", int(eid), data)
    touch(conn, int(eid))
    return {"id": int(eid)}


@route("DELETE", r"/api/estimates/(\d+)")
def _estimate_delete(conn, body, eid):
    delete(conn, "estimates", int(eid))
    return {"ok": True}


@route("POST", r"/api/estimates/(\d+)/duplicate")
def _estimate_dup(conn, body, eid):
    return duplicate_estimate(conn, int(eid))


@route("POST", r"/api/estimates/(\d+)/tasks")
def _task_add(conn, body, eid):
    return add_task(conn, int(eid), body)


@route("PUT", r"/api/tasks/(\d+)")
def _task_update(conn, body, tid):
    return update_task(conn, int(tid), body)


@route("DELETE", r"/api/tasks/(\d+)")
def _task_delete(conn, body, tid):
    eid = estimate_of(conn, "estimate_tasks", int(tid))
    delete(conn, "estimate_tasks", int(tid))
    touch(conn, eid)
    return {"ok": True}


@route("POST", r"/api/tasks/(\d+)/move")
def _task_move(conn, body, tid):
    return move_row(conn, "estimate_tasks", int(tid), int(_num(body.get("dir"), "dir")))


@route("POST", r"/api/tasks/(\d+)/to-library")
def _task_to_lib(conn, body, tid):
    return task_to_library(conn, int(tid))


@route("POST", r"/api/estimates/(\d+)/indirects")
def _ind_add(conn, body, eid):
    return add_indirect(conn, int(eid), body)


@route("PUT", r"/api/indirects/(\d+)")
def _ind_update(conn, body, iid):
    eid = estimate_of(conn, "estimate_indirects", int(iid))
    update(conn, "estimate_indirects", int(iid),
           clean(body, IND_SPEC, ("description",), partial=True))
    touch(conn, eid)
    return {"id": int(iid)}


@route("DELETE", r"/api/indirects/(\d+)")
def _ind_delete(conn, body, iid):
    eid = estimate_of(conn, "estimate_indirects", int(iid))
    delete(conn, "estimate_indirects", int(iid))
    touch(conn, eid)
    return {"ok": True}


@route("POST", r"/api/indirects/(\d+)/move")
def _ind_move(conn, body, iid):
    return move_row(conn, "estimate_indirects", int(iid), int(_num(body.get("dir"), "dir")))


def integrity_message(err):
    msg = str(err)
    if "FOREIGN KEY" in msg:
        return "This record is in use (by a crew, task or estimate) and cannot be deleted."
    if "UNIQUE" in msg:
        return "That code is already used. Codes must be unique."
    if "CHECK" in msg:
        return "Invalid value."
    return msg


class Handler(BaseHTTPRequestHandler):
    db_path = None
    server_version = "Kotiza/1.0"

    def log_message(self, fmt, *args):
        if os.environ.get("KOTIZA_LOG"):
            super().log_message(fmt, *args)

    def _send(self, status, payload, ctype="application/json; charset=utf-8", headers=None):
        data = payload if isinstance(payload, bytes) else (
            payload.encode("utf-8") if isinstance(payload, str)
            else json.dumps(payload).encode("utf-8"))
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _api(self, method):
        path = urlparse(self.path).path
        body = {}
        if method in ("POST", "PUT"):
            n = int(self.headers.get("Content-Length") or 0)
            if n:
                try:
                    body = json.loads(self.rfile.read(n) or b"{}")
                except json.JSONDecodeError:
                    return self._send(400, {"error": "Invalid JSON"})
            if not isinstance(body, dict):
                return self._send(400, {"error": "Expected a JSON object"})

        m = re.match(r"^/api/estimates/(\d+)/export\.csv$", path)
        if m and method == "GET":
            conn = db.connect(self.db_path)
            try:
                text = export_csv(conn, int(m.group(1)))
            except ApiError as e:
                return self._send(e.status, {"error": e.message})
            finally:
                conn.close()
            return self._send(200, "﻿" + text, "text/csv; charset=utf-8",
                              {"Content-Disposition": f'attachment; filename="estimate-{m.group(1)}.csv"'})

        for meth, rx, fn in ROUTES:
            if meth != method:
                continue
            m = rx.match(path)
            if not m:
                continue
            conn = db.connect(self.db_path)
            try:
                result = fn(conn, body, *m.groups())
                conn.commit()
                return self._send(200, result)
            except ApiError as e:
                conn.rollback()
                return self._send(e.status, {"error": e.message})
            except sqlite3.IntegrityError as e:
                conn.rollback()
                return self._send(409, {"error": integrity_message(e)})
            except Exception as e:  # noqa: BLE001
                conn.rollback()
                traceback.print_exc()
                return self._send(500, {"error": f"Server error: {e}"})
            finally:
                conn.close()
        return self._send(404, {"error": "Unknown endpoint"})

    def _static(self):
        path = urlparse(self.path).path
        if path in ("", "/"):
            path = "/index.html"
        full = os.path.normpath(os.path.join(STATIC_DIR, path.lstrip("/")))
        if not full.startswith(STATIC_DIR) or not os.path.isfile(full):
            full = os.path.join(STATIC_DIR, "index.html")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as fh:
            self._send(200, fh.read(), ctype)

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self._api("GET")
        return self._static()

    def do_POST(self):
        return self._api("POST")

    def do_PUT(self):
        return self._api("PUT")

    def do_DELETE(self):
        return self._api("DELETE")


def make_server(host="127.0.0.1", port=8000, db_path=None):
    conn = db.connect(db_path)
    db.init_db(conn)
    conn.close()
    handler = type("BoundHandler", (Handler,), {"db_path": db_path})
    return ThreadingHTTPServer((host, port), handler)


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(prog="kotiza", description="Kotiza cost estimating server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--db", default=None, help=f"SQLite file (default {db.DEFAULT_DB})")
    a = p.parse_args(argv)
    srv = make_server(a.host, a.port, a.db)
    print(f"Kotiza running at http://{a.host}:{a.port}  (database: {a.db or db.DEFAULT_DB})")
    print("Press Ctrl+C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        srv.server_close()


if __name__ == "__main__":
    sys.exit(main())
