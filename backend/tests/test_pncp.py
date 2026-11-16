from datetime import date

import httpx
import pytest

from orion_api.pncp import PNCPClient, PNCPError


@pytest.mark.asyncio
async def test_open_proposals_builds_national_query():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"data": [], "totalRegistros": 0})

    client = PNCPClient(
        "https://pncp.gov.br/api/consulta",
        transport=httpx.MockTransport(handler),
    )
    result = await client.open_proposals(end_date=date(2026, 11, 16), page=2, page_size=20)

    assert result["totalRegistros"] == 0
    assert "/v1/contratacoes/proposta" in captured["url"]
    assert "dataFinal=20261116" in captured["url"]
    assert "pagina=2" in captured["url"]
    assert "uf=" not in captured["url"]


@pytest.mark.asyncio
async def test_published_requires_valid_date_range():
    client = PNCPClient("https://pncp.gov.br/api/consulta")
    with pytest.raises(ValueError, match="data inicial"):
        await client.published(
            start_date=date(2026, 11, 17),
            end_date=date(2026, 11, 16),
            modality_code=6,
        )


@pytest.mark.asyncio
async def test_page_size_is_validated():
    client = PNCPClient("https://pncp.gov.br/api/consulta")
    with pytest.raises(ValueError, match="tamanho da página"):
        await client.open_proposals(end_date=date(2026, 11, 16), page_size=5)


@pytest.mark.asyncio
async def test_collect_open_proposals_follows_reported_pages():
    requested_pages = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["pagina"])
        requested_pages.append(page)
        return httpx.Response(
            200,
            json={
                "data": [{"numeroControlePNCP": f"ID-{page}"}],
                "totalPaginas": 2,
                "totalRegistros": 2,
            },
        )

    client = PNCPClient(
        "https://pncp.gov.br/api/consulta",
        transport=httpx.MockTransport(handler),
    )
    result = await client.collect_open_proposals(
        end_date=date(2026, 11, 16),
        page_size=10,
    )

    assert requested_pages == [1, 2]
    assert [item["numeroControlePNCP"] for item in result["data"]] == ["ID-1", "ID-2"]
    assert result["collection_complete"] is True


@pytest.mark.asyncio
async def test_collect_open_proposals_stops_at_safety_ceiling():
    requested_pages = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["pagina"])
        requested_pages.append(page)
        return httpx.Response(
            200,
            json={"data": [{"numeroControlePNCP": f"ID-{page}"}], "totalPaginas": 99},
        )

    client = PNCPClient(
        "https://pncp.gov.br/api/consulta",
        transport=httpx.MockTransport(handler),
    )
    result = await client.collect_open_proposals(
        end_date=date(2026, 11, 16),
        page_size=10,
        max_pages=2,
    )

    assert requested_pages == [1, 2]
    assert result["collection_complete"] is False


@pytest.mark.asyncio
async def test_collect_open_proposals_rejects_zero_reported_pages():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [], "totalPaginas": 0})

    client = PNCPClient(
        "https://pncp.gov.br/api/consulta",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(PNCPError, match="quantidade inválida de páginas"):
        await client.collect_open_proposals(end_date=date(2026, 11, 16), page_size=10)


@pytest.mark.asyncio
async def test_collect_open_proposals_marks_empty_page_as_complete_without_metadata():
    requested_pages = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["pagina"])
        requested_pages.append(page)
        records = [{"numeroControlePNCP": "ID-1"}] if page == 1 else []
        return httpx.Response(200, json={"data": records})

    client = PNCPClient(
        "https://pncp.gov.br/api/consulta",
        transport=httpx.MockTransport(handler),
    )
    result = await client.collect_open_proposals(
        end_date=date(2026, 11, 16),
        page_size=10,
    )

    assert requested_pages == [1, 2]
    assert result["collection_complete"] is True


@pytest.mark.asyncio
async def test_collect_published_follows_pages_for_requested_modality():
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["pagina"])
        requested.append((page, request.url.params["codigoModalidadeContratacao"]))
        return httpx.Response(
            200,
            json={
                "data": [{"numeroControlePNCP": f"PUB-{page}"}],
                "totalPaginas": 2,
            },
        )

    client = PNCPClient(
        "https://pncp.gov.br/api/consulta",
        transport=httpx.MockTransport(handler),
    )
    result = await client.collect_published(
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 16),
        modality_code=6,
        page_size=10,
    )

    assert requested == [(1, "6"), (2, "6")]
    assert [item["numeroControlePNCP"] for item in result["data"]] == ["PUB-1", "PUB-2"]
    assert result["collection_complete"] is True


@pytest.mark.asyncio
async def test_collect_published_reports_incomplete_at_safety_ceiling():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"numeroControlePNCP": "PUB-1"}], "totalPaginas": 5},
        )

    client = PNCPClient(
        "https://pncp.gov.br/api/consulta",
        transport=httpx.MockTransport(handler),
    )
    result = await client.collect_published(
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 16),
        modality_code=6,
        page_size=10,
        max_pages=2,
    )

    assert result["pages_collected"] == 2
    assert result["source_total_pages"] == 5
    assert result["collection_complete"] is False
