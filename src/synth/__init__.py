"""synth — the calibrated, behavior-driven synthetic ERP transaction generator.

Build Step: synthetic dataset (pulled forward from Phase 6 by recorded user
decision, 2026-07-13). The one binding design rule, inherited from the locked
architecture's "circularity trap" clause:

    Fraud is generated as BEHAVIOR (an agent with a goal), never as a PATTERN
    (a graph shape a detector looks for). Shapes must EMERGE from behavior.
    No module in this package may import from, reference, or be parameterized
    by ``topology`` detectors.

Modules:
    calibrate — measure reference statistics from the REAL datasets (the
                numbers the generator's parameters are anchored to).
    world     — the account population and its relationships (the economy).
    normal    — legitimate business behaviors (the overwhelming majority).
    fraud     — fraud scenario agents, one per typology, with evasion.
    generate  — orchestrator: world -> events -> raw CSVs + provenance.
    validate  — the realism battery: synthetic vs. real, reported honestly.
"""
