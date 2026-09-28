from datetime import date

import pytest

from bestbill.arera.fetch import (
    FetchError,
    fetch_with_fallback,
    mlibero_url,
    placet_url,
)


def test_mlibero_url_no_leading_zero_month():
    url = mlibero_url(date(2026, 9, 28))
    assert url == (
        "https://www.ilportaleofferte.it/portaleOfferte/resources/opendata/csv/"
        "offerteML/2026_9/PO_Offerte_E_MLIBERO_20260928.xml"
    )


def test_placet_url_zero_padded_day():
    url = placet_url(date(2026, 1, 5))
    assert url == (
        "https://www.ilportaleofferte.it/portaleOfferte/resources/opendata/csv/"
        "offerte/2026_1/PO_Offerte_E_PLACET_20260105.csv"
    )


class _FakeOpener:
    """Fails for every URL except one matching a specific date."""

    def __init__(self, succeeds_on: str):
        self.succeeds_on = succeeds_on
        self.calls: list[str] = []

    def open(self, url: str, timeout: float = 30.0):  # noqa: ARG002
        self.calls.append(url)
        if self.succeeds_on in url:
            return _FakeResponse(b"content")
        raise OSError("not found")


class _FakeResponse:
    def __init__(self, content: bytes):
        self._content = content

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def read(self) -> bytes:
        return self._content


def test_fetch_with_fallback_succeeds_immediately(tmp_path):
    opener = _FakeOpener(succeeds_on="20260928")
    result = fetch_with_fallback(
        mlibero_url,
        date(2026, 9, 28),
        tmp_path / "out.xml",
        opener=opener,
        sleep=lambda _: None,
    )
    assert result.effective_date == date(2026, 9, 28)
    assert result.path.read_bytes() == b"content"


def test_fetch_with_fallback_falls_back_to_previous_day(tmp_path):
    opener = _FakeOpener(succeeds_on="20260927")
    result = fetch_with_fallback(
        mlibero_url,
        date(2026, 9, 28),
        tmp_path / "out.xml",
        opener=opener,
        sleep=lambda _: None,
    )
    assert result.effective_date == date(2026, 9, 27)


def test_fetch_with_fallback_raises_after_exhausting_days(tmp_path):
    opener = _FakeOpener(succeeds_on="never")
    with pytest.raises(FetchError):
        fetch_with_fallback(
            mlibero_url,
            date(2026, 9, 28),
            tmp_path / "out.xml",
            opener=opener,
            sleep=lambda _: None,
            max_fallback_days=2,
            max_retries=1,
        )
    # target + 2 fallback days = 3 attempts
    assert len(opener.calls) == 3


def test_fetch_with_fallback_retries_before_falling_back(tmp_path):
    class FlakyOpener:
        def __init__(self):
            self.attempts = 0

        def open(self, url: str, timeout: float = 30.0):  # noqa: ARG002
            self.attempts += 1
            if self.attempts < 2:
                raise OSError("temporary")
            return _FakeResponse(b"ok")

    opener = FlakyOpener()
    result = fetch_with_fallback(
        mlibero_url,
        date(2026, 9, 28),
        tmp_path / "out.xml",
        opener=opener,
        sleep=lambda _: None,
        max_retries=3,
    )
    assert result.effective_date == date(2026, 9, 28)
    assert opener.attempts == 2
