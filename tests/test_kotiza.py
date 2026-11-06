import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from kotiza import calc, db, server


class CalcTests(unittest.TestCase):
    def crew(self):
        return {
            "labor": [
                {"qty": 1, "base_rate": 10, "burden_pct": 50},   # 15/hr
                {"qty": 2, "base_rate": 4, "burden_pct": 50},    # 2 x 6 = 12/hr
            ],
            "equipment": [{"qty": 1, "hourly_rate": 5}],
        }

    def test_crew_hourly_cost(self):
        c = calc.compute_crew(self.crew())
        self.assertAlmostEqual(c["labor_hourly"], 27)
        self.assertAlmostEqual(c["equipment_hourly"], 5)
        self.assertAlmostEqual(c["hourly_cost"], 32)
        self.assertAlmostEqual(c["headcount"], 3)

    def test_task_cost(self):
        crew = calc.compute_crew(self.crew())
        task = {
            "quantity": 100, "production_rate": 20,   # 5 crew-days, 40 crew-hours at 8h
            "resources": [
                {"qty_per_unit": 2, "unit_cost": 3, "waste_pct": 10, "kind": "material"},
                {"qty_per_unit": 0.5, "unit_cost": 2, "waste_pct": 0, "kind": "consumable"},
            ],
        }
        c = calc.compute_task(task, crew, 8)["calc"]
        self.assertAlmostEqual(c["crew_days"], 5)
        self.assertAlmostEqual(c["crew_hours"], 40)
        self.assertAlmostEqual(c["man_hours"], 120)
        self.assertAlmostEqual(c["labor"], 1080)
        self.assertAlmostEqual(c["equipment"], 200)
        self.assertAlmostEqual(c["material"], 660)      # 100 x 2 x 1.1 x 3
        self.assertAlmostEqual(c["consumable"], 100)    # 100 x 0.5 x 2
        self.assertAlmostEqual(c["direct"], 2040)
        self.assertAlmostEqual(c["unit_cost"], 20.40)

    def test_zero_rate_warns_and_no_division_error(self):
        crew = calc.compute_crew(self.crew())
        c = calc.compute_task({"quantity": 10, "production_rate": 0, "resources": []}, crew, 8)["calc"]
        self.assertEqual(c["labor"], 0)
        self.assertTrue(c["warnings"])
        c = calc.compute_task({"quantity": 0, "production_rate": 5, "resources": []}, crew, 8)["calc"]
        self.assertEqual(c["unit_cost"], 0)

    def test_estimate_rollup_and_markups(self):
        crews = {1: self.crew()}
        tasks = [{"crew_id": 1, "quantity": 100, "production_rate": 20, "resources": []},
                 {"crew_id": None, "quantity": 10, "production_rate": 0,
                  "resources": [{"qty_per_unit": 1, "unit_cost": 100, "waste_pct": 0,
                                 "kind": "material"}]}]
        # direct = 1280 labor+equip + 1000 material = 2280; labor = 1080
        indirects = [
            {"method": "lump", "quantity": 2, "rate": 500},          # 1000
            {"method": "pct_direct", "percent": 10},                 # 228
            {"method": "pct_labor", "percent": 10},                  # 108
        ]
        est = {"hours_per_day": 8, "contingency_pct": 10, "overhead_pct": 10,
               "profit_pct": 10, "bond_pct": 0, "tax_pct": 7}
        s = calc.compute_estimate(est, tasks, crews, indirects)
        self.assertAlmostEqual(s["direct"], 2280)
        self.assertAlmostEqual(s["indirect"], 1336)
        self.assertAlmostEqual(s["cost"], 3616)
        self.assertAlmostEqual(s["price_before_tax"], 3616 * 1.1 ** 3)
        self.assertAlmostEqual(s["tax"], s["price_before_tax"] * 0.07)
        self.assertAlmostEqual(s["contract_price"], s["price_before_tax"] * 1.07)
        # Bid totals must reconcile exactly to the price before tax.
        self.assertAlmostEqual(sum(t["calc"]["bid_total"] for t in tasks), s["price_before_tax"])


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        path = os.path.join(cls.tmp.name, "test.db")
        cls.srv = server.make_server("127.0.0.1", 0, path)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}/api"
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.tmp.cleanup()

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_seeded_sample(self):
        code, est = self.call("GET", "/estimates")
        self.assertEqual(code, 200)
        self.assertTrue(est)
        code, full = self.call("GET", f"/estimates/{est[-1]['id']}")
        self.assertGreater(full["summary"]["contract_price"], full["summary"]["direct"])

    def test_build_estimate_end_to_end(self):
        _, mats = self.call("GET", "/materials")
        _, crews = self.call("GET", "/crews")
        _, lib = self.call("GET", "/library")
        _, e = self.call("POST", "/estimates", {"name": "Test job", "profit_pct": 10})
        eid = e["id"]

        code, t = self.call("POST", f"/estimates/{eid}/tasks", {
            "description": "Custom task", "unit": "m2", "quantity": 50,
            "crew_id": crews[0]["id"], "production_rate": 10,
            "resources": [{"material_id": mats[0]["id"], "qty_per_unit": 2}]})
        self.assertEqual(code, 200)
        self.call("POST", f"/estimates/{eid}/tasks", {"library_id": lib[0]["id"], "quantity": 20})
        self.call("POST", f"/estimates/{eid}/indirects", {"description": "Site office",
                                                          "method": "lump", "quantity": 2,
                                                          "rate": 100})
        _, full = self.call("GET", f"/estimates/{eid}")
        self.assertEqual(len(full["tasks"]), 2)
        s = full["summary"]
        self.assertAlmostEqual(s["indirect"], 200)
        self.assertAlmostEqual(s["price_before_tax"], (s["direct"] + 200) * 1.10)

        # Update quantity, reorder, duplicate
        self.call("PUT", f"/tasks/{t['id']}", {"quantity": 100})
        self.call("POST", f"/tasks/{t['id']}/move", {"dir": 1})
        _, full2 = self.call("GET", f"/estimates/{eid}")
        self.assertEqual(full2["tasks"][1]["id"], t["id"])
        self.assertEqual(full2["tasks"][1]["quantity"], 100)
        _, dup = self.call("POST", f"/estimates/{eid}/duplicate")
        _, full3 = self.call("GET", f"/estimates/{dup['id']}")
        self.assertAlmostEqual(full3["summary"]["contract_price"], full2["summary"]["contract_price"])

        # Save task to library
        code, saved = self.call("POST", f"/tasks/{t['id']}/to-library")
        self.assertEqual(code, 200)
        self.assertTrue(saved["code"])

    def test_cannot_delete_material_in_use(self):
        _, mats = self.call("GET", "/materials")
        used = [m for m in mats if m["code"] == "RMX"][0]
        code, body = self.call("DELETE", f"/materials/{used['id']}")
        self.assertEqual(code, 409)
        self.assertIn("in use", body["error"])

    def test_validation(self):
        code, _ = self.call("POST", "/labor", {"code": "", "trade": "X"})
        self.assertEqual(code, 400)
        code, _ = self.call("POST", "/labor", {"code": "ZZ", "trade": "X", "base_rate": "abc"})
        self.assertEqual(code, 400)
        code, _ = self.call("POST", "/labor", {"code": "MAS", "trade": "dup"})
        self.assertEqual(code, 409)


class PanamaLaborTests(unittest.TestCase):
    def test_burden_formula(self):
        from kotiza import rates_pa
        comps = [{"kind": "leave", "percent": 10}, {"kind": "charge", "percent": 20},
                 {"kind": "charge", "percent": 50, "active": 0}, {"kind": "fixed", "percent": 0.05}]
        leave, charge, total, fixed = rates_pa.total_burden(comps)
        self.assertAlmostEqual(total, 10 + 1.1 * 20)
        self.assertAlmostEqual(fixed, 0.05)
        _, _, default_total, _ = rates_pa.total_burden(
            [{"kind": k, "percent": p} for _, _, k, p, _ in rates_pa.BURDEN_COMPONENTS])
        self.assertTrue(45 < default_total < 65)

    def test_wage_tables_consistent(self):
        from kotiza import rates_pa
        codes = [t[0] for t in rates_pa.TRADES]
        self.assertEqual(len(codes), len(set(codes)))
        for code, _, _, priv, pub, special in rates_pa.TRADES:
            self.assertGreaterEqual(pub, priv, code)
            # Cl. 127: special projects = private + 11% (rounded to the cent)
            self.assertAlmostEqual(special, priv * 1.11, delta=0.011, msg=code)

    def test_migrates_v1_database(self):
        with tempfile.TemporaryDirectory() as d:
            conn = db.connect(os.path.join(d, "old.db"))
            conn.executescript("""
                CREATE TABLE labor (id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE,
                    trade TEXT NOT NULL, base_rate REAL NOT NULL DEFAULT 0,
                    burden_pct REAL NOT NULL DEFAULT 0);
                INSERT INTO labor(code, trade, base_rate, burden_pct) VALUES ('MAS', 'Mason', 5.5, 55);
                CREATE TABLE estimates (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
            """)
            db.init_db(conn)
            row = conn.execute("SELECT * FROM labor WHERE code = 'MAS'").fetchone()
            self.assertEqual(row["use_standard_burden"], 0)   # keeps its custom 55%
            ins, upd = db.load_capac_rates(conn)
            self.assertEqual(upd, 1)
            row = conn.execute("SELECT * FROM labor WHERE code = 'MAS'").fetchone()
            self.assertEqual((row["base_rate"], row["public_rate"], row["special_rate"]),
                             (6.10, 6.30, 6.77))
            conn.close()

    def test_rebuilds_old_check_constraints(self):
        with tempfile.TemporaryDirectory() as d:
            conn = db.connect(os.path.join(d, "v2.db"))
            old = db.SCHEMA.replace("('leave', 'charge', 'fixed')", "('leave', 'charge')") \
                           .replace("('private', 'public', 'special')", "('private', 'public')")
            conn.executescript(old)
            conn.execute("INSERT INTO estimates(name) VALUES ('Old job')")
            conn.execute("INSERT INTO estimate_tasks(estimate_id, description) VALUES (1, 'T')")
            conn.commit()
            db.init_db(conn)
            conn.execute("UPDATE estimates SET wage_scale = 'special' WHERE id = 1")
            conn.execute("INSERT INTO burden_components(name, kind, percent) VALUES ('x', 'fixed', 1)")
            self.assertEqual(conn.execute("SELECT description FROM estimate_tasks WHERE estimate_id = 1").fetchall()[0][0], "T")
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            conn.close()

    def test_wage_scales_and_fixed_costs(self):
        with tempfile.TemporaryDirectory() as d:
            conn = db.connect(os.path.join(d, "t.db"))
            db.init_db(conn)
            eid = conn.execute("SELECT id FROM estimates").fetchone()[0]
            labor = {}
            for scale in ("private", "public", "special"):
                conn.execute("UPDATE estimates SET wage_scale = ? WHERE id = ?", (scale, eid))
                labor[scale] = calc.load_estimate(conn, eid)["summary"]["labor"]
            self.assertLess(labor["private"], labor["public"])
            self.assertLess(labor["public"], labor["special"])
            crew = calc.load_crew(conn, conn.execute(
                "SELECT id FROM crews WHERE code = 'CV-PEON'").fetchone()[0])
            pct, fixed = db.standard_burden(conn)
            self.assertGreater(fixed, 0)
            self.assertAlmostEqual(crew["labor_hourly"], 4.51 * (1 + pct / 100) + fixed)
            conn.close()

    def test_rendimientos_library(self):
        from kotiza import rates_pa
        with tempfile.TemporaryDirectory() as d:
            conn = db.connect(os.path.join(d, "t.db"))
            db.init_db(conn)
            n = conn.execute("SELECT COUNT(*) FROM task_library WHERE code LIKE 'RM-%'").fetchone()[0]
            self.assertEqual(n, len(rates_pa.RENDIMIENTOS))
            ins, upd = db.load_capac_rendimientos(conn)      # idempotent
            self.assertEqual((ins, upd), (0, len(rates_pa.RENDIMIENTOS)))
            t = conn.execute("SELECT * FROM task_library WHERE code = 'RM-D3.1'").fetchone()
            self.assertEqual((t["unit"], t["production_rate"]), ("m2", 14.46))
            rebar = conn.execute("SELECT production_rate FROM task_library WHERE code='RM-B1.3'").fetchone()[0]
            self.assertAlmostEqual(rebar, 732.06 * 0.45359, places=2)
            conn.close()


class MaterialsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(os.path.join(self.tmp.name, "m.db"))
        db.init_db(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_cgr_catalog_loaded_and_idempotent(self):
        with open(db.CGR_MATERIALS, encoding="utf-8") as fh:
            data = json.load(fh)
        n = len(data["materials"])
        loaded = self.conn.execute("SELECT COUNT(*) FROM materials WHERE source = ?",
                                   (data["source_short"],)).fetchone()[0]
        # The sample 'DSC' (cutting disc) shares a code with the CGR catalog and is kept.
        self.assertEqual(loaded, n - 1)
        own = self.conn.execute("SELECT source FROM materials WHERE code = 'DSC'").fetchone()[0]
        self.assertEqual(own, "Sample data")
        ins, upd, skipped = db.load_cgr_materials(self.conn)
        self.assertEqual((ins, upd, skipped), (0, n - 1, ["DSC"]))
        cem = self.conn.execute("SELECT * FROM materials WHERE code = 'CEMENTO'").fetchone()
        self.assertEqual((cem["unit"], cem["unit_cost"], cem["price_date"]), ("saco", 8.49, "2025-07-10"))

    def test_csv_round_trip_and_import(self):
        from kotiza import server
        text = server.export_materials_csv(self.conn)
        self.assertTrue(text.startswith("code,description"))
        res = server.import_materials_csv(
            self.conn,
            "code;unit_cost;description\nCEMENTO;B/.8.95;\nNEW-1;12.5;Nuevo material\nNEW-2;3;\nBAD;abc;x\n",
            "Cotización Cochez #123", "2026-11-06")
        self.assertEqual((res["updated"], res["inserted"], res["error_count"]), (1, 1, 2))
        cem = self.conn.execute("SELECT * FROM materials WHERE code = 'CEMENTO'").fetchone()
        self.assertEqual((cem["unit_cost"], cem["source"], cem["price_date"], cem["description"]),
                         (8.95, "Cotización Cochez #123", "2026-11-06", "CEMENTO GRIS TIPO I"))
        # A later CGR reload must not overwrite a price the user replaced.
        _, _, skipped = db.load_cgr_materials(self.conn)
        self.assertIn("CEMENTO", skipped)


    def test_adjust_prices(self):
        from kotiza import server
        ids = [r[0] for r in self.conn.execute("SELECT id FROM materials WHERE code IN ('IBC6', 'IA')")]
        server._adjust_materials(self.conn, {"ids": ids, "percent": 10, "note": "INEC", "price_date": "2026-11-06"})
        r = self.conn.execute("SELECT unit_cost, source FROM materials WHERE code = 'IBC6'").fetchone()
        self.assertAlmostEqual(r["unit_cost"], 1.045)
        self.assertIn("+10% (INEC)", r["source"])
        _, _, skipped = db.load_cgr_materials(self.conn)     # adjusted prices are protected
        self.assertIn("IBC6", skipped)
        with self.assertRaises(server.ApiError):
            server._adjust_materials(self.conn, {"ids": ids, "percent": -100})


if __name__ == "__main__":
    unittest.main()
