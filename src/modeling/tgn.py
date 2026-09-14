"""Temporal Graph Network (TGN) embeddings — the learned-structure challenger arm.

A lightweight, CPU-friendly TGN (Rossi et al. 2020 style) that turns the
transaction edge stream into a per-transaction embedding, to be compared against
the hand-crafted topology features inside the modern-ablation
(``experiments/modern.py``). Three properties are non-negotiable and hold by
construction:

1. **Zero lookahead (rule 4).** Events are processed in (timestamp, id) order.
   Each account keeps a *memory* vector updated only by events already seen. A
   transaction's embedding is read from the memories of its two accounts BEFORE
   the transaction itself (or anything later) is folded in — the embedding for
   event at time T mathematically cannot contain information from events > T.
   (Within a chronological mini-batch, memories are frozen at batch start; batch
   neighbours are *excluded*, never included — conservative, still no lookahead.)
2. **Label-free.** Weights are trained by self-supervised temporal link
   prediction (real next edge vs a random negative destination) on the TRAIN
   period only — the network never sees a fraud label. Labels are consumed
   exclusively by the downstream XGBoost head, so no label leakage is possible
   through the embedding. After training, weights are FROZEN and the stream is
   replayed over train+val+test; memories keep rolling forward (past-only
   information, the same discipline as the expanding account statistics).
3. **Amount-blind.** Messages carry only graph dynamics (who↔who, time gaps) —
   no amounts. The old A.4d lesson: amount-derived "topology" re-smuggles the
   amount signal. Any lift from these embeddings is therefore structural /
   temporal, directly comparable to the structure-only probe.

Output: ``data/processed/<name>/features_tgn.parquet`` with ``transaction_id``,
2*dim memory columns (``tgn_s*``, ``tgn_d*``) and ``tgn_edge_expectedness`` —
the frozen link-predictor's probability that this edge was "expected", a small
interpretable anomaly signal in its own right.

Run:  python -m modeling.tgn banksim
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn

from common.config import get_dataset
from modeling.harness import time_split

log = logging.getLogger(__name__)


class _TGN(nn.Module):
    """Memory + GRU update + time encoding + link-prediction head."""

    def __init__(self, dim: int = 32, time_dim: int = 8):
        super().__init__()
        self.dim, self.time_dim = dim, time_dim
        # cos(w * log1p(dt) + b) — a Time2Vec-style periodic encoding of the gap
        self.time_w = nn.Parameter(torch.randn(time_dim))
        self.time_b = nn.Parameter(torch.zeros(time_dim))
        # separate update cells: sending and receiving are different behaviours
        self.gru_src = nn.GRUCell(dim + time_dim, dim)
        self.gru_dst = nn.GRUCell(dim + time_dim, dim)
        self.link = nn.Sequential(
            nn.Linear(2 * dim + time_dim, 64), nn.ReLU(), nn.Linear(64, 1),
        )

    def time_enc(self, dt: torch.Tensor) -> torch.Tensor:
        z = torch.log1p(dt.clamp(min=0)).unsqueeze(-1)
        return torch.cos(z * self.time_w + self.time_b)

    def link_logit(self, mem_s, mem_d, tenc):
        return self.link(torch.cat([mem_s, mem_d, tenc], dim=-1)).squeeze(-1)


def _last_occurrence(ids: np.ndarray):
    """(unique ids, position of each id's LAST occurrence) — deterministic
    batch-memory writes when a node appears several times in one batch."""
    uniq, first_in_reversed = np.unique(ids[::-1], return_index=True)
    return uniq, len(ids) - 1 - first_in_reversed


class TGNEmbedder:
    def __init__(self, dim: int = 32, time_dim: int = 8, batch: int = 500,
                 epochs: int = 3, lr: float = 1e-3, seed: int = 42):
        self.dim, self.time_dim, self.batch = dim, time_dim, batch
        self.epochs, self.lr, self.seed = epochs, lr, seed

    # ---- stream mechanics ----------------------------------------------------
    @staticmethod
    def _write(mem, ids: torch.Tensor, values: torch.Tensor):
        """Deterministic batch write: when a node occurs several times in one
        batch, its LAST occurrence wins (events are time-ordered)."""
        u, pos = _last_occurrence(ids.numpy())
        mem[torch.from_numpy(u).long()] = values[torch.from_numpy(pos).long()]

    def _fold_batch(self, model, mem, s, d, dt_s, dt_d):
        """Apply this batch's messages to memory (GRU update). Amount-blind:
        the message is [counterparty memory, time-gap encoding] only."""
        te_s, te_d = model.time_enc(dt_s), model.time_enc(dt_d)
        new_s = model.gru_src(torch.cat([mem[d], te_s], dim=-1), mem[s])
        new_d = model.gru_dst(torch.cat([mem[s], te_d], dim=-1), mem[d])
        self._write(mem, s, new_s)
        self._write(mem, d, new_d)
        return mem

    def _train_epoch(self, model, optimizer, src, dst, ts, n_nodes, rng):
        """Self-supervised temporal link prediction over TRAIN events only.

        The previous batch's messages are folded into memory *inside* the current
        batch's autograd graph (then detached) — the standard TGN trick that lets
        the loss reach the GRU/time-encoder weights while keeping BPTT truncated
        to one batch.
        """
        mem = torch.zeros(n_nodes, self.dim)
        last = torch.zeros(n_nodes)
        pending = None                      # previous batch's (s, d, dt_s, dt_d)
        total_loss, n_loss = 0.0, 0
        n = len(src)
        for lo in range(0, n, self.batch):
            hi = min(lo + self.batch, n)
            s = torch.from_numpy(src[lo:hi]).long()
            d = torch.from_numpy(dst[lo:hi]).long()
            t = torch.from_numpy(ts[lo:hi]).float()
            dt_s, dt_d = t - last[s], t - last[d]

            mem = mem.detach()
            if pending is not None:         # replay last batch's updates WITH grad
                mem = self._fold_batch(model, mem.clone(), *pending)

            mem_s, mem_d = mem[s], mem[d]   # memory of strictly earlier events only
            te_s = model.time_enc(dt_s)
            neg = torch.from_numpy(rng.integers(0, n_nodes, len(s))).long()
            pos_logit = model.link_logit(mem_s, mem_d, te_s)
            neg_logit = model.link_logit(mem_s, mem[neg], te_s)
            loss = nn.functional.binary_cross_entropy_with_logits(
                torch.cat([pos_logit, neg_logit]),
                torch.cat([torch.ones_like(pos_logit), torch.zeros_like(neg_logit)]),
            )
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(s)
            n_loss += len(s)

            pending = (s, d, dt_s, dt_d)
            self._write(last, s, t)         # deterministic (last occurrence wins)
            self._write(last, d, t)
        return total_loss / max(n_loss, 1)

    def _inference_pass(self, model, src, dst, ts, n_nodes,
                        capture: np.ndarray, scores: np.ndarray):
        """Frozen replay over ALL events: capture each event's PRE-update
        memories (zero lookahead by construction) and its edge-expectedness."""
        mem = torch.zeros(n_nodes, self.dim)
        last = torch.zeros(n_nodes)
        n = len(src)
        for lo in range(0, n, self.batch):
            hi = min(lo + self.batch, n)
            s = torch.from_numpy(src[lo:hi]).long()
            d = torch.from_numpy(dst[lo:hi]).long()
            t = torch.from_numpy(ts[lo:hi]).float()
            dt_s, dt_d = t - last[s], t - last[d]

            mem_s, mem_d = mem[s], mem[d]
            capture[lo:hi, : self.dim] = mem_s.numpy()
            capture[lo:hi, self.dim:] = mem_d.numpy()
            scores[lo:hi] = torch.sigmoid(
                model.link_logit(mem_s, mem_d, model.time_enc(dt_s))).numpy()

            self._fold_batch(model, mem, s, d, dt_s, dt_d)
            self._write(last, s, t)
            self._write(last, d, t)

    # ---- public API ----------------------------------------------------------
    def fit_transform(self, edges: pd.DataFrame, train_mask: np.ndarray) -> pd.DataFrame:
        """Train on train-period events, then frozen replay over ALL events."""
        torch.manual_seed(self.seed)
        rng = np.random.default_rng(self.seed)
        torch.set_num_threads(max(torch.get_num_threads(), 4))

        codes, uniques = pd.factorize(
            pd.concat([edges["source_account"].astype(str),
                       edges["dest_account"].astype(str)], ignore_index=True))
        n = len(edges)
        src = codes[:n].astype(np.int64)
        dst = codes[n:].astype(np.int64)
        ts = edges["timestamp"].to_numpy(dtype=np.float64)
        n_nodes = len(uniques)
        log.info("TGN: %d events, %d nodes, dim=%d, epochs=%d (train events: %d)",
                 n, n_nodes, self.dim, self.epochs, int(train_mask.sum()))

        model = _TGN(self.dim, self.time_dim)
        opt = torch.optim.Adam(model.parameters(), lr=self.lr)
        # weights learn from TRAIN-period events only; val/test events are absent
        # from the training stream entirely (structure-blind, not just label-blind)
        tr = np.asarray(train_mask, dtype=bool)
        for ep in range(self.epochs):
            loss = self._train_epoch(model, opt, src[tr], dst[tr], ts[tr], n_nodes, rng)
            log.info("TGN epoch %d/%d — link-prediction loss %.4f", ep + 1, self.epochs, loss)

        model.eval()
        capture = np.zeros((n, 2 * self.dim), dtype=np.float32)
        scores = np.zeros(n, dtype=np.float32)
        with torch.no_grad():                       # frozen weights; memory rolls forward
            self._inference_pass(model, src, dst, ts, n_nodes, capture, scores)

        cols = [f"tgn_s{i}" for i in range(self.dim)] + [f"tgn_d{i}" for i in range(self.dim)]
        out = pd.DataFrame(capture, columns=cols)
        out.insert(0, "transaction_id", edges["transaction_id"].to_numpy())
        out["tgn_edge_expectedness"] = scores
        return out


def build_embeddings(name: str, *, dim: int = 32, epochs: int = 3, batch: int = 500,
                     seed: int = 42, force: bool = False) -> Path:
    """Build (or reuse) the TGN embedding table for one dataset."""
    ds = get_dataset(name)
    proc = Path(ds["processed_dir"])
    out_path = proc / "features_tgn.parquet"
    if out_path.exists() and not force:
        log.info("[%s] TGN embeddings already exist -> %s", name, out_path.name)
        return out_path

    edges = pd.read_csv(proc / "edges_transactions.csv", low_memory=False)
    if not edges["timestamp"].is_monotonic_increasing:
        edges = edges.sort_values("timestamp", kind="stable").reset_index(drop=True)
    # identical split logic to the harness, so "train period" means the same thing
    pcol = ds.get("partition_col")
    partition = edges[pcol] if pcol and pcol in edges.columns else None
    train_mask, _, _ = time_split(edges["timestamp"], partition=partition)

    emb = TGNEmbedder(dim=dim, epochs=epochs, batch=batch, seed=seed).fit_transform(
        edges, np.asarray(train_mask))
    emb.to_parquet(out_path, index=False)
    with open(proc / "features_tgn_manifest.json", "w", encoding="utf-8") as f:
        json.dump({"dataset": name, "dim": dim, "epochs": epochs, "batch": batch,
                   "seed": seed, "n_rows": int(len(emb)),
                   "cols": [c for c in emb.columns if c != "transaction_id"],
                   "amount_blind": True, "label_free": True,
                   "train_events_only_for_weights": True}, f, indent=2)
    log.info("[%s] TGN embeddings -> %s (%d cols)", name, out_path.name, emb.shape[1] - 1)
    return out_path


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--dim", type=int, default=32)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch", type=int, default=500)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    print(build_embeddings(a.dataset, dim=a.dim, epochs=a.epochs, batch=a.batch,
                           seed=a.seed, force=a.force))
