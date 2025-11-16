from __future__ import annotations

import types

import pytest

from acb.monitoring.http import check_http_client_health, check_http_connectivity


class DummyResponse:
    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code

    def json(self) -> dict[str, str]:  # pragma: no cover - not used here
        return {"ok": "true"}


class DummyRequests:
    async def get(self, url: str, timeout: int = 5, **_: object) -> DummyResponse:  # noqa: ARG002
        return DummyResponse(status_code=200)


def _install_dummy_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "acb.monitoring.http.import_adapter",
        lambda category=None: types.SimpleNamespace(),  # noqa: ARG005
        raising=True,
    )
    monkeypatch.setattr(
        "acb.monitoring.http.depends.get_sync",
        lambda _adapter: DummyRequests(),  # noqa: ARG005
        raising=True,
    )


@pytest.mark.asyncio
async def test_check_http_client_health_without_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_dummy_adapter(monkeypatch)
    result = await check_http_client_health(test_url=None)
    assert result.status.value in ("healthy", "degraded")
    assert "initialized" in (result.message or "").lower()


@pytest.mark.asyncio
async def test_check_http_connectivity_success(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_dummy_adapter(monkeypatch)
    result = await check_http_connectivity(
        url="https://example.com/health", expected_status=200
    )
    assert result.status.value == "healthy"
    assert "connectivity test successful" in (result.message or "").lower()
