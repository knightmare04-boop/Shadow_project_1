"""normal — the legitimate business behaviors (the 99.5%+ background).

Every flow here exists for two reasons: (1) realism — these are the rhythms a
real ERP ledger has (payroll batches, month-end procurement, recurring bills,
refunds, treasury sweeps); (2) honesty — the benign world must contain the same
*ingredients* fraud is made of (bursts of fan-in at busy retailers, benign
fan-out in payroll runs, near-equal recurring amounts, reciprocal refund pairs,
company->employee->company circulation), so no detector gets a free lunch from
a sterile background.

Each function appends events to the shared ``EventBuffer`` and returns the
number of events it created (for the generation manifest).
"""
from __future__ import annotations

import numpy as np

from synth.base import (DAY, EventBuffer, anytime_seconds, business_seconds,
                        consumer_seconds, day_weights, lognorm)
from synth.world import World


def _days_from(rng: np.random.Generator, cumw: np.ndarray, n: int, min_day: int) -> np.ndarray:
    """Sample ``n`` days >= ``min_day`` proportionally to the day-weight table,
    via inverse-CDF on the cumulative weights (fast per-entity conditioning)."""
    lo = cumw[min_day - 1] if min_day > 0 else 0.0
    u = rng.uniform(lo, cumw[-1], size=n)
    return np.searchsorted(cumw, u)


# ---- sales + refunds -----------------------------------------------------------

def gen_sales_and_refunds(world: World, buf: EventBuffer, rng: np.random.Generator) -> dict:
    cfg = world.cfg
    act = cfg["activity"]
    tl = act["sales"]["ticket_lognorm"]
    days = int(cfg["days"])
    w = day_weights(cfg)
    cumw = np.cumsum(w)

    ops = np.array([c["ops"] for c in world.companies], dtype=object)
    scale = np.array([c["price_scale"] for c in world.companies])

    all_ts, all_buyer, all_co, all_amt, all_business = [], [], [], [], []

    for cid, cu in world.customers.items():
        active_frac = (days - cu["arrival"]) / days
        if active_frac <= 0 or not cu["favorites"]:
            continue
        n = rng.poisson(cu["rate_pm"] * 12.0 * active_frac)
        if n == 0:
            continue
        d = _days_from(rng, cumw, n, cu["arrival"])
        ts = d * DAY + (business_seconds(rng, n) if cu["business"] else consumer_seconds(rng, n))
        co = np.asarray(cu["favorites"])[rng.integers(0, len(cu["favorites"]), size=n)]
        med = tl["business_median"] if cu["business"] else tl["consumer_median"]
        sig = tl["business_sigma"] if cu["business"] else tl["consumer_sigma"]
        amt = lognorm(rng, med * cu["mult"], sig, size=n) * scale[co]
        all_ts.append(ts); all_buyer.append(np.full(n, cid, dtype=object))
        all_co.append(co); all_amt.append(amt)
        all_business.append(np.full(n, cu["business"]))

    # employees are consumers too (their salary circulates back into the economy)
    retail = [c["idx"] for c in world.companies if c["retail"]]
    emp_rate = act["sales"]["purchases_per_month"]["employee"]
    for eid, einfo in world.employees.items():
        start = einfo.get("start", 0)
        n = rng.poisson(emp_rate * 12.0 * (days - start) / days)
        if n == 0 or not retail:
            continue
        d = _days_from(rng, cumw, n, start)
        ts = d * DAY + consumer_seconds(rng, n)
        co = np.asarray(retail)[rng.integers(0, len(retail), size=n)]
        amt = lognorm(rng, tl["consumer_median"], tl["consumer_sigma"], size=n) * scale[co]
        all_ts.append(ts); all_buyer.append(np.full(n, eid, dtype=object))
        all_co.append(co); all_amt.append(amt)
        all_business.append(np.full(n, False))

    ts = np.concatenate(all_ts); buyer = np.concatenate(all_buyer)
    co = np.concatenate(all_co); amt = np.concatenate(all_amt)
    n_sales = buf.add(ts, buyer, ops[co], amt, "sale")

    # refunds: a slice of sales comes back later, full or partial -> benign
    # reciprocal (buyer, company) pairs with near-equal amounts exist by design.
    rf = act["refunds"]
    mask = rng.random(n_sales) < rf["frac"]
    idx = np.where(mask)[0]
    delay = rng.exponential(rf["delay_mean_days"] * DAY, size=idx.size).astype(np.int64)
    r_ts = ts[idx] + delay
    keep = r_ts < days * DAY
    idx, r_ts = idx[keep], r_ts[keep]
    full = rng.random(idx.size) < rf["full_frac"]
    frac = np.where(full, 1.0, rng.uniform(*rf["partial_range"], size=idx.size))
    n_ref = buf.add(r_ts, ops[co[idx]], buyer[idx], amt[idx] * frac, "refund")
    return {"sale": n_sales, "refund": n_ref}


# ---- procurement + recurring bills ----------------------------------------------

def gen_procurement(world: World, buf: EventBuffer, rng: np.random.Generator) -> dict:
    cfg = world.cfg
    act = cfg["activity"]["procurement"]
    w = day_weights(cfg, monthend=True)   # the month-end spike lives here
    cumw = np.cumsum(w)
    total = 0
    for c in world.companies:
        # base = invoices per company-year at the median size (60 employees),
        # scaled sublinearly with head-count.
        n = rng.poisson(act["per_company_per_year_base"] * (c["n_emp"] / 60.0) ** 0.7)
        if n == 0:
            continue
        # choose the vendor first, then a day the vendor is already onboarded
        # (mid-year vendors receive payments only after they exist)
        vend_idx = rng.choice(len(c["proc_pool"]), size=n, p=c["proc_weights"])
        bases = np.array([world.vendors[v]["base"] for v in c["proc_pool"]])
        avail = np.array([world.vendors[v]["available"] for v in c["proc_pool"]])
        d = np.empty(n, dtype=np.int64)
        for j in np.unique(vend_idx):
            sel = vend_idx == j
            d[sel] = _days_from(rng, cumw, int(sel.sum()), int(avail[j]))
        ts = d * DAY + business_seconds(rng, n)
        vendors = np.array(c["proc_pool"], dtype=object)[vend_idx]
        amt = bases[vend_idx] * lognorm(rng, 1.0, act["amount_sigma"], size=n)
        total += buf.add(ts, c["ops"], vendors, amt, "vendor_payment")
    return {"vendor_payment": total}


def gen_recurring(world: World, buf: EventBuffer, rng: np.random.Generator) -> dict:
    cfg = world.cfg
    jitter = cfg["activity"]["recurring_jitter"]
    days = int(cfg["days"])
    total = 0
    for c in world.companies:
        for r in c["rec_vendors"]:
            months = np.arange(12)
            d = months * 30 + (r["dom"] - 1) + rng.integers(-1, 2, size=12)
            d = d[(d >= world.vendors[r["vendor"]]["available"]) & (d < days)]
            ts = d * DAY + business_seconds(rng, d.size)
            amt = r["fee"] * (1.0 + rng.normal(0, jitter, size=d.size))
            total += buf.add(ts, c["ops"], r["vendor"], amt, "recurring_bill")
    return {"recurring_bill": total}


# ---- payroll + reimbursements ----------------------------------------------------

def gen_payroll(world: World, buf: EventBuffer, rng: np.random.Generator) -> dict:
    cfg = world.cfg
    days = int(cfg["days"])
    total = 0
    for c in world.companies:
        if c["pay_biweekly"]:
            run_days = np.arange(c["pay_offset"], days, 14)
        else:
            run_days = np.array([m * 30 + c["pay_dom"] - 1 for m in range(12)])
            run_days = run_days[run_days < days]
        salaries = np.array([world.employees[e]["salary"] for e in c["employees"]])
        starts = np.array([world.employees[e].get("start", 0) for e in c["employees"]])
        emp = np.array(c["employees"], dtype=object)
        for d in run_days:
            on_board = starts <= d              # new hires join the batch once hired
            m = int(on_board.sum())
            if m == 0:
                continue
            base = int(d) * DAY + int(rng.uniform(6.5, 9.0) * 3600)
            ts = base + np.arange(m) * rng.integers(1, 5)   # one batch, seconds apart
            bonus = 1.5 if (c["bonus_december"] and not c["pay_biweekly"] and d >= 334) else 1.0
            amt = salaries[on_board] * bonus * (1.0 + rng.normal(0, 0.01, size=m))
            total += buf.add(ts, c["ops"], emp[on_board], amt, "payroll")
    return {"payroll": total}


def gen_reimbursements(world: World, buf: EventBuffer, rng: np.random.Generator) -> dict:
    cfg = world.cfg
    act = cfg["activity"]["reimbursement"]
    w = day_weights(cfg)
    cumw = np.cumsum(w)
    total = 0
    for eid, e in world.employees.items():
        start = e.get("start", 0)
        n = rng.poisson(act["per_employee_per_year"] * (len(cumw) - start) / len(cumw))
        if n == 0:
            continue
        d = _days_from(rng, cumw, n, start)
        ts = d * DAY + business_seconds(rng, n)
        amt = lognorm(rng, act["median"], act["sigma"], size=n)
        total += buf.add(ts, world.companies[e["company"]]["ops"], eid, amt, "reimbursement")
    return {"reimbursement": total}


# ---- treasury sweeps + intercompany ----------------------------------------------

def gen_transfers(world: World, buf: EventBuffer, rng: np.random.Generator) -> dict:
    cfg = world.cfg
    days = int(cfg["days"])
    sw = cfg["activity"]["sweeps"]
    total = 0
    for c in world.companies:
        if not c["treasury"]:
            continue
        n = rng.poisson(sw["per_week"] * days / 7.0)
        d = rng.integers(0, days, size=n)
        d = d[(d % 7) < 5]                              # weekday treasury ops
        ts = d * DAY + business_seconds(rng, d.size)
        lo, hi = sw["amount_range"]
        amt = np.clip(lognorm(rng, 60000, 1.0, size=d.size), lo, hi)
        amt = np.round(amt, -2)                         # treasuries move round sums
        to_trs = rng.random(d.size) < 0.5
        src = np.where(to_trs, c["ops"], c["treasury"]).astype(object)
        dst = np.where(to_trs, c["treasury"], c["ops"]).astype(object)
        total += buf.add(ts, src, dst, amt, "transfer")

    # occasional company-to-company payments (partnerships, settlements)
    n = rng.poisson(cfg["activity"]["intercompany_per_year"])
    w = day_weights(cfg)
    cumw = np.cumsum(w)
    d = _days_from(rng, cumw, n, 0)
    ts = d * DAY + business_seconds(rng, n)
    a = rng.integers(0, len(world.companies), size=n)
    b = rng.integers(0, len(world.companies) - 1, size=n)
    b = np.where(b >= a, b + 1, b)                      # b != a
    ops = np.array([c["ops"] for c in world.companies], dtype=object)
    amt = lognorm(rng, 8000, 1.2, size=n)
    total += buf.add(ts, ops[a], ops[b], amt, "transfer")

    # ordinary person-to-person transfers (rent shares, loans, gifts). These keep
    # `transfer` a majority-benign category and put benign mass in the same
    # amount band as illicit transfers — the honest background for them to hide in.
    # A slice is private MARKETPLACE sales (secondhand goods): people — including
    # accounts opened this year — receive benign `sale` traffic too.
    p2p = cfg["activity"]["p2p"]
    people = np.array(list(world.customers) + list(world.employees), dtype=object)
    n = rng.poisson(p2p["per_person_per_year"] * len(people))
    d = _days_from(rng, cumw, n, 0)
    ts = d * DAY + anytime_seconds(rng, n)
    a = rng.integers(0, len(people), size=n)
    b = rng.integers(0, len(people) - 1, size=n)
    b = np.where(b >= a, b + 1, b)                      # b != a
    amt = lognorm(rng, p2p["median"], p2p["sigma"], size=n)
    is_sale = rng.random(n) < p2p["sale_frac"]
    n_sale = buf.add(ts[is_sale], people[a[is_sale]], people[b[is_sale]],
                     amt[is_sale], "sale")
    total += buf.add(ts[~is_sale], people[a[~is_sale]], people[b[~is_sale]],
                     amt[~is_sale], "transfer")
    return {"transfer": total, "p2p_marketplace_sale": n_sale}


def generate_normal(world: World, buf: EventBuffer, rng: np.random.Generator) -> dict:
    counts: dict[str, int] = {}
    for fn in (gen_sales_and_refunds, gen_procurement, gen_recurring,
               gen_payroll, gen_reimbursements, gen_transfers):
        counts.update(fn(world, buf, rng))
    return counts
