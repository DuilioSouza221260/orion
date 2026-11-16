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



@pytest.mark.asyncio
async def test_procurement_detail_endpoint_returns_pncp_record(monkeypatch: pytest.MonkeyPatch):
    async def contracting_detail(**kwargs: Any) -> dict[str, Any]:
        assert kwargs == {"cnpj": "10000000000003", "year": 2026, "sequence": 15}
        return {"numeroControlePNCP": "PNCP-DETAIL"}

    monkeypatch.setattr(
        app.state,
        "pncp",
        SimpleNamespace(contracting_detail=contracting_detail),
        raising=False,
    )

    response = await request_api("/api/v1/procurements/10000000000003/2026/15")

    assert response.status_code == 200
    assert response.json()["data"]["numeroControlePNCP"] == "PNCP-DETAIL"


@pytest.mark.asyncio
async def test_procurement_documents_endpoint_returns_document_metadata(
    monkeypatch: pytest.MonkeyPatch,
):
    async def contracting_documents(**kwargs: Any) -> list[dict[str, Any]]:
        assert kwargs == {"cnpj": "10000000000003", "year": 2026, "sequence": 15}
        return [{"sequencialDocumento": 3, "tipoDocumentoNome": "Edital"}]

    monkeypatch.setattr(
        app.state,
        "pncp",
        SimpleNamespace(contracting_documents=contracting_documents),
        raising=False,
    )

    response = await request_api(
        "/api/v1/procurements/10000000000003/2026/15/documents"
    )

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["documents"][0]["tipoDocumentoNome"] == "Edital"


@pytest.mark.asyncio
async def test_procurement_detail_endpoint_maps_invalid_reference_to_422(
    monkeypatch: pytest.MonkeyPatch,
):
    async def contracting_detail(**kwargs: Any) -> dict[str, Any]:
        raise ValueError("CNPJ inválido.")

    monkeypatch.setattr(
        app.state,
        "pncp",
        SimpleNamespace(contracting_detail=contracting_detail),
        raising=False,
    )

    response = await request_api("/api/v1/procurements/invalid/2026/15")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_procurement_document_content_returns_binary_with_integrity_headers(
    monkeypatch: pytest.MonkeyPatch,
):
    async def download_contracting_document(**kwargs: Any) -> tuple[bytes, str]:
        assert kwargs == {
            "cnpj": "10000000000003",
            "year": 2026,
            "sequence": 15,
            "document_sequence": 3,
            "max_bytes": 26214400,
        }
        return b"%PDF-1.7 sample", "application/pdf"

    monkeypatch.setattr(
        app.state,
        "pncp",
        SimpleNamespace(download_contracting_document=download_contracting_document),
        raising=False,
    )

    response = await request_api(
        "/api/v1/procurements/10000000000003/2026/15/documents/3/content"
    )

    import hashlib

    assert response.status_code == 200
    assert response.content == b"%PDF-1.7 sample"
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["x-content-sha256"] == hashlib.sha256(response.content).hexdigest()
    assert response.headers["x-document-source"] == "PNCP"


@pytest.mark.asyncio
async def test_procurement_document_content_maps_size_limit_to_413(
    monkeypatch: pytest.MonkeyPatch,
):
    async def download_contracting_document(**kwargs: Any) -> tuple[bytes, str]:
        raise PNCPError("Documento excede o limite de 100 bytes.")

    monkeypatch.setattr(
        app.state,
        "pncp",
        SimpleNamespace(download_contracting_document=download_contracting_document),
        raising=False,
    )

    response = await request_api(
        "/api/v1/procurements/10000000000003/2026/15/documents/3/content"
    )

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_opportunity_version_history_endpoint_returns_paginated_versions(
    monkeypatch: pytest.MonkeyPatch,
):
    from datetime import UTC, datetime

    from orion_api import main

    now = datetime(2026, 11, 16, tzinfo=UTC)
    opportunity = SimpleNamespace(
        id=9, source="PNCP", external_id="10000000000003-2026-15",
        first_seen_at=now, last_seen_at=now,
    )
    version = SimpleNamespace(
        id=12, payload_hash="a" * 64, source_endpoint="pncp:publicacao",
        observed_at=now, raw_payload={"situacao": "aberta"},
    )

    class FakeResult:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

        def scalar_one(self):
            return self.value

        def scalars(self):
            return self

        def all(self):
            return self.value

    class FakeSession:
        def __init__(self):
            self.calls = 0

        async def execute(self, statement):
            self.calls += 1
            return [
                FakeResult(opportunity), FakeResult(1), FakeResult([version])
            ][self.calls - 1]

    class SessionContext:
        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, *args):
            return None

    monkeypatch.setattr(main, "require_session_factory", lambda: lambda: SessionContext())
    response = await request_api(
        "/api/v1/opportunities/10000000000003-2026-15/versions?page=1&page_size=10"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"] == {"page": 1, "page_size": 10, "total": 1, "pages": 1}
    assert body["versions"][0]["source_endpoint"] == "pncp:publicacao"
    assert body["versions"][0]["payload"]["situacao"] == "aberta"


@pytest.mark.asyncio
async def test_opportunity_version_history_endpoint_returns_404_when_missing(
    monkeypatch: pytest.MonkeyPatch,
):
    from orion_api import main

    class FakeResult:
        def scalar_one_or_none(self):
            return None

    class FakeSession:
        async def execute(self, statement):
            return FakeResult()

    class SessionContext:
        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, *args):
            return None

    monkeypatch.setattr(main, "require_session_factory", lambda: lambda: SessionContext())
    response = await request_api("/api/v1/opportunities/unknown/versions")
    assert response.status_code == 404



@pytest.mark.asyncio
async def test_document_asset_version_history_endpoint_returns_paginated_versions(
    monkeypatch: pytest.MonkeyPatch,
):
    from datetime import UTC, datetime

    from orion_api import main

    now = datetime(2026, 11, 16, tzinfo=UTC)
    history = {
        "document": {
            "id": 7,
            "source": "PNCP",
            "external_id": "10000000000003-2026-15",
            "document_sequence": 3,
            "status": "present",
            "first_seen_at": now.isoformat(),
            "last_seen_at": now.isoformat(),
        },
        "pagination": {"page": 1, "page_size": 10, "total": 2, "pages": 1},
        "versions": [
            {
                "id": 15,
                "sha256": "a" * 64,
                "filename": "edital.pdf",
                "content_type": "application/pdf",
                "byte_size": 120,
                "storage_backend": "s3",
                "storage_key": "sha256/aa/" + "a" * 64,
                "status": "present",
                "observed_at": now.isoformat(),
            }
        ],
    }

    class FakeSession:
        pass

    class SessionContext:
        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, *args):
            return None

    async def fake_history(session, **kwargs):
        assert kwargs == {
            "external_id": "10000000000003-2026-15",
            "document_sequence": 3,
            "page": 1,
            "page_size": 10,
        }
        return history

    monkeypatch.setattr(main, "require_session_factory", lambda: lambda: SessionContext())
    monkeypatch.setattr(main, "get_document_asset_versions", fake_history)

    response = await request_api(
        "/api/v1/procurements/10000000000003-2026-15/documents/3/versions"
        "?page=1&page_size=10"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "ORION"
    assert body["pagination"]["total"] == 2
    assert body["versions"][0]["sha256"] == "a" * 64
    assert body["versions"][0]["status"] == "present"


@pytest.mark.asyncio
async def test_document_asset_version_history_endpoint_returns_404_when_missing(
    monkeypatch: pytest.MonkeyPatch,
):
    from orion_api import main

    class FakeSession:
        pass

    class SessionContext:
        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, *args):
            return None

    async def missing_history(session, **kwargs):
        return None

    monkeypatch.setattr(main, "require_session_factory", lambda: lambda: SessionContext())
    monkeypatch.setattr(main, "get_document_asset_versions", missing_history)

    response = await request_api(
        "/api/v1/procurements/unknown/documents/1/versions"
    )
    assert response.status_code == 404
