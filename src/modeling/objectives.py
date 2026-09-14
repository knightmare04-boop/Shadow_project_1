"""Custom XGBoost objectives — the focal-loss imbalance mechanism (rule 1 alternative).

Focal loss (Lin et al. 2017) down-weights *easy* examples by the factor
``(1 - p_t)^gamma`` so training capacity concentrates on hard ones. Under extreme
imbalance the rare fraud cases are almost all "hard", so they are up-weighted
implicitly — without resampling and without a class-prior weight.

Deliberate design choice: this is the **unweighted** (symmetric, alpha-free) focal
loss. The alpha-balanced variant multiplies in a per-class weight, which would mean
running class weights *and* focal focusing at once — exactly the two-mechanisms-
at-once mistake rule 1 forbids. Keeping it alpha-free makes "class_weight" vs
"focal" a clean single-mechanism comparison (see Boundary Focal Loss, 2021, and
the modernization plan).

XGBoost integration notes:
  * With a callable objective the model's raw output is a MARGIN (log-odds), not a
    probability — callers must apply a sigmoid (see ``harness._predict_scores``).
  * The gradient is closed-form; the hessian uses a central finite difference of
    the gradient (standard practice for focal-XGBoost; the analytic hessian is
    long and error-prone, and the numeric one is exact to O(eps^2)).
"""
from __future__ import annotations

import numpy as np

_EPS_P = 1e-12      # probability clip (log stability)
_EPS_H = 1e-4       # finite-difference step for the hessian
_MIN_HESS = 1e-16   # XGBoost requires strictly positive hessians


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -60, 60)))


def _focal_grad(margin: np.ndarray, y: np.ndarray, gamma: float) -> np.ndarray:
    """d(focal loss)/d(margin), closed form.

    For y=1, with p = sigmoid(margin):
        L  = -(1-p)^g * log(p)
        dL/dmargin = g*p*(1-p)^g*log(p) - (1-p)^(g+1)
    The y=0 case follows by the symmetry p <-> 1-p, margin <-> -margin.
    """
    p = np.clip(sigmoid(margin), _EPS_P, 1.0 - _EPS_P)

    def g1(q):  # gradient for a positive example with predicted prob q
        return gamma * q * (1.0 - q) ** gamma * np.log(q) - (1.0 - q) ** (gamma + 1.0)

    return np.where(y == 1, g1(p), -g1(1.0 - p))


def focal_objective(gamma: float = 2.0):
    """Return an XGBoost custom objective ``f(y_true, margin) -> (grad, hess)``.

    ``gamma=0`` reduces exactly to plain log-loss (sanity anchor: grad = p - y).
    """
    def obj(y_true: np.ndarray, margin: np.ndarray):
        y = np.asarray(y_true).astype(np.float64)
        m = np.asarray(margin, dtype=np.float64)
        grad = _focal_grad(m, y, gamma)
        hess = (_focal_grad(m + _EPS_H, y, gamma)
                - _focal_grad(m - _EPS_H, y, gamma)) / (2.0 * _EPS_H)
        return grad, np.maximum(hess, _MIN_HESS)

    return obj
