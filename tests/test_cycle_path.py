"""cycle_path must mirror cycle_features exactly (same BFS, same shortest cycle).

The alert-evidence layer (topology/paths.py) presents cycle_path's output as THE
loop behind a stored in_cycle feature — so any divergence between the two
searches would show auditors unverified evidence.
"""
import numpy as np

from topology.window_graph import WindowGraph


def test_cycle_path_mirrors_cycle_features():
    rng = np.random.default_rng(7)
    cycles = 0
    for _ in range(150):
        n_nodes = int(rng.integers(3, 12))
        g = WindowGraph(int(rng.integers(3, 15)))
        t = 0
        for _ in range(int(rng.integers(20, 120))):
            t += int(rng.integers(0, 3))
            u = int(rng.integers(n_nodes))
            v = int(rng.integers(n_nodes))
            if u == v:
                continue
            g.evict(t)
            feat = g.cycle_features(v, u, 6, 4000)
            path = g.cycle_path(v, u, 6, 4000)
            assert (feat is None) == (path is None)
            if feat is not None:
                cycles += 1
                length, p_min_amt, p_max_amt, p_min_ts = feat
                amts = [a for (_, _, a, _) in path]
                tss = [ts for (_, _, _, ts) in path]
                assert len(path) + 1 == length          # path + closing edge
                assert min(amts) == p_min_amt and max(amts) == p_max_amt
                assert min(tss) == p_min_ts
                assert path[0][0] == v and path[-1][1] == u
                assert all(path[i][1] == path[i + 1][0]
                           for i in range(len(path) - 1))  # forward-chained
            g.add(t, u, v, float(rng.uniform(1, 100)))
    assert cycles > 500  # the property actually got exercised
