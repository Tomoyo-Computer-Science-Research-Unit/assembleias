"""Run the ETL of one Assembleia and write data/<uf>/snapshot.json.

    python -m app.etl.export_snapshot --uf SP --all       # daily: both legislatures, refresh what can change
    python -m app.etl.export_snapshot --uf RJ --all
    python -m app.etl.export_snapshot --uf SP --offline   # rebuild from the raw cache only (no network)

Every response is cached under data/raw/. A re-run only hits the network for what can change
(rosters, the current year's vote lists, the newest presence months) and for documents it has
never read. Each casa has its own adapter (app/casas.py); they all write the same snapshot shape.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .. import config
from ..casas import adapter, casa_ufs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--uf", choices=casa_ufs(), default="RJ", type=str.upper, help="casa (frontend/data/casas.json); RJ by default")
    ap.add_argument("--all", action="store_true", help="daily mode: everything from --from-year 2019, no document budget")
    ap.add_argument("--max-docs", type=int, default=0, help="max vote documents to read (0 = no limit)")
    ap.add_argument("--from-year", type=int, default=2019, help="first year (the 2019–2023 legislature starts in 2019)")
    ap.add_argument("--presenca-from", type=int, default=2019)
    ap.add_argument("--presenca-refresh-from", type=str, default=None, metavar="YYYY-MM",
                    help="also re-pull presence months from this one on (absences are justified retroactively)")
    ap.add_argument("--offline", action="store_true", help="never touch the network; rebuild from data/raw only")
    ap.add_argument("--no-refresh", action="store_true", help="do not re-fetch index pages (rosters, current lists)")
    ap.add_argument("--out", type=Path, default=None, help="default: data/<uf>/snapshot.json")
    args = ap.parse_args(argv)
    if args.all:
        args.from_year, args.presenca_from, args.max_docs = 2019, 2019, 0
    if args.out is None:
        args.out = config.snapshot_path(args.uf)
    return adapter(args.uf)(args)


if __name__ == "__main__":
    raise SystemExit(main())
