"""Neo4j connection — env-configured, with a graceful availability check.

Environment variables (defaults suit a local Neo4j Desktop / Docker instance):
    NEO4J_URI       bolt://localhost:7687
    NEO4J_USER      neo4j
    NEO4J_PASSWORD  (required — no default password is assumed)
"""
from __future__ import annotations

import logging
import os

from neo4j import GraphDatabase

log = logging.getLogger(__name__)

SETUP_HINT = """\
Neo4j is not reachable. The audit alerts (results/<ds>/alerts/alerts.json) are
fully standalone - the demo only VISUALIZES them. To run the visual demo:

  Option A - Neo4j Desktop: create a local DBMS (v5+), start it, set a password.
  Option B - Docker:
      docker run -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/<password> neo4j:5

Then set the environment variables and retry:
      $env:NEO4J_PASSWORD = "<password>"          (PowerShell)
      # optional: $env:NEO4J_URI, $env:NEO4J_USER (default bolt://localhost:7687, neo4j)
"""


def get_driver():
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        raise RuntimeError("NEO4J_PASSWORD is not set")
    return GraphDatabase.driver(uri, auth=(user, password))


def ping(driver=None) -> bool:
    """True if a Neo4j instance answers; False (with instructions) otherwise."""
    try:
        own = driver is None
        if own:
            driver = get_driver()
        try:
            driver.verify_connectivity()
            return True
        finally:
            if own:
                driver.close()
    except Exception as e:  # connection refused, auth, missing password...
        log.warning("Neo4j unavailable (%s)", e)
        print(SETUP_HINT)
        return False
