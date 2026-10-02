"""Loads the catalogue snapshot: a local file (dev/tests) or the GitHub
release assets (production), kept fresh in the background.

The snapshot is read fully into memory (offers, PUN, meta) and the SQLite
file is closed straight away, so swapping in a new snapshot is just an
atomic file replace plus a reference assignment. On any failure the last
good snapshot keeps being served.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from bestbill.catalog.store import CatalogStore
from bestbill.core.models import Offer, PunSeries

log = logging.getLogger(__name__)

SQLITE_ASSET = "catalog.sqlite"
MANIFEST_ASSET = "manifest.json"
MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024
_TIMEOUT = httpx.Timeout(15.0, read=60.0)


class CatalogError(Exception):
    """A catalogue could not be fetched, verified or opened."""


@dataclass(frozen=True)
class CatalogSettings:
    catalog_path: Path | None = None
    repo: str = "leonardoburalli/bestbill"
    release_tag: str = "catalog-latest"
    github_token: str | None = None
    cache_dir: Path = Path(tempfile.gettempdir()) / "bestbill-catalog"
    refresh_hours: float = 6.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> CatalogSettings:
        e = os.environ if env is None else env
        defaults = cls()
        path = e.get("BESTBILL_CATALOG_PATH")
        return cls(
            catalog_path=Path(path) if path else None,
            repo=e.get("BESTBILL_REPO") or defaults.repo,
            release_tag=e.get("BESTBILL_RELEASE_TAG") or defaults.release_tag,
            github_token=e.get("GITHUB_TOKEN") or None,
            cache_dir=Path(e.get("BESTBILL_CACHE_DIR") or defaults.cache_dir),
            refresh_hours=float(e.get("BESTBILL_REFRESH_HOURS") or 6),
        )


@dataclass(frozen=True)
class CatalogSnapshot:
    offers: tuple[Offer, ...]
    pun: PunSeries
    snapshot_date: date
    attribution: str
    stats: dict[str, Any]
    manifest: dict[str, Any]

    def age_days(self, today: date | None = None) -> int:
        return ((today or date.today()) - self.snapshot_date).days


def load_snapshot(
    sqlite_path: Path, manifest_path: Path | None = None
) -> CatalogSnapshot:
    """Read a catalogue file fully into memory (read-only, then closed)."""
    try:
        with CatalogStore(sqlite_path) as store:
            meta = store.meta()
            snapshot_date = date.fromisoformat(meta["snapshot_date"])
            offers = tuple(store.offers(limit=1_000_000))
            pun = store.pun_series()
            stats = store.stats()
    except Exception as exc:  # sqlite3.Error, KeyError, ValueError, ...
        raise CatalogError(f"cannot open catalogue: {type(exc).__name__}") from exc
    manifest: dict[str, Any] = {}
    if manifest_path is not None and manifest_path.is_file():
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                manifest = loaded
        except (OSError, ValueError):
            log.warning("ignoring unreadable catalogue manifest")
    return CatalogSnapshot(
        offers=offers,
        pun=pun,
        snapshot_date=snapshot_date,
        attribution=meta.get("attribution", ""),
        stats=stats,
        manifest=manifest,
    )


def _parse_manifest(raw: bytes) -> dict[str, Any]:
    loaded = json.loads(raw)
    return loaded if isinstance(loaded, dict) else {}


class CatalogProvider:
    """Holds the current snapshot and refreshes it from the GitHub release."""

    def __init__(
        self,
        settings: CatalogSettings,
        *,
        client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        self.settings = settings
        self._client_factory = client_factory or (
            lambda: httpx.Client(timeout=_TIMEOUT, follow_redirects=True)
        )
        self._snapshot: CatalogSnapshot | None = None
        self._updated_at: str | None = None
        self._sha256: str | None = None
        self._lock = threading.Lock()

    @property
    def snapshot(self) -> CatalogSnapshot | None:
        return self._snapshot

    @property
    def is_remote(self) -> bool:
        return self.settings.catalog_path is None

    # -- startup ---------------------------------------------------------
    def load_initial(self) -> None:
        """Load the local catalogue, or the cached remote one if present."""
        try:
            if self.settings.catalog_path is not None:
                path = self.settings.catalog_path
                self._snapshot = load_snapshot(path, path.with_name(MANIFEST_ASSET))
                return
            cache = self.settings.cache_dir
            if (cache / SQLITE_ASSET).is_file():
                self._snapshot = load_snapshot(
                    cache / SQLITE_ASSET, cache / MANIFEST_ASSET
                )
                state = cache / "state.json"
                if state.is_file():
                    data = json.loads(state.read_text())
                    self._updated_at = data.get("updated_at") or None
                    self._sha256 = data.get("sqlite_sha256") or None
        except Exception as exc:
            log.warning("could not load the local catalogue: %s", exc)

    # -- remote refresh --------------------------------------------------
    def _headers(self, accept: str) -> dict[str, str]:
        headers = {"Accept": accept}
        if self.settings.github_token:
            headers["X-GitHub-Api-Version"] = "2022-11-28"
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        return headers

    def refresh(self) -> bool:
        """Fetch the release if its sqlite asset changed. Never raises; at
        most one refresh runs at a time. Returns True if a new snapshot was
        swapped in.
        """
        if not self.is_remote:
            return False
        if not self._lock.acquire(blocking=False):
            return False
        try:
            return self._refresh()
        except httpx.HTTPStatusError as exc:
            # Never log headers/tokens: only status and rate-limit hints.
            status = exc.response.status_code
            hint = ""
            if status in (403, 429):
                for name in ("Retry-After", "X-RateLimit-Reset"):
                    value = exc.response.headers.get(name)
                    if value:
                        hint += f" {name}={value[:40]}"
            log.warning(
                "catalogue refresh failed (HTTP %s%s); keeping the last good one",
                status,
                f";{hint}" if hint else "",
            )
            return False
        except Exception as exc:
            # Never log headers/tokens: only the exception type and message.
            log.warning(
                "catalogue refresh failed (%s: %s); keeping the last good one",
                type(exc).__name__,
                exc,
            )
            return False
        finally:
            self._lock.release()

    def _refresh(self) -> bool:
        with self._client_factory() as client:
            if self.settings.github_token:
                return self._refresh_api(client)
            return self._refresh_public(client)

    def _refresh_public(self, client: httpx.Client) -> bool:
        """Public repo: only github.com release download URLs (no REST API,
        so no 60 req/h unauthenticated quota); redirects are followed."""
        s = self.settings
        base = f"https://github.com/{s.repo}/releases/download/{s.release_tag}"
        manifest_bytes = self._download_bytes(client, f"{base}/{MANIFEST_ASSET}")
        manifest = _parse_manifest(manifest_bytes)
        sha = manifest.get("sqlite_sha256")
        if not sha:
            log.warning("catalogue manifest has no sqlite_sha256; cannot verify")
        elif self._snapshot is not None and sha == self._sha256:
            log.debug("catalogue unchanged (sha256 %s)", sha)
            return False
        return self._download_and_swap(
            client, f"{base}/{SQLITE_ASSET}", manifest, manifest_bytes, ""
        )

    def _refresh_api(self, client: httpx.Client) -> bool:
        """Private repo: GitHub REST API with the token."""
        s = self.settings
        resp = client.get(
            f"https://api.github.com/repos/{s.repo}/releases/tags/{s.release_tag}",
            headers=self._headers("application/vnd.github+json"),
        )
        resp.raise_for_status()
        assets = {a["name"]: a for a in resp.json().get("assets", [])}
        if SQLITE_ASSET not in assets:
            raise CatalogError(f"release has no {SQLITE_ASSET} asset")
        sqlite_asset = assets[SQLITE_ASSET]
        updated_at = str(sqlite_asset.get("updated_at", ""))
        if self._snapshot is not None and updated_at == self._updated_at:
            log.debug("catalogue unchanged (updated_at %s)", updated_at)
            return False

        manifest: dict[str, Any] = {}
        manifest_bytes = b""
        if MANIFEST_ASSET in assets:
            manifest_bytes = self._download_bytes(client, assets[MANIFEST_ASSET]["url"])
            manifest = _parse_manifest(manifest_bytes)
        sha = manifest.get("sqlite_sha256")
        if sha and self._snapshot is not None and sha == self._sha256:
            log.debug("catalogue unchanged (sha256 %s)", sha)
            self._updated_at = updated_at
            return False
        return self._download_and_swap(
            client, sqlite_asset["url"], manifest, manifest_bytes, updated_at
        )

    def _download_and_swap(
        self,
        client: httpx.Client,
        url: str,
        manifest: dict[str, Any],
        manifest_bytes: bytes,
        updated_at: str,
    ) -> bool:
        cache = self.settings.cache_dir
        cache.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=cache, suffix=".sqlite.part")
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as fh:
                digest = self._download_to(client, url, fh)
            expected = manifest.get("sqlite_sha256")
            if expected and digest != expected:
                raise CatalogError("sha256 mismatch on the downloaded catalogue")
            # Validate before swapping: it must open and hold the data.
            loaded = load_snapshot(tmp)
            if manifest_bytes:
                (cache / MANIFEST_ASSET).write_bytes(manifest_bytes)
            new_snapshot = CatalogSnapshot(
                offers=loaded.offers,
                pun=loaded.pun,
                snapshot_date=loaded.snapshot_date,
                attribution=loaded.attribution,
                stats=loaded.stats,
                manifest=manifest,
            )
            os.replace(tmp, cache / SQLITE_ASSET)
            (cache / "state.json").write_text(
                json.dumps({"sqlite_sha256": digest, "updated_at": updated_at}),
                encoding="utf-8",
            )
        finally:
            tmp.unlink(missing_ok=True)
        self._snapshot = new_snapshot
        self._sha256 = digest
        self._updated_at = updated_at or None
        log.info("catalogue refreshed (snapshot %s)", new_snapshot.snapshot_date)
        return True

    def _download_bytes(self, client: httpx.Client, url: str) -> bytes:
        resp = client.get(url, headers=self._headers("application/octet-stream"))
        resp.raise_for_status()
        return resp.content

    def _download_to(self, client: httpx.Client, url: str, fh: Any) -> str:
        digest = hashlib.sha256()
        size = 0
        with client.stream(
            "GET", url, headers=self._headers("application/octet-stream")
        ) as resp:
            resp.raise_for_status()
            for chunk in resp.iter_bytes():
                size += len(chunk)
                if size > MAX_DOWNLOAD_BYTES:
                    raise CatalogError("catalogue download too large")
                digest.update(chunk)
                fh.write(chunk)
        return digest.hexdigest()
