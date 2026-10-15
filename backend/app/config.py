"""Paths, identity and politeness settings shared by the ETL."""
from __future__ import annotations

from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"            # every download, keyed by host and request, shared by the casas
FRONTEND_DATA_DIR = PROJECT_DIR / "frontend" / "data"

USER_AGENT = "tomoyo-g0v-research (contact: g0v@tomoyo.systems)"
REQUEST_DELAY_S = 1.0
TIMEOUT_S = 120.0

# System roots plus intermediates that some legislative hosts forget to send.
CA_BUNDLE = BACKEND_DIR / "app" / "cabundle.pem"


def snapshot_path(uf: str) -> Path:
    return DATA_DIR / uf.lower() / "snapshot.json"


def photos_dir(uf: str) -> Path:
    return DATA_DIR / uf.lower() / "photos"


# --- Assembleia Legislativa do Estado de São Paulo (ALESP) ----------------------------------------
ALESP = "https://www.al.sp.gov.br"
ALESP_API = "https://legis-api-portal-prd.al.sp.gov.br"          # the portal's own JSON API (presence, deputies)
ALESP_DADOS = f"{ALESP}/repositorioDados"                          # open data files (XML, zipped XML)
ALESP_FOTOS = "https://www3.al.sp.gov.br/legis"
