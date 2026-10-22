"""Polite HTTP downloader with an on-disk cache under data/raw/."""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

import httpx

from . import config


@dataclass(frozen=True)
class Fetched:
    url: str
    path: Path
    accessed_at: str
    sha256: str
    from_cache: bool

    def text(self, encoding: str = "utf-8") -> str:
        return self.path.read_bytes().decode(encoding, errors="replace")

    def json(self) -> dict:
        return json.loads(self.path.read_bytes().decode("utf-8", errors="replace"))


class Downloader:
    """GET/POST with caching keyed on (method, url, body). One request per second."""

    def __init__(self, raw_dir: Path = config.RAW_DIR, delay_s: float = config.REQUEST_DELAY_S,
                 offline: bool = False) -> None:
        self.raw_dir = raw_dir
        self.delay_s = delay_s
        self.offline = offline          # True: never touch the network (cache misses raise)
        self.requests_made = 0
        self._last = 0.0
        self._client = httpx.Client(
            headers={"User-Agent": config.USER_AGENT},
            verify=str(config.CA_BUNDLE),
            timeout=config.TIMEOUT_S,
            follow_redirects=True,
        )
        self.sources: dict[str, Fetched] = {}

    def _key(self, method: str, url: str, data: dict[str, str] | None) -> Path:
        host = urlsplit(url).hostname or "unknown"
        raw = method + "\n" + url + "\n" + json.dumps(data or {}, sort_keys=True, ensure_ascii=False)
        h = hashlib.sha1(raw.encode()).hexdigest()[:20]
        return self.raw_dir / host / h

    def _throttle(self) -> None:
        wait = self.delay_s - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def cache_path(self, method: str, url: str, data: dict[str, str] | None = None) -> Path:
        """Where the cache for this request lives; TextCache keeps its files beside it."""
        return self._key(method, url, data)

    def get_uncached(self, url: str) -> httpx.Response:
        """Throttled GET that bypasses the body cache (the caller stores what it needs)."""
        self._throttle()
        self.requests_made += 1
        r = self._client.get(url)
        r.raise_for_status()
        return r

    def fetch(self, url: str, *, data: dict[str, str] | None = None, refresh: bool = False) -> Fetched:
        method = "POST" if data is not None else "GET"
        base = self._key(method, url, data)
        body, meta = base.with_suffix(".body"), base.with_suffix(".json")
        cached = body.exists() and meta.exists()
        if cached and (not refresh or self.offline):
            m = json.loads(meta.read_text())
            f = Fetched(url, body, m["accessed_at"], m["sha256"], True)
        elif self.offline:
            raise FileNotFoundError(f"offline and not cached: {method} {url}")
        else:
            self._throttle()
            self.requests_made += 1
            r = self._client.post(url, data=data) if data is not None else self._client.get(url)
            r.raise_for_status()
            base.parent.mkdir(parents=True, exist_ok=True)
            body.write_bytes(r.content)
            accessed = datetime.now(timezone.utc).isoformat(timespec="seconds")
            sha = hashlib.sha256(r.content).hexdigest()
            meta.write_text(json.dumps({"url": url, "method": method, "data": data, "accessed_at": accessed,
                                        "sha256": sha, "status": r.status_code,
                                        "content_type": r.headers.get("content-type")}, ensure_ascii=False, indent=1))
            f = Fetched(url, body, accessed, sha, False)
        self.sources[f"{method} {url}"] = f
        return f


def pdf_text(data: bytes) -> str:
    """Text of a PDF in reading order (pdfium), one form feed between pages; soft hyphens at line ends removed."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(data)
    try:
        pages = []
        for i in range(len(doc)):
            page = doc[i]
            tp = page.get_textpage()
            pages.append(tp.get_text_range())
            tp.close()
            page.close()
    finally:
        doc.close()
    text = "\f".join(pages).replace("\r\n", "\n").replace("\r", "\n")
    return re.sub("￾\n?", "", text)


class TextCache:
    """For large PDFs whose text is all the ETL needs (the Diário Oficial): keep the extracted text,
    gzipped, plus the checksum of the PDF it came from; the PDF itself is not stored."""

    def __init__(self, dl: Downloader, sub: str = "pdftext") -> None:
        self.dl = dl
        self.sub = sub

    def fetch(self, url: str, keep: Callable[[str], bool] | None = None) -> tuple[str, dict]:
        base = self.dl.cache_path("GET", url)
        base = base.parent / self.sub / base.name
        gz, meta = base.with_suffix(".txt.gz"), base.with_suffix(".json")
        if meta.exists():
            m = json.loads(meta.read_text())
            text = gzip.decompress(gz.read_bytes()).decode("utf-8") if gz.exists() else ""
            self.dl.sources[f"GET {url}"] = Fetched(url, gz, m["accessed_at"], m["sha256"], True)
            return text, m
        if self.dl.offline:
            raise FileNotFoundError(f"offline and not cached: GET {url}")
        r = self.dl.get_uncached(url)
        accessed = datetime.now(timezone.utc).isoformat(timespec="seconds")
        sha = hashlib.sha256(r.content).hexdigest()
        if not r.content.startswith(b"%PDF"):
            raise ValueError(f"not a PDF: {url} ({r.headers.get('content-type')})")
        text = pdf_text(r.content)
        stored = keep is None or keep(text)
        base.parent.mkdir(parents=True, exist_ok=True)
        if stored:
            gz.write_bytes(gzip.compress(text.encode("utf-8"), 6))
        m = {"url": url, "accessed_at": accessed, "sha256": sha, "bytes": len(r.content), "chars": len(text), "text_stored": stored}
        meta.write_text(json.dumps(m, ensure_ascii=False, indent=1))
        self.dl.sources[f"GET {url}"] = Fetched(url, gz, accessed, sha, False)
        return (text if stored else ""), m
