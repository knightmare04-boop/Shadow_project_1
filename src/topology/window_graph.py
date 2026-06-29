"""WindowGraph — an incremental directed multigraph over a trailing time window.

This is the data structure the streaming topology engine walks. It holds only the
edges currently inside the trailing window ``[now - window, now]`` and supports the
two operations the engine needs in time order:

    * cheap O(1) degree / fan queries against the *current* (past-only) state, and
    * a bounded shortest-cycle search (does adding ``u -> v`` close a loop ``v ⇝ u``).

Leakage-safety is a property of *how the engine uses this object*, not of the
object itself: the engine reads a transaction's features **before** calling
``add`` for that transaction, so a transaction can never see itself or anything
later. The window only ever evicts edges that are too *old*; it never holds a
future edge. See ``engine.extract_features``.

All node ids are integers (the engine factorizes account strings up front for
speed). Each directed pair also remembers the ``(amount, timestamp)`` of its
**most recent** in-window edge (``self.last``), so the cycle search can report
amount-conservation and tightness around a closed loop. Tracking only the most
recent edge is correct under FIFO eviction: edges are evicted oldest-first, so the
remembered "last" edge is always still in the window until the pair empties.
"""
from __future__ import annotations

from collections import defaultdict, deque


class WindowGraph:
    """A directed multigraph holding only edges within a trailing time window.

    Parameters
    ----------
    window:
        Trailing window length in the dataset's native time units. Edges with
        ``timestamp < now - window`` are evicted. ``None`` means *unbounded*
        (keep every edge seen so far in the current partition).
    """

    __slots__ = ("window", "_edges", "out", "in_", "indeg", "outdeg", "last")

    def __init__(self, window: int | float | None):
        self.window = window
        self._edges: deque[tuple[int, int, int]] = deque()      # (ts, u, v), time order
        self.out: dict[int, dict[int, int]] = defaultdict(dict)  # out[u][v] = multiplicity
        self.in_: dict[int, dict[int, int]] = defaultdict(dict)  # in_[v][u] = multiplicity
        self.indeg: dict[int, int] = defaultdict(int)            # total in-edges  (multiplicity)
        self.outdeg: dict[int, int] = defaultdict(int)           # total out-edges (multiplicity)
        # most-recent (amount, ts) per directed pair; lives exactly as long as out[u][v]
        self.last: dict[int, dict[int, tuple[float, int | float]]] = defaultdict(dict)

    # ---- mutation -----------------------------------------------------------
    def evict(self, now: int | float) -> None:
        """Drop every edge older than the trailing window relative to ``now``."""
        if self.window is None:
            return
        cutoff = now - self.window
        edges = self._edges
        out = self.out
        last = self.last
        while edges and edges[0][0] < cutoff:
            ts, u, v = edges.popleft()
            # out side: decrement multiplicity; when the pair empties, drop its
            # remembered last-edge attrs too (kept in lock-step with out[u][v]).
            ou = out[u]
            c = ou[v] - 1
            if c <= 0:
                del ou[v]
                if not ou:
                    del out[u]
                lu = last.get(u)
                if lu is not None:
                    lu.pop(v, None)
                    if not lu:
                        del last[u]
            else:
                ou[v] = c
            self._dec(self.in_, v, u)
            self.outdeg[u] -= 1
            self.indeg[v] -= 1

    def add(self, ts: int | float, u: int, v: int, amount: float = 0.0) -> None:
        """Insert edge ``u -> v`` stamped ``ts`` (call AFTER reading its features).

        ``amount`` is remembered as this pair's most-recent edge attributes (used by
        ``cycle_features`` for amount-conservation / tightness). Adds arrive in
        non-decreasing ``ts`` order, so the latest write is genuinely the newest edge.
        """
        self._edges.append((ts, u, v))
        ou = self.out[u]
        ou[v] = ou.get(v, 0) + 1
        iv = self.in_[v]
        iv[u] = iv.get(u, 0) + 1
        self.outdeg[u] += 1
        self.indeg[v] += 1
        self.last[u][v] = (amount, ts)

    @staticmethod
    def _dec(side: dict[int, dict[int, int]], a: int, b: int) -> None:
        inner = side[a]
        c = inner[b] - 1
        if c <= 0:
            del inner[b]
            if not inner:
                del side[a]
        else:
            inner[b] = c

    # ---- O(1) structural queries (current, past-only state) -----------------
    def fan_in(self, v: int) -> int:
        """Number of *distinct* accounts that have sent to ``v`` in the window."""
        d = self.in_.get(v)
        return len(d) if d else 0

    def fan_out(self, u: int) -> int:
        """Number of *distinct* accounts ``u`` has sent to in the window."""
        d = self.out.get(u)
        return len(d) if d else 0

    def in_degree(self, v: int) -> int:
        """Total in-edges to ``v`` in the window (counting parallel edges)."""
        return self.indeg.get(v, 0)

    def out_degree(self, u: int) -> int:
        """Total out-edges from ``u`` in the window (counting parallel edges)."""
        return self.outdeg.get(u, 0)

    # ---- bounded cycle search ----------------------------------------------
    def cycle_features(self, v: int, u: int, max_len: int, budget: int):
        """Shortest cycle that adding ``u -> v`` would close, with loop attributes.

        Breadth-first search for a directed path ``v ⇝ u`` already present in the
        window, so the first time ``u`` is reached gives the *shortest* such path.
        The closed cycle is ``u -> v ⇝ u``. On success the path is reconstructed and

            (length, path_min_amt, path_max_amt, path_min_ts)

        is returned, where ``length`` counts ALL cycle edges (path edges + the
        closing ``u -> v``) and the ``path_*`` aggregates range over the path edges'
        most-recent ``(amount, ts)`` attributes. The caller folds in the closing
        edge's own amount/ts to finish the conservation / tightness features.

        Returns ``None`` if no cycle exists within ``max_len`` / ``budget``. Bounds
        keep per-transaction cost flat on dense/hub-heavy graphs:
            * ``max_len``  — only cycles up to this many edges are detectable;
            * ``budget``   — abandon after visiting this many nodes (conservative
                             miss: returns ``None``, never a false cycle).

        Precondition: ``v != u`` (self-loops are handled by the engine directly).
        """
        out = self.out
        if v not in out:
            return None  # v has no outgoing edges -> cannot reach u
        pred = {v: -1}             # node -> BFS predecessor; -1 marks the root v
        frontier = [v]
        visited = 1
        depth = 0
        max_path = max_len - 1     # edges allowed on the v ⇝ u path
        closer = None              # node x whose edge x -> u closes the loop
        while frontier and depth < max_path and closer is None:
            depth += 1
            nxt: list[int] = []
            for x in frontier:
                neigh = out.get(x)
                if not neigh:
                    continue
                for w in neigh:
                    if w == u:
                        closer = x
                        break
                    if w not in pred:
                        pred[w] = x
                        visited += 1
                        if visited > budget:
                            return None
                        nxt.append(w)
                if closer is not None:
                    break
            frontier = nxt
        if closer is None:
            return None

        # Walk the path backwards (closer -> u, then pred links to v), aggregating
        # the most-recent (amount, ts) of each hop from self.last.
        last = self.last
        node = closer
        succ = u                   # current hop is (node -> succ)
        p_min_amt = float("inf")
        p_max_amt = float("-inf")
        p_min_ts: float = float("inf")
        hops = 0
        while node != -1:
            amt, ts = last[node][succ]
            if amt < p_min_amt:
                p_min_amt = amt
            if amt > p_max_amt:
                p_max_amt = amt
            if ts < p_min_ts:
                p_min_ts = ts
            hops += 1
            succ = node
            node = pred[node]
        return hops + 1, p_min_amt, p_max_amt, p_min_ts
