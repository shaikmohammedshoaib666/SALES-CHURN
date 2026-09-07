"""URL ingest (Forge v2 slice): Google Drive, Kaggle, HTTPS, Dropbox → a fetchable path."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import requests

_GDRIVE_ID_PATTERNS = (
    re.compile(r"drive\.google\.com/file/d/([^/?#]+)"),
    re.compile(r"drive\.google\.com/open\?[^#]*\bid=([^&#]+)"),
    re.compile(r"drive\.google\.com/uc\?(?:export=download&)?[^#]*\bid=([^&#]+)"),
    re.compile(r"docs\.google\.com/spreadsheets/d/([^/?#]+)"),
)
_KAGGLE_PAGE = re.compile(r"kaggle\.com/(?:datasets|competitions)/([^/?#]+/[^/?#]+)")
_KAGGLE_SCHEME = re.compile(r"^kaggle://([^/]+/[^/]+)(?:/(.+))?$", re.I)

MAX_DOWNLOAD_BYTES = 3 * 1024 * 1024 * 1024  # 3 GiB ceiling
_REQUEST_HEADERS = {"User-Agent": "Keel-CustomerTwin/1.0 (+https://github.com/shaikmohammedshoaib666/SALES-CHURN)"}


def looks_like_zip(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith(".zip") or ".zip?" in (url or "").lower()


def detect_source_kind(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return "empty"
    if _KAGGLE_SCHEME.match(u):
        return "kaggle_api"
    if "drive.google.com" in u or "docs.google.com/spreadsheets" in u:
        return "google_drive"
    if "kaggle.com" in u:
        return "kaggle_page"
    return "https"


def extract_gdrive_file_id(url: str) -> Optional[str]:
    for pat in _GDRIVE_ID_PATTERNS:
        m = pat.search(url)
        if m:
            return m.group(1)
    return None


def extract_kaggle_slug(url: str) -> Optional[str]:
    m = _KAGGLE_PAGE.search(url)
    return m.group(1) if m else None


def resolve_gdrive_download_url(file_id: str, session: Optional[requests.Session] = None) -> str:
    sess = session or requests.Session()
    base = f"https://drive.google.com/uc?export=download&id={file_id}"
    resp = sess.get(base, headers=_REQUEST_HEADERS, stream=True, timeout=60, allow_redirects=True)
    resp.raise_for_status()
    for key, value in resp.cookies.items():
        if key.startswith("download_warning"):
            return f"{base}&confirm={value}"
    if "text/html" in (resp.headers.get("content-type") or "").lower():
        m = re.search(r"confirm=([0-9A-Za-z_]+)", resp.text[:8000])
        if m:
            return f"{base}&confirm={m.group(1)}"
    return base


def _kaggle_file(owner_dataset: str, filename: Optional[str] = None) -> Path:
    user = (os.getenv("KAGGLE_USERNAME") or "").strip()
    key = (os.getenv("KAGGLE_KEY") or "").strip()
    if not user or not key:
        raise RuntimeError(
            "Kaggle page links need secrets KAGGLE_USERNAME and KAGGLE_KEY "
            "(https://www.kaggle.com/settings → API). Or paste a direct file URL."
        )
    from kaggle.api.kaggle_api_extended import KaggleApi

    owner, _, dataset = owner_dataset.partition("/")
    tmp_dir = Path(tempfile.mkdtemp(prefix="keel-kaggle-"))
    api = KaggleApi()
    api.authenticate()
    if filename:
        api.dataset_download_file(f"{owner}/{dataset}", filename, path=str(tmp_dir), quiet=True)
    else:
        api.dataset_download_files(f"{owner}/{dataset}", path=str(tmp_dir), quiet=True, unzip=True)
    candidates = [p for p in tmp_dir.rglob("*") if p.is_file()]
    if not candidates:
        raise RuntimeError("Kaggle download returned no files.")
    prefer = {".csv", ".tsv", ".parquet", ".zip"}
    candidates.sort(key=lambda p: (0 if p.suffix.lower() in prefer else 1, p.name))
    return candidates[0]


def download_to_temp(url: str, suffix: str = "") -> Path:
    sess = requests.Session()
    resp = sess.get(url, headers=_REQUEST_HEADERS, stream=True, timeout=120, allow_redirects=True)
    resp.raise_for_status()
    parsed = urlparse(url)
    ext = Path(parsed.path).suffix or suffix or ".bin"
    dest = Path(tempfile.mkstemp(prefix="keel-url-", suffix=ext)[1])
    written = 0
    with dest.open("wb") as fh:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            written += len(chunk)
            if written > MAX_DOWNLOAD_BYTES:
                fh.close()
                dest.unlink(missing_ok=True)
                raise RuntimeError("Download exceeded 3 GB cap. Slice on the source or use a smaller extract.")
            fh.write(chunk)
    return dest


def resolve_source(url: str) -> tuple[str, dict[str, Any]]:
    raw = (url or "").strip()
    if not raw:
        raise ValueError("Paste a URL first.")
    meta: dict[str, Any] = {"original_url": raw, "kind": detect_source_kind(raw)}

    m = _KAGGLE_SCHEME.match(raw)
    if m:
        path = str(_kaggle_file(m.group(1), m.group(2)))
        meta["resolved"] = path
        meta["local"] = True
        return path, meta
    if meta["kind"] == "kaggle_page":
        slug = extract_kaggle_slug(raw)
        if not slug:
            raise ValueError("Could not parse Kaggle dataset slug.")
        path = str(_kaggle_file(slug))
        meta["resolved"] = path
        meta["local"] = True
        return path, meta
    if meta["kind"] == "google_drive":
        file_id = extract_gdrive_file_id(raw)
        if not file_id:
            raise ValueError("Could not parse Google Drive file id.")
        resolved = resolve_gdrive_download_url(file_id)
        local = str(download_to_temp(resolved, suffix=".bin"))
        meta["resolved"] = local
        meta["local"] = True
        return local, meta
    if "dropbox.com" in raw and "dl=0" in raw:
        raw = raw.replace("dl=0", "dl=1")
    # ZIP cannot be sliced by DuckDB httpfs — fetch locally, then extract.
    if looks_like_zip(raw):
        local = str(download_to_temp(raw, suffix=".zip"))
        meta["resolved"] = local
        meta["local"] = True
        return local, meta
    meta["resolved"] = raw
    meta["local"] = False
    return raw, meta
