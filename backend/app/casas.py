"""The Assembleias the project publishes (frontend/data/casas.json) and the source adapter of each.

Every Assembleia publishes in its own way, so each one has its own ETL module; they all write a
snapshot of the same shape (data/<uf>/snapshot.json). To add a casa: write its adapter, register it
in ADAPTERS, add it to casas.json and its texts to frontend/lib/uf.ts and frontend/lib/method.ts.
"""
from __future__ import annotations

import importlib
import json
from typing import Callable

from . import config

ADAPTERS = {"RJ": "app.etl.snapshot_alerj", "SP": "app.etl.snapshot_alesp"}


def load_casas() -> list[dict]:
    return json.loads((config.FRONTEND_DATA_DIR / "casas.json").read_text(encoding="utf-8"))["casas"]


def casa_ufs() -> list[str]:
    return [c["uf"].upper() for c in load_casas()]


def adapter(uf: str) -> Callable:
    """run(args) -> int for the casa's ETL."""
    uf = uf.upper()
    if uf not in ADAPTERS:
        raise KeyError(f"no source adapter for {uf}; see app/casas.py")
    return importlib.import_module(ADAPTERS[uf]).run
