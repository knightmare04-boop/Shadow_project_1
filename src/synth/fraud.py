"""fraud — goal-driven fraud scenario agents, one per typology.

THE BINDING RULE (the circularity trap, PROJECT_OVERVIEW §14.12): every
scenario below is written as a *behavior* — an actor with a goal, constraints,
and an evasion style. None of this module knows what a detector is. Whatever
graph shapes appear in the data EMERGE from the behavior (a launderer routing
money through a ring happens to create a cycle; a collector being paid by many
mules happens to create fan-in) — they are consequences, not targets. This file
deliberately imports nothing from ``topology``.

Evasion is first-class (real fraudsters hide): amounts are jittered lognormals
that OVERLAP the benign flows they imitate (we measured — and avoid — the
AMLSim giveaway where fraud amounts are 15x smaller than benign, see
calibration_reference.json); payments are structured just under approval
thresholds; timing is staggered over days-to-weeks, not bursts; shells are
opened well before first use; mules are EXISTING customers who keep living
their normal lives; fraud reuses the benign ``tx_type`` vocabulary.

Labeling policy (mirrors IBM AML: every transaction belonging to a fraud
pattern is labeled): a row gets ``IS_FRAUD=1`` iff the fraudster initiated,
rerouted, or misapplied it. A mule's ordinary groceries stay label 0; the scam
payment INTO the mule and the forward OUT of it are both 1.

Each scenario returns a provenance record for ``scenarios.json``.
"""
from __future__ import annotations

import numpy as np

from synth.base import DAY, EventBuffer, anytime_seconds, business_seconds, lognorm, randint
from synth.world import World


def _office_ts(rng: np.random.Generator, day: float) -> int:
    return int(day) * DAY + int(business_seconds(rng, 1)[0])


def _any_ts(rng: np.random.Generator, day: float) -> int:
    return int(day) * DAY + int(anytime_seconds(rng, 1)[0])


def _structured(rng: np.random.Generator, total: float, threshold: float,
                max_parts: int = 4) -> list[float]:
    """Split ``total`` into parts that each stay below the approval threshold
    (classic structuring). Returns [total] unchanged when it already fits."""
    if total <= threshold * 0.96:
        return [total]
    parts: list[float] = []
    remaining = total
    while remaining > threshold * 0.96 and len(parts) < max_parts - 1:
        part = threshold * rng.uniform(0.55, 0.92)
        parts.append(part)
        remaining -= part
    parts.append(max(remaining, 0.01))
    return parts


def _pick_victim(world: World, rng: np.random.Generator, busy: dict, start: int,
                 end: int, retail_only: bool = False):
    """A victim company, weighted by size, respecting the concurrency cap."""
    cap = world.cfg["fraud"]["max_concurrent_per_company"]
    pool = [c for c in world.companies if c["retail"]] if retail_only else world.companies
    wts = np.array([c["n_emp"] for c in pool], dtype=float)
    wts /= wts.sum()
    for _ in range(25):
        c = pool[int(rng.choice(len(pool), p=wts))]
        overlaps = [1 for (s, e) in busy.get(c["idx"], []) if s <= end and start <= e]
        if len(overlaps) < cap:
            busy.setdefault(c["idx"], []).append((start, end))
            return c
    busy.setdefault(c["idx"], []).append((start, end))   # give up gracefully
    return c


# ---- typology 1: laundering ring (may or may not loop back) ---------------------

def laundering_cycle(world: World, buf: EventBuffer, rng: np.random.Generator,
                     sid: str, start_day: int, busy: dict, recruited: set) -> dict:
    p = world.cfg["fraud"]["laundering_cycle"]
    horizon = int(world.cfg["days"])
    victim = _pick_victim(world, rng, busy, start_day, start_day + 45)

    ring_size = randint(rng, p["ring_size"])
    entry = world.new_shell(start_day, role="external")
    ring = [entry]
    consumers = [c for c in world.consumer_ids() if c not in recruited]
    for _ in range(ring_size - 1):
        if rng.random() < 0.2 and consumers:            # a recruited mule inside the ring
            mule = str(rng.choice(consumers))
            recruited.add(mule)                          # one criminal association each
            consumers.remove(mule)
            ring.append(mule)
        else:
            ring.append(world.new_shell(start_day, role="external"))
    exit_acct = world.new_shell(start_day, role="external")
    loops_back = rng.random() < p["loop_frac"]

    n = 0
    t_day = float(start_day)
    for _ in range(randint(rng, p["rounds"])):
        # placement: embezzled funds leave the victim, disguised as a payable
        amount = float(lognorm(rng, **p["placement_lognorm"]))
        for part in _structured(rng, amount, victim["threshold"]):
            ts = _office_ts(rng, t_day)
            if ts >= horizon * DAY:
                break
            tx = "vendor_payment" if rng.random() < 0.7 else "transfer"
            n += buf.add([ts], victim["ops"], entry, [part], tx,
                         alert_id=sid, alert_type="laundering_cycle")
            t_day += rng.uniform(0.0, 1.5)
        # layering: hop the money along the ring, skimming a cut each hop
        carried = amount
        path = ring + ([entry] if loops_back else [exit_acct])
        t = _any_ts(rng, t_day)
        for hop_from, hop_to in zip(path[:-1], path[1:]):
            gap = float(rng.lognormal(np.log(p["hop_gap_hours_median"] * 3600),
                                      p["hop_gap_sigma"]))
            t = int(t + max(gap, 600))
            if t >= horizon * DAY:
                break
            carried *= 1.0 - rng.uniform(*p["skim"])
            if rng.random() < p["split_hop_frac"]:
                cut = rng.uniform(0.3, 0.7)
                n += buf.add([t], hop_from, hop_to, [carried * cut], "transfer",
                             alert_id=sid, alert_type="laundering_cycle")
                n += buf.add([t + int(rng.uniform(0.5, 6) * 3600)], hop_from, hop_to,
                             [carried * (1 - cut)], "transfer",
                             alert_id=sid, alert_type="laundering_cycle")
            else:
                n += buf.add([t], hop_from, hop_to, [carried], "transfer",
                             alert_id=sid, alert_type="laundering_cycle")
        t_day = t / DAY + rng.uniform(1, 5)
        if t_day >= horizon:
            break

    return {"id": sid, "typology": "laundering_cycle", "victim": victim["ops"],
            "accounts": ring + [exit_acct], "loops_back": loops_back,
            "start_day": start_day, "end_day": round(t_day, 1), "n_txns": n}


# ---- typology 2: mule collection (scam proceeds funnelled to a collector) --------

def mule_fanin(world: World, buf: EventBuffer, rng: np.random.Generator,
               sid: str, start_day: int, busy: dict, recruited: set) -> dict:
    p = world.cfg["fraud"]["mule_fanin"]
    horizon = int(world.cfg["days"])
    collector = world.new_shell(start_day, role="external")
    exit_acct = world.new_shell(start_day, role="external")
    span = randint(rng, p["campaign_days"])

    consumers = [c for c in world.consumer_ids()
                 if c not in recruited and world.customers[c]["arrival"] <= max(start_day - 30, 0)]
    n_mules = min(randint(rng, p["mules"]), len(consumers))
    mules = [str(m) for m in rng.choice(consumers, size=n_mules, replace=False)]
    recruited.update(mules)

    n = 0
    collected = 0.0
    last_ts = start_day * DAY
    for mule in mules:
        for _ in range(randint(rng, p["payments_per_mule"])):
            victim = mule
            while victim == mule:                        # a victim can't be the mule
                victim = str(rng.choice(consumers))
            d = start_day + rng.uniform(0, span)
            ts = _any_ts(rng, d)
            if ts >= horizon * DAY:
                continue
            amt = float(lognorm(rng, **p["payment_lognorm"]))
            # half the scams ride the purchase rails (fake marketplace "sales"),
            # half are direct transfers — real scam payments use both
            scam_tx = "sale" if rng.random() < 0.5 else "transfer"
            n += buf.add([ts], victim, mule, [amt], scam_tx,
                         alert_id=sid, alert_type="mule_fanin")
            fwd_ts = ts + int(rng.uniform(*p["forward_delay_days"]) * DAY)
            if fwd_ts < horizon * DAY:
                fwd = amt * rng.uniform(*p["forward_frac"])
                n += buf.add([fwd_ts], mule, collector, [fwd], "transfer",
                             alert_id=sid, alert_type="mule_fanin")
                collected += fwd
                last_ts = max(last_ts, fwd_ts)

    if collected > 0:
        for chunk in rng.dirichlet(np.ones(randint(rng, p["exit_chunks"]))) * collected * 0.97:
            ts = last_ts + int(rng.uniform(0.5, 7) * DAY)
            if ts >= horizon * DAY:
                break
            n += buf.add([ts], collector, exit_acct, [float(chunk)], "transfer",
                         alert_id=sid, alert_type="mule_fanin")
            last_ts = ts

    return {"id": sid, "typology": "mule_fanin", "victim": None,
            "accounts": [collector, exit_acct] + mules, "n_mules": n_mules,
            "start_day": start_day, "end_day": round(last_ts / DAY, 1), "n_txns": n}


# ---- typology 3: lapping (divert a receivable, cover it with the next one) -------

def lapping(world: World, buf: EventBuffer, rng: np.random.Generator,
            sid: str, start_day: int, busy: dict) -> dict:
    p = world.cfg["fraud"]["lapping"]
    horizon = int(world.cfg["days"])
    victim = _pick_victim(world, rng, busy, start_day, start_day + 120, retail_only=True)
    clerk = str(rng.choice(victim["employees"]))         # the A/R clerk's own account
    payers = world.business_customer_ids()

    n = 0
    t_day = float(start_day)
    cycles = randint(rng, p["n_cycles"])
    collapse_at = cycles - randint(rng, (1, 3)) if rng.random() < p["collapse_frac"] else None
    for k in range(cycles):
        t_day += rng.uniform(*p["divert_gap_days"])
        if t_day >= horizon:
            break
        invoice = float(lognorm(rng, **p["invoice_lognorm"])) * victim["price_scale"]
        payer = str(rng.choice(payers))
        # the diversion: a customer's invoice payment is rerouted to the clerk
        n += buf.add([_office_ts(rng, t_day)], payer, clerk, [invoice], "sale",
                     alert_id=sid, alert_type="lapping")
        if collapse_at is not None and k >= collapse_at:
            continue                                     # end-stage: holes never covered
        # the cover: a near-equal sum is pushed back to the company days later
        cover_day = t_day + rng.uniform(*p["cover_delay_days"])
        if cover_day < horizon:
            cover = invoice * rng.uniform(*p["cover_frac"])
            n += buf.add([_office_ts(rng, cover_day)], clerk, victim["ops"], [cover],
                         "transfer", alert_id=sid, alert_type="lapping")

    return {"id": sid, "typology": "lapping", "victim": victim["ops"],
            "accounts": [clerk], "collapsed": collapse_at is not None,
            "start_day": start_day, "end_day": round(t_day, 1), "n_txns": n}


# ---- typology 4: invoice kickback (vendor overbills, insider gets a cut) ---------

def invoice_kickback(world: World, buf: EventBuffer, rng: np.random.Generator,
                     sid: str, start_day: int, busy: dict) -> dict:
    p = world.cfg["fraud"]["invoice_kickback"]
    horizon = int(world.cfg["days"])
    victim = _pick_victim(world, rng, busy, start_day, start_day + 300)
    insider = str(rng.choice(victim["employees"]))
    if rng.random() < p["new_vendor_frac"] or not victim["proc_pool"]:
        vendor = world.new_shell_vendor(start_day)       # a planted fake supplier
        corrupted_existing = False
    else:
        vendor = str(rng.choice(victim["proc_pool"]))    # a real relationship gone bad
        corrupted_existing = True
    middle = world.new_shell(start_day, role="external")

    n = 0
    t_day = float(start_day)
    for _ in range(randint(rng, p["rounds"])):
        t_day += rng.uniform(*p["gap_days"])
        if t_day >= horizon:
            break
        if rng.random() < 0.8:                           # structured under the limit
            invoice = victim["threshold"] * rng.uniform(*p["threshold_frac"])
        else:                                            # or inflated vs. history
            invoice = world.vendors[vendor]["base"] * rng.uniform(1.3, 2.2)
        n += buf.add([_office_ts(rng, t_day)], victim["ops"], vendor, [invoice],
                     "vendor_payment", alert_id=sid, alert_type="invoice_kickback")
        kb_day = t_day + rng.uniform(*p["kickback_delay_days"])
        if kb_day >= horizon:
            continue
        kick = invoice * rng.uniform(*p["kickback_frac"])
        if rng.random() < p["via_shell_frac"]:           # sometimes laundered once
            n += buf.add([_any_ts(rng, kb_day)], vendor, middle, [kick], "transfer",
                         alert_id=sid, alert_type="invoice_kickback")
            n += buf.add([_any_ts(rng, kb_day + rng.uniform(1, 3))], middle, insider,
                         [kick * rng.uniform(0.93, 0.99)], "transfer",
                         alert_id=sid, alert_type="invoice_kickback")
        else:
            n += buf.add([_any_ts(rng, kb_day)], vendor, insider, [kick], "transfer",
                         alert_id=sid, alert_type="invoice_kickback")

    return {"id": sid, "typology": "invoice_kickback", "victim": victim["ops"],
            "accounts": [vendor, insider, middle], "corrupted_existing": corrupted_existing,
            "start_day": start_day, "end_day": round(t_day, 1), "n_txns": n}


# ---- typology 5: larceny (insider drains funds, camouflaged as payables) ---------

def larceny(world: World, buf: EventBuffer, rng: np.random.Generator,
            sid: str, start_day: int, busy: dict) -> dict:
    p = world.cfg["fraud"]["larceny"]
    horizon = int(world.cfg["days"])
    victim = _pick_victim(world, rng, busy, start_day, start_day + 200)
    insider = str(rng.choice(victim["employees"]))
    own_account = rng.random() < p["own_account_frac"]
    dest = insider if own_account else world.new_shell_vendor(start_day)
    # own-account theft is EXPENSE fraud: padded claims riding the reimbursement
    # rail at reimbursement-like scale (a 5k "expense" would stand out; real
    # expense fraudsters skim). Shell-vendor theft is fake payables at invoice scale.
    tx_type = "reimbursement" if own_account else "vendor_payment"

    n = 0
    t_day = float(start_day)
    if own_account:
        amount = float(lognorm(rng, 400, 0.8))
    else:
        amount = victim["threshold"] * rng.uniform(*p["threshold_frac"])
    for _ in range(randint(rng, p["events"])):
        t_day += rng.uniform(*p["gap_days"])
        if t_day >= horizon:
            break
        parts = (_structured(rng, amount, victim["threshold"], max_parts=randint(rng, p["splits"]))
                 if rng.random() < p["split_frac"] else [amount])
        for i, part in enumerate(parts):
            ts = _office_ts(rng, t_day + i * rng.uniform(0.3, 1.5))
            if ts < horizon * DAY:
                n += buf.add([ts], victim["ops"], dest, [part], tx_type,
                             alert_id=sid, alert_type="larceny")
        amount *= rng.uniform(*p["escalation"])          # confidence grows

    return {"id": sid, "typology": "larceny", "victim": victim["ops"],
            "accounts": [dest], "own_account": own_account,
            "start_day": start_day, "end_day": round(t_day, 1), "n_txns": n}


# ---- driver -----------------------------------------------------------------------

_TYPOLOGIES = {
    "laundering_cycle": laundering_cycle,
    "mule_fanin": mule_fanin,
    "lapping": lapping,
    "invoice_kickback": invoice_kickback,
    "larceny": larceny,
}


def generate_fraud(world: World, buf: EventBuffer, rng: np.random.Generator) -> list[dict]:
    """Instantiate every configured scenario. Returns provenance records."""
    fcfg = world.cfg["fraud"]
    lo, hi = fcfg["start_day_range"]
    busy: dict[int, list] = {}
    recruited: set[str] = set()
    records: list[dict] = []
    seq = 0
    for typology, fn in _TYPOLOGIES.items():
        for _ in range(int(fcfg[typology]["n_scenarios"])):
            seq += 1
            sid = f"{typology[:4].upper()}-{seq:04d}"
            start = int(rng.integers(lo, hi + 1))
            if typology in ("mule_fanin", "laundering_cycle"):
                rec = fn(world, buf, rng, sid, start, busy, recruited)
            else:
                rec = fn(world, buf, rng, sid, start, busy)
            records.append(rec)
    return records
