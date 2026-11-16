from datetime import date
from typing import Any

import httpx


class PNCPError(RuntimeError):
    """Erro de comunicação ou resposta inválida do PNCP."""


class PNCPClient:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 25.0,
        max_page_size: int = 50,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_page_size = max_page_size
        self.transport = transport

    def _validate_common(self, page: int, page_size: int) -> None:
        if page < 1:
            raise ValueError("A página deve ser maior ou igual a 1.")
        if not 10 <= page_size <= self.max_page_size:
            raise ValueError(f"O tamanho da página deve estar entre 10 e {self.max_page_size}.")

    @staticmethod
    def _date_param(value: date) -> str:
        return value.strftime("%Y%m%d")

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
                headers={"Accept": "application/json", "User-Agent": "ORION/0.1"},
            ) as client:
                response = await client.get(path, params=params)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise PNCPError(f"Falha na consulta ao PNCP: {exc}") from exc

        if not isinstance(payload, dict):
            raise PNCPError("O PNCP retornou um formato JSON inesperado.")
        return payload

    async def open_proposals(
        self,
        *,
        end_date: date,
        page: int = 1,
        page_size: int = 50,
        modality_code: int | None = None,
        uf: str | None = None,
    ) -> dict[str, Any]:
        self._validate_common(page, page_size)
        params: dict[str, Any] = {
            "dataFinal": self._date_param(end_date),
            "pagina": page,
            "tamanhoPagina": page_size,
        }
        if modality_code is not None:
            params["codigoModalidadeContratacao"] = modality_code
        if uf:
            params["uf"] = uf.upper()
        return await self._get("/v1/contratacoes/proposta", params)

    async def published(
        self,
        *,
        start_date: date,
        end_date: date,
        modality_code: int,
        page: int = 1,
        page_size: int = 50,
        uf: str | None = None,
    ) -> dict[str, Any]:
        self._validate_common(page, page_size)
        if start_date > end_date:
            raise ValueError("A data inicial não pode ser posterior à data final.")
        params: dict[str, Any] = {
            "dataInicial": self._date_param(start_date),
            "dataFinal": self._date_param(end_date),
            "codigoModalidadeContratacao": modality_code,
            "pagina": page,
            "tamanhoPagina": page_size,
        }
        if uf:
            params["uf"] = uf.upper()
        return await self._get("/v1/contratacoes/publicacao", params)
