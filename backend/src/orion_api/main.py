import hashlib
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Response

from orion_api.config import settings
from orion_api.db import require_session_factory
from orion_api.pncp import PNCPClient, PNCPError
from orion_api.repository import (\n    get_document_asset_versions,\n    get_document_sync_operation,\n    get_opportunity_versions,\n    list_document_sync_operations,\n)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pncp = PNCPClient(
        base_url=settings.pncp_base_url,
        timeout_seconds=settings.pncp_timeout_seconds,
        max_page_size=settings.pncp_max_page_size,
        domain_base_url=settings.pncp_domain_base_url,
    )
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "orion-api", "environment": settings.environment}


@app.get("/api/v1/reference/modalities")
async def contracting_modalities(active_only: bool = True) -> dict[str, Any]:
    try:
        data = await app.state.pncp.modalities(active_only=active_only)
    except PNCPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "source": "PNCP",
        "retrieved_at": datetime.now(UTC).isoformat(),
        "count": len(data),
        "data": data,
    }


@app.get("/api/v1/procurements/{cnpj}/{year}/{sequence}")
async def procurement_detail(cnpj: str, year: int, sequence: int) -> dict[str, Any]:
    try:
        data = await app.state.pncp.contracting_detail(
            cnpj=cnpj, year=year, sequence=sequence
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PNCPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "source": "PNCP",
        "retrieved_at": datetime.now(UTC).isoformat(),
        "data": data,
    }


@app.get("/api/v1/procurements/{cnpj}/{year}/{sequence}/documents")
async def procurement_documents(cnpj: str, year: int, sequence: int) -> dict[str, Any]:
    try:
        documents = await app.state.pncp.contracting_documents(
            cnpj=cnpj, year=year, sequence=sequence
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PNCPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "source": "PNCP",
        "retrieved_at": datetime.now(UTC).isoformat(),
        "count": len(documents),
        "documents": documents,
    }


@app.get(
    "/api/v1/procurements/{cnpj}/{year}/{sequence}/documents/{document_sequence}/content"
)
async def procurement_document_content(
    cnpj: str, year: int, sequence: int, document_sequence: int
) -> Response:
    try:
        content, content_type = await app.state.pncp.download_contracting_document(
            cnpj=cnpj,
            year=year,
            sequence=sequence,
            document_sequence=document_sequence,
            max_bytes=settings.pncp_max_document_bytes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PNCPError as exc:
        status_code = 413 if "excede o limite" in str(exc) else 502
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    digest = hashlib.sha256(content).hexdigest()
    safe_content_type = (
        content_type
        if content_type.startswith(("application/", "image/", "text/"))
        else "application/octet-stream"
    )
    filename = f"pncp-{cnpj}-{year}-{sequence}-{document_sequence}"
    return Response(
        content=content,
        media_type=safe_content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-SHA256": digest,
            "X-Content-Length": str(len(content)),
            "X-Document-Source": "PNCP",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.get("/api/v1/opportunities/open")
async def open_opportunities(
    end_date: date = Query(..., description="Data final da consulta"),  # noqa: B008
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=50),
    modality_code: int | None = Query(None, ge=1),
    uf: str | None = Query(None, min_length=2, max_length=2),
) -> dict[str, Any]:
    try:
        data = await app.state.pncp.open_proposals(
            end_date=end_date,
            page=page,
            page_size=page_size,
            modality_code=modality_code,
            uf=uf,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PNCPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"source": "PNCP", "retrieved_at": datetime.now(UTC).isoformat(), "raw": data}


@app.get("/api/v1/opportunities/published")
async def published_opportunities(
    start_date: date,
    end_date: date,
    modality_code: int = Query(..., ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=50),
    uf: str | None = Query(None, min_length=2, max_length=2),
) -> dict[str, Any]:
    try:
        data = await app.state.pncp.published(
            start_date=start_date,
            end_date=end_date,
            modality_code=modality_code,
            page=page,
            page_size=page_size,
            uf=uf,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PNCPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"source": "PNCP", "retrieved_at": datetime.now(UTC).isoformat(), "raw": data}


@app.get("/api/v1/opportunities/{external_id}/versions")
async def opportunity_version_history(
    external_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    session_factory = require_session_factory()
    async with session_factory() as session:
        history = await get_opportunity_versions(
            session, external_id=external_id, page=page, page_size=page_size
        )
    if history is None:
        raise HTTPException(status_code=404, detail="Oportunidade não encontrada.")
    return {
        "source": "ORION",
        "retrieved_at": datetime.now(UTC).isoformat(),
        **history,
    }



@app.get(
    "/api/v1/procurements/{external_id}/documents/{document_sequence}/versions"
)
async def document_asset_version_history(
    external_id: str,
    document_sequence: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    session_factory = require_session_factory()
    async with session_factory() as session:
        history = await get_document_asset_versions(
            session,
            external_id=external_id,
            document_sequence=document_sequence,
            page=page,
            page_size=page_size,
        )
    if history is None:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    return {
        "source": "ORION",
        "retrieved_at": datetime.now(UTC).isoformat(),
        **history,
    }


@app.get("/api/v1/document-sync-operations")
async def document_sync_operations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    session_factory = require_session_factory()
    async with session_factory() as session:
        data = await list_document_sync_operations(
            session, page=page, page_size=page_size
        )
    return {"source": "ORION", "retrieved_at": datetime.now(UTC).isoformat(), **data}


@app.get("/api/v1/document-sync-operations/{operation_id}")
async def document_sync_operation_detail(operation_id: int) -> dict[str, Any]:
    session_factory = require_session_factory()
    async with session_factory() as session:
        operation = await get_document_sync_operation(
            session, operation_id=operation_id
        )
    if operation is None:
        raise HTTPException(status_code=404, detail="Operação de sincronização não encontrada.")
    return {
        "source": "ORION",
        "retrieved_at": datetime.now(UTC).isoformat(),
        "operation": operation,
    }
