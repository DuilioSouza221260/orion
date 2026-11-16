from datetime import date

import httpx
import pytest

from orion_api.pncp import PNCPClient


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
