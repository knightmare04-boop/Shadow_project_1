"""LapMemory — per-account rolling amount memory for the lapping detector.

Lapping ("robbing Peter to pay Paul") is covering a prior shortfall with new,
near-equal money — a sequence of similar amounts on one entity, often sourced from
*different* counterparties. Unlike the cycle / fan-in detectors, lapping is NOT a
graph-window feature: per the locked slow-fraud rule (PROJECT_OVERVIEW A.8 rule 1)
it uses **cheap, count-based per-account memory** — the last ``k`` amounts an account
saw in a given role — so it can span months at near-zero cost, independent of the
graph window's time bound.

The discriminative signal is recurrence *with counterparty diversity*: many distinct
payers sending near-equal amounts looks like lapping/collection, whereas the same
payer repeating one amount is ordinary recurring billing (and would otherwise inflate
a naive recurrence count — the same "too common" trap raw cycle membership fell into).

Leakage-safety is a property of *usage*, identical to ``WindowGraph``: the engine
reads a transaction's features **before** calling ``record`` for it, so a transaction
never sees itself or anything later. Account ids are integers (the engine factorizes
the unified namespace up front).
"""
from __future__ import annotations

from collections import defaultdict, deque


class LapMemory:
    """Rolling memory of each account's recent ``(amount, counterparty)`` in one role.

    Parameters
    ----------
    k:
        How many recent amounts to remember per account (count-based, so it spans
        whatever time those ``k`` transactions cover — the "long memory" property).
    tol:
        Relative tolerance for "near-equal": an amount ``a`` matches the query ``q``
        when ``|a - q| <= tol * q``.
    """

    __slots__ = ("k", "tol", "mem")

    def __init__(self, k: int, tol: float):
        self.k = k
        self.tol = tol
        self.mem: dict[int, deque[tuple[float, int]]] = defaultdict(lambda: deque(maxlen=k))

    def recurrence(self, acct: int, amount: float) -> tuple[int, int]:
        """Against ``acct``'s remembered amounts, return
        ``(#within tol of `amount`, #distinct counterparties among those)``.

        Reads only what was ``record``ed before now (past-only). Returns ``(0, 0)``
        when the account has no history yet.
        """
        d = self.mem.get(acct)
        if not d:
            return 0, 0
        lo = amount - self.tol * amount
        hi = amount + self.tol * amount
        if lo > hi:                      # negative amount (e.g. corrupted future row): normalise
            lo, hi = hi, lo
        cps: set[int] = set()
        cnt = 0
        for a, cp in d:
            if lo <= a <= hi:
                cnt += 1
                cps.add(cp)
        return cnt, len(cps)

    def record(self, acct: int, amount: float, counterparty: int) -> None:
        """Append this transaction to ``acct``'s memory (call AFTER reading features)."""
        self.mem[acct].append((amount, counterparty))
