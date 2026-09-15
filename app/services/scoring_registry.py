"""Registry of live FraudScoringService instances, one per dataset, loaded
at app startup (app.main's lifespan) from the "online" bundles Module 5
trains (tools/train_online_bundles.py). `/ready` reports honestly false
until at least one is loaded — see app/api/system.py.

KNOWN ARCHITECTURAL CONSTRAINT (Module 11 council review, confirmed
correct and NOT resolved in this build — do not "fix" by adding
`--workers N` without reading this first): each FraudScoringService holds
its WindowGraph/LapMemory state in THIS PROCESS's memory
(app/services/online_topology.py, app/services/online_ordinary.py). That
state IS the leakage-free window every score depends on. Running this app
behind more than one worker process (`uvicorn --workers 4`, or any
horizontal replica) would give each worker its OWN independent, diverging
graph — same transaction scored differently depending on which worker
happened to receive it, and no worker ever seeing the full picture. The
k6 load-test degradation documented in docs/TESTING_MODULE9.md (p95 8.18s
at 500 VUs) looks like an ordinary scaling problem but is NOT one you can
solve with more processes until this state is externalized (e.g. a shared
Redis-backed graph store, or routing all scoring for a dataset through one
dedicated single-writer process/queue). Scale the REST of the app
(vendors/invoices/payments CRUD) freely; do not scale the process holding
this registry without addressing this first.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.services.scoring_service import FraudScoringService

log = get_logger(__name__)

_SERVICES: dict[str, FraudScoringService] = {}

# Categorical vocabularies fixed at training time (see the batch pipeline's
# one-hot encoding in src/features/build.py) — required so the online path
# produces the SAME columns in the SAME order the bundle expects. Extend
# this as more datasets are wired up; an unlisted dataset just gets no
# categoricals (fine for datasets whose ordinary_cols have none).
_CATEGORICAL_VOCAB: dict[str, dict[str, list[str]]] = {
    "banksim": {"category": [
        "es_barsandrestaurants", "es_contents", "es_fashion", "es_food", "es_health",
        "es_home", "es_hotelservices", "es_hyper", "es_leisure", "es_otherservices",
        "es_sportsandtoys", "es_tech", "es_transportation", "es_travel", "es_wellnessandbeauty",
    ]},
    # synth_erp is the domain match for live ERP payments (its tx_type
    # vocabulary IS "vendor_payment", "payroll", etc.) — see
    # app/services/payment_service.py's scoring integration.
    "synth_erp": {"tx_type": [
        "payroll", "recurring_bill", "refund", "reimbursement", "sale", "transfer", "vendor_payment",
    ]},
}

# Static per-account attributes (src_/dest_ prefixed columns) this dataset's
# ordinary_cols expects, with a fallback default for accounts the app hasn't
# explicitly registered via set_static_attrs (e.g. new vendors) — avoids NaN
# on every live payment until each vendor is onboarded with a real value.
_STATIC_ATTR_DEFAULTS: dict[str, dict[str, float]] = {
    "synth_erp": {"creation_day": 0.0},
}


def scoring_bundles_loaded() -> bool:
    return len(_SERVICES) > 0


def get_service(dataset: str) -> FraudScoringService | None:
    return _SERVICES.get(dataset)


def loaded_datasets() -> list[str]:
    return sorted(_SERVICES.keys())


def load_all_online_bundles(datasets: list[str] | None = None) -> dict[str, bool]:
    """Called once at startup. Missing artifacts are logged and skipped —
    a dataset the app hasn't trained yet just isn't servable, it doesn't
    crash the whole process."""
    from common.config import get_dataset, load_config
    from modeling.score import load_bundle
    from topology.engine import resolve_params

    if datasets is None:
        datasets = list(load_config().get("datasets", {}).keys())

    results: dict[str, bool] = {}
    for name in datasets:
        try:
            ds_cfg = get_dataset(name)
            bundle = load_bundle(f"artifacts/{name}/online")
            topo_params = resolve_params(ds_cfg)
            service = FraudScoringService(
                dataset=name, bundle=bundle, topology_params=topo_params,
                categorical_prefixes=_CATEGORICAL_VOCAB.get(name),
            )
            service.ordinary.static_attr_defaults = _STATIC_ATTR_DEFAULTS.get(name, {})
            _SERVICES[name] = service
            results[name] = True
            log.info("scoring_bundle_loaded", dataset=name, n_features=len(bundle.features),
                     threshold=bundle.threshold)
        except FileNotFoundError:
            results[name] = False
            log.warning("scoring_bundle_missing", dataset=name,
                       hint="run: python -m tools.train_online_bundles " + name)
        except Exception as exc:  # noqa: BLE001
            results[name] = False
            log.error("scoring_bundle_load_failed", dataset=name, error=str(exc))
    return results
