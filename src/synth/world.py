"""world — the account population and its relationships (the simulated economy).

A three-tier economy with money actually circulating (so benign multi-hop paths
and reciprocal pairs exist — a sterile background where only fraud has structure
would be the subtle version of the circularity trap):

    vendors  <--procurement/recurring--  COMPANIES  --payroll/reimburse-->  employees
                                            ^   \--refunds-->  customers
        customers & employees --sales--->  /

Employees are ALSO consumers (their salary funds purchases from retail
companies), which closes benign company -> employee -> company paths.
Customers keep joining throughout the year, so "recently opened account" is a
normal event, not a fraud giveaway.

Account roles recorded in ``accounts.csv`` (``role``, ``creation_day``) are
PROVENANCE for evaluation and the demo. ``role`` is a string and is never used
as a model feature (the feature builder keeps numeric attributes only);
``creation_day`` is a legitimate real-world attribute (account opening date).
"""
from __future__ import annotations

import numpy as np

from synth.base import lognorm, randint

ZIPF_A = 1.25  # weight ~ 1/rank^a for vendor / company preference


def _zipf_weights(n: int) -> np.ndarray:
    w = 1.0 / np.power(np.arange(1, n + 1), ZIPF_A)
    return w / w.sum()


class World:
    """Builds and holds the population. All randomness comes from one rng."""

    def __init__(self, cfg: dict, rng: np.random.Generator):
        self.cfg = cfg
        self.rng = rng
        self.accounts: dict[str, dict] = {}   # id -> {role, creation_day}
        self.companies: list[dict] = []
        self.vendors: dict[str, dict] = {}
        self.employees: dict[str, dict] = {}
        self.customers: dict[str, dict] = {}
        self._shell_seq = 0
        self._build()

    # ---- registry ------------------------------------------------------------
    def register(self, acct_id: str, role: str, creation_day: int) -> str:
        self.accounts[acct_id] = {"role": role, "creation_day": int(creation_day)}
        return acct_id

    def _preexisting_day(self) -> int:
        lo, hi = self.cfg["world"]["preexisting_creation_day"]
        return int(self.rng.integers(lo, hi + 1))

    def new_shell(self, first_use_day: int, role: str = "external") -> str:
        """A fraudster-opened account, aged a little before first use (evasion).
        Ids look like ordinary external accounts; the honest marker is the
        provenance role, which is eval-only."""
        self._shell_seq += 1
        lo, hi = self.cfg["fraud"]["shell_age_days"]
        created = max(0, first_use_day - randint(self.rng, (lo, hi)))
        return self.register(f"EXT:{self._shell_seq:05d}", role, created)

    def new_shell_vendor(self, first_use_day: int) -> str:
        """A shell registered AS a vendor (indistinguishable id-wise from real
        vendors); used by kickback schemes that plant a fake supplier."""
        vid = f"VEND:{len(self.vendors):04d}"
        lo, hi = self.cfg["fraud"]["shell_age_days"]
        created = max(0, first_use_day - randint(self.rng, (lo, hi)))
        self.register(vid, "vendor_shell", created)
        base = float(lognorm(self.rng, **self.cfg["activity"]["procurement"]["vendor_base_lognorm"]))
        self.vendors[vid] = {"base": base}
        return vid

    # ---- population ----------------------------------------------------------
    def _build(self) -> None:
        cfg, rng = self.cfg, self.rng
        w = cfg["world"]

        # vendors -------------------------------------------------------------
        # A slice onboards DURING the year (receiver-side mid-year cover: new
        # supplier relationships are normal business, so "newly created account
        # that receives a vendor payment" must not be a fraud rule).
        vb = cfg["activity"]["procurement"]["vendor_base_lognorm"]
        for i in range(w["n_vendors"]):
            if rng.random() < w["vendor_midyear_frac"]:
                created = int(rng.integers(0, 301))
            else:
                created = self._preexisting_day()
            vid = self.register(f"VEND:{i:04d}", "vendor", created)
            self.vendors[vid] = {"base": float(lognorm(rng, vb["median"], vb["sigma"])),
                                 "available": max(0, created)}
        vendor_ids = list(self.vendors)

        # companies -----------------------------------------------------------
        el = w["employees_lognorm"]
        sal = w["salary_lognorm"]
        for c in range(w["n_companies"]):
            n_emp = int(np.clip(lognorm(rng, el["median"], el["sigma"]), el["min"], el["max"]))
            ops = self.register(f"CO:{c:02d}:OPS", "company_ops", self._preexisting_day())
            treasury = None
            if rng.random() < w["treasury_frac"]:
                treasury = self.register(f"CO:{c:02d}:TRS", "company_treasury", self._preexisting_day())

            employees = []
            for e in range(n_emp):
                # new hires join all year (receiver-side mid-year cover: payroll
                # and reimbursements to recently opened accounts are normal life)
                if rng.random() < w["hire_midyear_frac"]:
                    created = int(rng.integers(0, 331))
                else:
                    created = self._preexisting_day()
                eid = self.register(f"EMP:{c:02d}:{e:03d}", "employee", created)
                self.employees[eid] = {"company": c, "start": max(0, created),
                                       "salary": float(lognorm(rng, sal["median"], sal["sigma"]))}
                employees.append(eid)

            # recurring vendors: a fixed monthly fee on a fixed day-of-month
            n_rec = randint(rng, w["recurring_vendors_per_company"])
            rec = []
            for vid in rng.choice(vendor_ids, size=n_rec, replace=False):
                fee = float(lognorm(rng, 1800, 0.9))
                rec.append({"vendor": str(vid), "fee": fee, "dom": int(rng.integers(1, 28))})

            # procurement pool: zipf preference over a random supplier subset
            n_pool = randint(rng, w["procurement_pool_per_company"])
            pool = [str(v) for v in rng.choice(vendor_ids, size=n_pool, replace=False)]

            pay_biweekly = rng.random() < w["biweekly_payroll_frac"]
            self.companies.append({
                "idx": c,
                "ops": ops,
                "treasury": treasury,
                "retail": rng.random() < w["retail_frac"],
                "n_emp": n_emp,
                "employees": employees,
                "price_scale": float(lognorm(rng, 1.0, w["price_scale_sigma"])),
                "threshold": float(rng.choice(w["approval_thresholds"])),
                "pay_biweekly": pay_biweekly,
                "pay_dom": int(rng.integers(25, 29)),          # monthly pay day
                "pay_offset": int(rng.integers(0, 14)),        # biweekly phase
                "bonus_december": bool(rng.random() < 0.4),
                "rec_vendors": rec,
                "proc_pool": pool,
                "proc_weights": _zipf_weights(len(pool)),
            })

        # customers (initial base + arrivals through the year) ------------------
        n0 = w["n_customers0"]
        arrivals = rng.poisson(w["customer_arrival_per_day"], size=cfg["days"])
        arrival_days = np.repeat(np.arange(cfg["days"]), arrivals)
        creation = np.concatenate([
            rng.integers(w["preexisting_creation_day"][0], 0, size=n0),
            arrival_days,
        ])
        retail_idx = [c["idx"] for c in self.companies if c["retail"]]
        retail_w = _zipf_weights(len(retail_idx))
        ppm = cfg["activity"]["sales"]["purchases_per_month"]
        for i, created in enumerate(creation):
            cid = self.register(f"CUST:{i:05d}", "customer", int(created))
            business = rng.random() < w["business_customer_frac"]
            n_fav = randint(rng, (1, 4))
            # zipf-tilted popularity: some retailers are much busier than others
            fav = rng.choice(retail_idx, size=min(n_fav, len(retail_idx)),
                             replace=False, p=retail_w)
            rate = (ppm["business"] if business else ppm["consumer"]) * float(rng.gamma(2.0, 0.5))
            self.customers[cid] = {
                "business": business,
                "rate_pm": rate,                      # purchases per month
                "mult": float(lognorm(rng, 1.0, 0.4)),  # personal ticket multiplier
                "arrival": int(max(created, 0)),
                "favorites": [int(f) for f in fav],
            }

    # ---- convenience ----------------------------------------------------------
    def consumer_ids(self) -> list[str]:
        return [k for k, v in self.customers.items() if not v["business"]]

    def business_customer_ids(self) -> list[str]:
        return [k for k, v in self.customers.items() if v["business"]]
