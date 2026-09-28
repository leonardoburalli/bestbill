"""Deterministic ARERA Portale Offerte URL builder and downloader.

Files are published 22:30-23:05 UTC on day D-1 (see docs/arera-data.md);
if today's file (or the requested date's file) is missing, retry with
backoff and then fall back to D-1, D-2, D-3, tagging the effective date.
No network calls happen at import time or in the test suite (mocked).
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

BASE_URL = "https://www.ilportaleofferte.it/portaleOfferte/resources/opendata/csv"
INDICES_URL = (
    "https://www.ilportaleofferte.it/portaleOfferte/resources/cms/documents/"
    "5d6f1085b4d5f20821af55764e647671.csv"
)

MAX_FALLBACK_DAYS = 3
MAX_RETRIES = 3
BACKOFF_SECONDS = 1.0


class FetchError(RuntimeError):
    """All retries and fallback days were exhausted."""


@dataclass(frozen=True)
class FetchResult:
    path: Path
    effective_date: date


def _month_folder(d: date) -> str:
    # "month folder has no leading zero" (docs/arera-data.md)
    return f"{d.year}_{d.month}"


def mlibero_url(d: date) -> str:
    return (
        f"{BASE_URL}/offerteML/{_month_folder(d)}/PO_Offerte_E_MLIBERO_{d:%Y%m%d}.xml"
    )


def placet_url(d: date) -> str:
    return f"{BASE_URL}/offerte/{_month_folder(d)}/PO_Offerte_E_PLACET_{d:%Y%m%d}.csv"


def _download(
    url: str,
    *,
    opener: urllib.request.OpenerDirector | None = None,
    timeout: float = 30.0,
) -> bytes:
    open_url = opener.open if opener is not None else urllib.request.urlopen
    with open_url(url, timeout=timeout) as response:
        return response.read()  # type: ignore[no-any-return]


def _download_with_retries(
    url: str,
    *,
    max_retries: int = MAX_RETRIES,
    backoff_seconds: float = BACKOFF_SECONDS,
    sleep: Callable[[float], None] | None = None,
    opener: urllib.request.OpenerDirector | None = None,
) -> bytes | None:
    sleep_fn = sleep if sleep is not None else time.sleep
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            return _download(url, opener=opener)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < max_retries - 1:
                sleep_fn(backoff_seconds * (2**attempt))
    del last_error
    return None


def fetch_with_fallback(
    url_builder: Callable[[date], str],
    target: date,
    dest: Path,
    *,
    max_fallback_days: int = MAX_FALLBACK_DAYS,
    max_retries: int = MAX_RETRIES,
    backoff_seconds: float = BACKOFF_SECONDS,
    sleep: Callable[[float], None] | None = None,
    opener: urllib.request.OpenerDirector | None = None,
) -> FetchResult:
    """Try ``target``, then ``target - 1``, ... down to
    ``target - max_fallback_days``. Raises :class:`FetchError` if every day
    fails.
    """
    for offset in range(max_fallback_days + 1):
        day = target - timedelta(days=offset)
        url = url_builder(day)
        content = _download_with_retries(
            url,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
            sleep=sleep,
            opener=opener,
        )
        if content is not None:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
            return FetchResult(path=dest, effective_date=day)
    raise FetchError(
        f"could not fetch {url_builder.__name__} for {target} or the "
        f"{max_fallback_days} preceding days"
    )


def fetch_mlibero(
    target: date,
    dest: Path,
    *,
    max_fallback_days: int = MAX_FALLBACK_DAYS,
    max_retries: int = MAX_RETRIES,
    backoff_seconds: float = BACKOFF_SECONDS,
    sleep: Callable[[float], None] | None = None,
    opener: urllib.request.OpenerDirector | None = None,
) -> FetchResult:
    return fetch_with_fallback(
        mlibero_url,
        target,
        dest,
        max_fallback_days=max_fallback_days,
        max_retries=max_retries,
        backoff_seconds=backoff_seconds,
        sleep=sleep,
        opener=opener,
    )


def fetch_placet(
    target: date,
    dest: Path,
    *,
    max_fallback_days: int = MAX_FALLBACK_DAYS,
    max_retries: int = MAX_RETRIES,
    backoff_seconds: float = BACKOFF_SECONDS,
    sleep: Callable[[float], None] | None = None,
    opener: urllib.request.OpenerDirector | None = None,
) -> FetchResult:
    return fetch_with_fallback(
        placet_url,
        target,
        dest,
        max_fallback_days=max_fallback_days,
        max_retries=max_retries,
        backoff_seconds=backoff_seconds,
        sleep=sleep,
        opener=opener,
    )


def fetch_indices(dest: Path, *, timeout: float = 30.0) -> Path:
    """The indices file has a single, non-dated URL (no fallback needed)."""
    content = _download(INDICES_URL, timeout=timeout)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    return dest
