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


@pytest.mark.asyncio
async def test_modalities_uses_integration_api_and_filters_active_records():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            json=[
                {"id": 6, "nome": "Pregão - Eletrônico", "statusAtivo": True},
                {"id": 99, "nome": "Modalidade inativa", "statusAtivo": False},
            ],
        )

    client = PNCPClient(
        "https://pncp.gov.br/api/consulta",
        transport=httpx.MockTransport(handler),
    )
    result = await client.modalities()

    assert "pncp.gov.br/api/pncp/v1/modalidades" in captured["url"]
    assert "statusAtivo=true" in captured["url"]
    assert [item["id"] for item in result] == [6]


@pytest.mark.asyncio
async def test_modalities_rejects_unexpected_response_shape():
    client = PNCPClient(
        "https://pncp.gov.br/api/consulta",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"data": []})
        ),
    )
    with pytest.raises(PNCPError, match="formato inesperado"):
        await client.modalities()


@pytest.mark.asyncio
async def test_collect_all_published_sweeps_active_modalities_and_reports_failures():
    requested_modalities = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/v1/modalidades"):
            return httpx.Response(
                200,
                json=[
                    {"id": 6, "nome": "Pregão", "statusAtivo": True},
                    {"id": 8, "nome": "Concorrência", "statusAtivo": True},
                ],
            )
        modality = int(request.url.params["codigoModalidadeContratacao"])
        requested_modalities.append(modality)
        if modality == 8:
            return httpx.Response(503, json={"message": "temporariamente indisponível"})
        return httpx.Response(
            200,
            json={
                "data": [{"numeroControlePNCP": "PUB-6"}],
                "totalPaginas": 1,
            },
        )

    client = PNCPClient(
        "https://pncp.gov.br/api/consulta",
        transport=httpx.MockTransport(handler),
    )
    result = await client.collect_all_published(
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 16),
        page_size=10,
    )

    assert requested_modalities == [6, 8]
    assert result["modalities_discovered"] == 2
    assert result["modalities_completed"] == 1
    assert result["collection_complete"] is False
    assert [item["numeroControlePNCP"] for item in result["data"]] == ["PUB-6"]
    assert result["modality_results"][1]["error"]



@pytest.mark.asyncio
async def test_updated_contracts_uses_global_update_endpoint_and_national_scope():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"data": [], "totalPaginas": 1})

    client = PNCPClient(
        "https://pncp.gov.br/api/consulta",
        transport=httpx.MockTransport(handler),
    )
    result = await client.updated_contracts(
        start_date=date(2026, 11, 15),
        end_date=date(2026, 11, 16),
        modality_code=6,
        page=2,
        page_size=20,
    )

    assert result["totalPaginas"] == 1
    assert "/v1/contratacoes/atualizacao" in captured["url"]
    assert "dataInicial=20261115" in captured["url"]
    assert "dataFinal=20261116" in captured["url"]
    assert "codigoModalidadeContratacao=6" in captured["url"]
    assert "pagina=2" in captured["url"]
    assert "uf=" not in captured["url"]


@pytest.mark.asyncio
async def test_collect_updated_follows_pages_and_stops_at_reported_total():
    requested_pages = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["pagina"])
        requested_pages.append(page)
        return httpx.Response(
            200,
            json={
                "data": [{"numeroControlePNCP": f"UPD-{page}"}],
                "totalPaginas": 2,
            },
        )

    client = PNCPClient(
        "https://pncp.gov.br/api/consulta",
        transport=httpx.MockTransport(handler),
    )
    result = await client.collect_updated(
        start_date=date(2026, 11, 15),
        end_date=date(2026, 11, 16),
        modality_code=6,
        page_size=10,
    )

    assert requested_pages == [1, 2]
    assert [item["numeroControlePNCP"] for item in result["data"]] == ["UPD-1", "UPD-2"]
    assert result["collection_complete"] is True


@pytest.mark.asyncio
async def test_collect_all_updated_continues_after_modality_failure():
    requested_modalities = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/v1/modalidades"):
            return httpx.Response(
                200,
                json=[
                    {"id": 6, "nome": "Pregão", "statusAtivo": True},
                    {"id": 8, "nome": "Concorrência", "statusAtivo": True},
                ],
            )
        modality = int(request.url.params["codigoModalidadeContratacao"])
        requested_modalities.append(modality)
        if modality == 8:
            return httpx.Response(503, json={"message": "indisponível"})
        return httpx.Response(
            200,
            json={"data": [{"numeroControlePNCP": "UPD-6"}], "totalPaginas": 1},
        )

    client = PNCPClient(
        "https://pncp.gov.br/api/consulta",
        transport=httpx.MockTransport(handler),
    )
    result = await client.collect_all_updated(
        start_date=date(2026, 11, 15),
        end_date=date(2026, 11, 16),
        page_size=10,
    )

    assert requested_modalities == [6, 8]
    assert result["modalities_discovered"] == 2
    assert result["modalities_completed"] == 1
    assert result["collection_complete"] is False
    assert [item["numeroControlePNCP"] for item in result["data"]] == ["UPD-6"]
    assert result["modality_results"][1]["error"]
