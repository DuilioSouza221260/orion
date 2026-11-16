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
        domain_base_url: str = "https://pncp.gov.br/api/pncp",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.domain_base_url = domain_base_url.rstrip("/")
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

    async def modalities(self, *, active_only: bool = True) -> list[dict[str, Any]]:
        """Return PNCP contracting modalities from the integration API, not the query API."""
        params = {"statusAtivo": "true"} if active_only else {}
        try:
            async with httpx.AsyncClient(
                base_url=self.domain_base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
                headers={"Accept": "application/json", "User-Agent": "ORION/0.1"},
            ) as client:
                response = await client.get("/v1/modalidades", params=params)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise PNCPError(f"Falha ao consultar modalidades do PNCP: {exc}") from exc

        if not isinstance(payload, list):
            raise PNCPError("O PNCP retornou o catálogo de modalidades em formato inesperado.")

        modalities: list[dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, dict):
                raise PNCPError("O PNCP retornou uma modalidade em formato inválido.")
            modality_id = item.get("id")
            name = item.get("nome")
            if isinstance(modality_id, bool) or not isinstance(modality_id, int) or modality_id < 1:
                raise PNCPError("O PNCP retornou uma modalidade sem identificador válido.")
            if not isinstance(name, str) or not name.strip():
                raise PNCPError("O PNCP retornou uma modalidade sem nome válido.")
            if active_only and item.get("statusAtivo") is False:
                continue
            modalities.append(item)

        return modalities

    async def collect_all_published(
        self,
        *,
        start_date: date,
        end_date: date,
        page_size: int = 50,
        uf: str | None = None,
        max_pages_per_modality: int = 100,
    ) -> dict[str, Any]:
        """Sweep publication records across every active modality; report partial failures."""
        active_modalities = await self.modalities(active_only=True)
        if not active_modalities:
            raise PNCPError("O catálogo do PNCP não retornou modalidades ativas.")

        records: list[dict[str, Any]] = []
        results: list[dict[str, Any]] = []
        for modality in active_modalities:
            modality_id = modality["id"]
            try:
                collection = await self.collect_published(
                    start_date=start_date,
                    end_date=end_date,
                    modality_code=modality_id,
                    page_size=page_size,
                    uf=uf,
                    max_pages=max_pages_per_modality,
                )
                records.extend(collection["data"])
                results.append({
                    "modality_id": modality_id,
                    "modality_name": modality["nome"],
                    "pages_collected": collection["pages_collected"],
                    "source_total_pages": collection["source_total_pages"],
                    "collection_complete": collection["collection_complete"],
                    "error": None,
                })
            except (PNCPError, ValueError) as exc:
                results.append({
                    "modality_id": modality_id,
                    "modality_name": modality["nome"],
                    "pages_collected": 0,
                    "source_total_pages": None,
                    "collection_complete": False,
                    "error": str(exc),
                })

        return {
            "data": records,
            "modalities_discovered": len(active_modalities),
            "modalities_completed": sum(1 for item in results if item["collection_complete"]),
            "collection_complete": all(item["collection_complete"] for item in results),
            "modality_results": results,
        }

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

    async def collect_open_proposals(
        self,
        *,
        end_date: date,
        page_size: int = 50,
        modality_code: int | None = None,
        uf: str | None = None,
        max_pages: int = 100,
    ) -> dict[str, Any]:
        """Collect pages with a hard safety ceiling; preserve source pagination metadata."""
        if max_pages < 1:
            raise ValueError("O limite máximo de páginas deve ser maior ou igual a 1.")

        records: list[dict[str, Any]] = []
        page = 1
        pages_collected = 0
        total_pages: int | None = None
        collection_complete = False

        while page <= max_pages:
            payload = await self.open_proposals(
                end_date=end_date,
                page=page,
                page_size=page_size,
                modality_code=modality_code,
                uf=uf,
            )
            pages_collected += 1
            page_records = payload.get("data", [])
            if not isinstance(page_records, list):
                raise PNCPError("O PNCP retornou uma lista de oportunidades em formato inválido.")
            records.extend(item for item in page_records if isinstance(item, dict))

            reported_pages = payload.get("totalPaginas")
            if isinstance(reported_pages, int) and not isinstance(reported_pages, bool):
                if reported_pages < 1:
                    raise PNCPError("O PNCP informou uma quantidade inválida de páginas.")
                total_pages = max(total_pages or reported_pages, reported_pages)

            if total_pages is not None and page >= total_pages:
                collection_complete = True
                break
            if not page_records:
                collection_complete = total_pages is None
                break
            page += 1

        return {
            "data": records,
            "pages_collected": pages_collected,
            "source_total_pages": total_pages,
            "collection_complete": collection_complete,
        }

    async def collect_published(
        self,
        *,
        start_date: date,
        end_date: date,
        modality_code: int,
        page_size: int = 50,
        uf: str | None = None,
        max_pages: int = 100,
    ) -> dict[str, Any]:
        """Collect publication pages for one modality with a hard safety ceiling."""
        if max_pages < 1:
            raise ValueError("O limite máximo de páginas deve ser maior ou igual a 1.")
        if start_date > end_date:
            raise ValueError("A data inicial não pode ser posterior à data final.")

        records: list[dict[str, Any]] = []
        total_pages: int | None = None
        collection_complete = False
        pages_collected = 0

        for page in range(1, max_pages + 1):
            payload = await self.published(
                start_date=start_date,
                end_date=end_date,
                modality_code=modality_code,
                page=page,
                page_size=page_size,
                uf=uf,
            )
            pages_collected += 1
            page_records = payload.get("data", [])
            if not isinstance(page_records, list):
                raise PNCPError("O PNCP retornou uma lista de oportunidades em formato inválido.")
            records.extend(item for item in page_records if isinstance(item, dict))

            reported_pages = payload.get("totalPaginas")
            if isinstance(reported_pages, int) and not isinstance(reported_pages, bool):
                if reported_pages < 1:
                    raise PNCPError("O PNCP informou uma quantidade inválida de páginas.")
                total_pages = max(total_pages or reported_pages, reported_pages)

            if total_pages is not None and page >= total_pages:
                collection_complete = True
                break
            if not page_records:
                collection_complete = total_pages is None
                break

        return {
            "data": records,
            "pages_collected": pages_collected,
            "source_total_pages": total_pages,
            "collection_complete": collection_complete,
        }

    async def updated_contracts(
        self,
        *,
        start_date: date,
        end_date: date,
        modality_code: int,
        page: int = 1,
        page_size: int = 50,
        uf: str | None = None,
    ) -> dict[str, Any]:
        """Return contracts changed globally in the requested interval."""
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
        return await self._get("/v1/contratacoes/atualizacao", params)

    async def collect_updated(
        self,
        *,
        start_date: date,
        end_date: date,
        modality_code: int,
        page_size: int = 50,
        uf: str | None = None,
        max_pages: int = 100,
    ) -> dict[str, Any]:
        """Collect globally updated contracts for one modality."""
        if max_pages < 1:
            raise ValueError("O limite máximo de páginas deve ser maior ou igual a 1.")
        if start_date > end_date:
            raise ValueError("A data inicial não pode ser posterior à data final.")

        records: list[dict[str, Any]] = []
        total_pages: int | None = None
        pages_collected = 0
        collection_complete = False

        for page in range(1, max_pages + 1):
            payload = await self.updated_contracts(
                start_date=start_date,
                end_date=end_date,
                modality_code=modality_code,
                page=page,
                page_size=page_size,
                uf=uf,
            )
            pages_collected += 1
            page_records = payload.get("data", [])
            if not isinstance(page_records, list):
                raise PNCPError("O PNCP retornou uma lista de oportunidades em formato inválido.")
            records.extend(item for item in page_records if isinstance(item, dict))

            reported_pages = payload.get("totalPaginas")
            if isinstance(reported_pages, int) and not isinstance(reported_pages, bool):
                if reported_pages < 1:
                    raise PNCPError("O PNCP informou uma quantidade inválida de páginas.")
                total_pages = max(total_pages or reported_pages, reported_pages)

            if total_pages is not None and page >= total_pages:
                collection_complete = True
                break
            if not page_records:
                collection_complete = total_pages is None
                break

        return {
            "data": records,
            "pages_collected": pages_collected,
            "source_total_pages": total_pages,
            "collection_complete": collection_complete,
        }

    async def collect_all_updated(
        self,
        *,
        start_date: date,
        end_date: date,
        page_size: int = 50,
        uf: str | None = None,
        max_pages_per_modality: int = 100,
    ) -> dict[str, Any]:
        """Sweep globally updated contracts across all active modalities."""
        active_modalities = await self.modalities(active_only=True)
        if not active_modalities:
            raise PNCPError("O catálogo do PNCP não retornou modalidades ativas.")

        records: list[dict[str, Any]] = []
        results: list[dict[str, Any]] = []
        for modality in active_modalities:
            modality_id = modality["id"]
            try:
                collection = await self.collect_updated(
                    start_date=start_date,
                    end_date=end_date,
                    modality_code=modality_id,
                    page_size=page_size,
                    uf=uf,
                    max_pages=max_pages_per_modality,
                )
                records.extend(collection["data"])
                results.append({
                    "modality_id": modality_id,
                    "modality_name": modality["nome"],
                    "pages_collected": collection["pages_collected"],
                    "source_total_pages": collection["source_total_pages"],
                    "collection_complete": collection["collection_complete"],
                    "error": None,
                })
            except (PNCPError, ValueError) as exc:
                results.append({
                    "modality_id": modality_id,
                    "modality_name": modality["nome"],
                    "pages_collected": 0,
                    "source_total_pages": None,
                    "collection_complete": False,
                    "error": str(exc),
                })

        return {
            "data": records,
            "modalities_discovered": len(active_modalities),
            "modalities_completed": sum(1 for item in results if item["collection_complete"]),
            "collection_complete": all(item["collection_complete"] for item in results),
            "modality_results": results,
        }

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
