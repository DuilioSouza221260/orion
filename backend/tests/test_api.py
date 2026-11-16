from datetime import date
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from orion_api.main import app
from orion_api.pncp import PNCPError


async def request_api(path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


@pytest.mark.asyncio
async def test_open_opportunities_returns_source_and_raw_payload(monkeypatch: pytest.MonkeyPatch):
    async def open_proposals(**kwargs: Any) -> dict[str, Any]:
        assert kwargs == {
            "end_date": date(2026, 11, 16),
            "page": 1,
            "page_size": 50,
            "modality_code": None,
            "uf": None,
        }
        return {"data": [{"numeroControlePNCP": "PNCP-1"}], "totalRegistros": 1}

    monkeypatch.setattr(app.state, "pncp", SimpleNamespace(open_proposals=open_proposals), raising=False)

    response = await request_api("/api/v1/opportunities/open?end_date=2026-11-16")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "PNCP"
    assert body["raw"]["data"][0]["numeroControlePNCP"] == "PNCP-1"
    assert body["retrieved_at"]


@pytest.mark.asyncio
async def test_open_opportunities_maps_invalid_parameters_to_422(monkeypatch: pytest.MonkeyPatch):
    async def open_proposals(**kwargs: Any) -> dict[str, Any]:
        raise ValueError("Parâmetro inválido.")

    monkeypatch.setattr(app.state, "pncp", SimpleNamespace(open_proposals=open_proposals), raising=False)

    response = await request_api("/api/v1/opportunities/open?end_date=2026-11-16&page=0")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_open_opportunities_maps_pncp_failure_to_502(monkeypatch: pytest.MonkeyPatch):
    async def open_proposals(**kwargs: Any) -> dict[str, Any]:
        raise PNCPError("Serviço PNCP indisponível.")

    monkeypatch.setattr(app.state, "pncp", SimpleNamespace(open_proposals=open_proposals), raising=False)

    response = await request_api("/api/v1/opportunities/open?end_date=2026-11-16")

    assert response.status_code == 502
    assert response.json()["detail"] == "Serviço PNCP indisponível."


@pytest.mark.asyncio
async def test_published_opportunities_passes_filters_to_client(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, Any] = {}

    async def published(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"data": [], "totalRegistros": 0}

    monkeypatch.setattr(app.state, "pncp", SimpleNamespace(published=published), raising=False)

    response = await request_api(
        "/api/v1/opportunities/published"
        "?start_date=2026-11-01&end_date=2026-11-16&modality_code=6&uf=mg"
    )

    assert response.status_code == 200
    assert captured == {
        "start_date": date(2026, 11, 1),
        "end_date": date(2026, 11, 16),
        "modality_code": 6,
        "page": 1,
        "page_size": 50,
        "uf": "mg",
    }


@pytest.mark.asyncio
async def test_reference_modalities_returns_active_catalog(monkeypatch: pytest.MonkeyPatch):
    async def modalities(*, active_only: bool) -> list[dict[str, Any]]:
        assert active_only is True
        return [{"id": 6, "nome": "Pregão", "statusAtivo": True}]

    monkeypatch.setattr(app.state, "pncp", SimpleNamespace(modalities=modalities), raising=False)

    response = await request_api("/api/v1/reference/modalities")

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["data"][0]["id"] == 6
