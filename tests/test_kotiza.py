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


if __name__ == "__main__":
    unittest.main()
