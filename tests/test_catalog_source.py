"""The catalogue loader against a fully mocked GitHub API (no network)."""

from __future__ import annotations

import hashlib
import json
import logging
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from bestbill.api.catalog_source import (
    CatalogError,
    CatalogProvider,
    CatalogSettings,
    load_snapshot,
)
from bestbill.api.main import create_app
from bestbill.api.settings import Settings

API = "https://api.github.com/repos/o/r"


class FakeGitHub:
    """Serves one release with catalog.sqlite + manifest.json assets."""

    def __init__(self, sqlite: bytes, *, sha: str | None = "auto") -> None:
        self.sqlite = sqlite
        self.sha = hashlib.sha256(sqlite).hexdigest() if sha == "auto" else sha
        self.updated_at = "2026-09-29T10:00:00Z"
        self.fail_release = False
        self.requests: list[httpx.Request] = []

    def manifest(self) -> bytes:
        data = {"snapshot_date": "2026-09-29", "licence": "CC-BY-SA-4.0"}
        if self.sha is not None:
            data["sqlite_sha256"] = self.sha
        return json.dumps(data).encode()

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)
        if url == f"{API}/releases/tags/catalog-latest":
            if self.fail_release:
                return httpx.Response(502)
            return httpx.Response(
                200,
                json={
                    "assets": [
                        {
                            "name": "catalog.sqlite",
                            "url": f"{API}/releases/assets/1",
                            "updated_at": self.updated_at,
                        },
                        {
                            "name": "manifest.json",
                            "url": f"{API}/releases/assets/2",
                            "updated_at": self.updated_at,
                        },
                        {"name": "retailers.csv", "url": f"{API}/releases/assets/3"},
                    ]
                },
            )
        if url == f"{API}/releases/assets/1":
            assert request.headers["accept"] == "application/octet-stream"
            return httpx.Response(200, content=self.sqlite)
        if url == f"{API}/releases/assets/2":
            return httpx.Response(200, content=self.manifest())
        return httpx.Response(404)

    @property
    def downloads(self) -> int:
        return sum("/assets/" in str(r.url) for r in self.requests)

    def provider(self, tmp_path, *, token: str | None = None) -> CatalogProvider:
        settings = CatalogSettings(
            repo="o/r", github_token=token, cache_dir=tmp_path / "cache"
        )
        return CatalogProvider(
            settings,
            client_factory=lambda: httpx.Client(
                transport=httpx.MockTransport(self.handler)
            ),
        )


@pytest.fixture()
def sqlite_bytes(catalog_dir) -> bytes:
    return (catalog_dir / "catalog.sqlite").read_bytes()


def test_load_snapshot_reads_everything_and_closes(catalog_dir):
    snap = load_snapshot(catalog_dir / "catalog.sqlite", catalog_dir / "manifest.json")
    assert snap.offers and not snap.pun.is_empty
    assert snap.stats["included"] == len(snap.offers)
    assert snap.manifest["licence"] == "CC-BY-SA-4.0"
    assert snap.attribution


def test_load_snapshot_bad_file(tmp_path):
    bad = tmp_path / "bad.sqlite"
    bad.write_bytes(b"not a database")
    with pytest.raises(CatalogError):
        load_snapshot(bad)


def test_load_snapshot_ignores_broken_manifest(catalog_dir, tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{nope")
    snap = load_snapshot(catalog_dir / "catalog.sqlite", manifest)
    assert snap.manifest == {}


def test_refresh_downloads_verifies_and_caches(tmp_path, sqlite_bytes):
    gh = FakeGitHub(sqlite_bytes)
    provider = gh.provider(tmp_path)
    assert provider.snapshot is None
    assert provider.refresh() is True
    assert provider.snapshot is not None
    assert provider.snapshot.manifest["licence"] == "CC-BY-SA-4.0"
    assert (tmp_path / "cache" / "catalog.sqlite").read_bytes() == sqlite_bytes
    assert not list((tmp_path / "cache").glob("*.part"))

    # A new process starts from the cache, without touching the network.
    restarted = gh.provider(tmp_path)
    restarted.load_initial()
    assert restarted.snapshot is not None
    n = len(gh.requests)
    assert restarted.refresh() is False  # same updated_at
    assert len(gh.requests) == n + 1  # only the release lookup


def test_token_header_sent_only_when_set(tmp_path, sqlite_bytes):
    with_token = FakeGitHub(sqlite_bytes)
    with_token.provider(tmp_path / "a", token="s3cret").refresh()
    assert len(with_token.requests) == 3
    assert all(
        r.headers["authorization"] == "Bearer s3cret" for r in with_token.requests
    )
    without = FakeGitHub(sqlite_bytes)
    without.provider(tmp_path / "b").refresh()
    assert len(without.requests) == 3
    assert all("authorization" not in r.headers for r in without.requests)


def test_sha256_mismatch_is_rejected(tmp_path, sqlite_bytes, caplog):
    gh = FakeGitHub(sqlite_bytes, sha="0" * 64)
    provider = gh.provider(tmp_path, token="s3cret")
    with caplog.at_level(logging.WARNING):
        assert provider.refresh() is False
    assert provider.snapshot is None
    assert not (tmp_path / "cache" / "catalog.sqlite").exists()
    assert not list((tmp_path / "cache").glob("*.part"))
    assert "sha256 mismatch" in caplog.text
    assert "s3cret" not in caplog.text


def test_no_manifest_hash_still_validates_the_database(tmp_path):
    gh = FakeGitHub(b"garbage, not sqlite", sha=None)
    provider = gh.provider(tmp_path)
    assert provider.refresh() is False
    assert provider.snapshot is None


def test_keeps_last_good_catalog_on_failure(tmp_path, sqlite_bytes, caplog):
    gh = FakeGitHub(sqlite_bytes)
    provider = gh.provider(tmp_path)
    assert provider.refresh() is True
    good = provider.snapshot

    gh.updated_at = "2026-09-30T10:00:00Z"
    gh.fail_release = True
    with caplog.at_level(logging.WARNING):
        assert provider.refresh() is False
    assert provider.snapshot is good
    assert "keeping the last good one" in caplog.text

    # A bad new build is rejected too and the good one stays.
    gh.fail_release = False
    gh.sqlite = b"corrupt"
    gh.sha = hashlib.sha256(gh.sqlite).hexdigest()
    assert provider.refresh() is False
    assert provider.snapshot is good
    assert (tmp_path / "cache" / "catalog.sqlite").read_bytes() == sqlite_bytes


def test_refreshes_only_when_updated_at_changed(tmp_path, sqlite_bytes):
    gh = FakeGitHub(sqlite_bytes)
    provider = gh.provider(tmp_path)
    assert provider.refresh() is True
    assert gh.downloads == 2
    assert provider.refresh() is False
    assert gh.downloads == 2
    gh.updated_at = "2026-09-30T10:00:00Z"
    assert provider.refresh() is True
    assert gh.downloads == 4


def test_release_without_sqlite_asset(tmp_path, caplog):
    def handler(request):
        return httpx.Response(200, json={"assets": []})

    provider = CatalogProvider(
        CatalogSettings(repo="o/r", cache_dir=tmp_path),
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with caplog.at_level(logging.WARNING):
        assert provider.refresh() is False
    assert "no catalog.sqlite asset" in caplog.text


def test_download_size_cap(tmp_path, sqlite_bytes, monkeypatch):
    import bestbill.api.catalog_source as cs

    monkeypatch.setattr(cs, "MAX_DOWNLOAD_BYTES", 10)
    provider = FakeGitHub(sqlite_bytes).provider(tmp_path)
    assert provider.refresh() is False


def test_only_one_refresh_at_a_time(tmp_path, sqlite_bytes):
    gh = FakeGitHub(sqlite_bytes)
    provider = gh.provider(tmp_path)
    assert provider._lock.acquire(blocking=False)
    try:
        assert provider.refresh() is False
    finally:
        provider._lock.release()
    assert gh.requests == []


def test_local_path_takes_precedence_and_never_refreshes(catalog_dir):
    def handler(request):  # pragma: no cover - must not be called
        raise AssertionError("network used")

    provider = CatalogProvider(
        CatalogSettings(catalog_path=catalog_dir / "catalog.sqlite", repo="o/r"),
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )
    provider.load_initial()
    assert provider.snapshot is not None
    assert provider.refresh() is False


def test_load_initial_with_broken_local_file_starts_empty(tmp_path, caplog):
    bad = tmp_path / "c.sqlite"
    bad.write_bytes(b"nope")
    provider = CatalogProvider(CatalogSettings(catalog_path=bad))
    with caplog.at_level(logging.WARNING):
        provider.load_initial()
    assert provider.snapshot is None
    assert "could not load" in caplog.text


def test_app_starts_without_catalog_and_refreshes_in_background(tmp_path, sqlite_bytes):
    gh = FakeGitHub(sqlite_bytes)
    provider = gh.provider(tmp_path)
    app = create_app(Settings(), provider=provider)
    with TestClient(app) as client:
        deadline = time.monotonic() + 10
        body = client.get("/api/health").json()
        while not body["catalog_loaded"] and time.monotonic() < deadline:
            time.sleep(0.05)
            body = client.get("/api/health").json()
        assert body["catalog_loaded"] is True
        assert client.get("/api/catalog/meta").status_code == 200


def test_app_serves_503_while_remote_is_unreachable(tmp_path, sqlite_bytes):
    gh = FakeGitHub(sqlite_bytes)
    gh.fail_release = True
    with TestClient(create_app(Settings(), provider=gh.provider(tmp_path))) as client:
        time.sleep(0.2)
        assert client.get("/api/health").json()["catalog_loaded"] is False
        assert client.get("/api/offers").status_code == 503
