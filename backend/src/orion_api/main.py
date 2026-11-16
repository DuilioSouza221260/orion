from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query

from orion_api.config import settings
from orion_api.pncp import PNCPClient, PNCPError


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pncp = PNCPClient(
        base_url=settings.pncp_base_url,
        timeout_seconds=settings.pncp_timeout_seconds,
        max_page_size=settings.pncp_max_page_size,
    )
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "orion-api", "environment": settings.environment}


@app.get("/api/v1/opportunities/open")
async def open_opportunities(
    end_date: date = Query(..., description="Data final da consulta"),
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
    return {"source": "PNCP", "retrieved_at": datetime.now(timezone.utc).isoformat(), "raw": data}


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
    return {"source": "PNCP", "retrieved_at": date.today().isoformat(), "raw": data}
