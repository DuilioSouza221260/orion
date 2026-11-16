import argparse
import asyncio
import json
import sys
from datetime import UTC, date, datetime
from typing import Any

from orion_api.config import settings
from orion_api.db import require_session_factory
from orion_api.pncp import PNCPClient
from orion_api.repository import (
    create_ingestion_run,
    finish_ingestion_run,
    get_ingestion_run,
    record_ingestion_checkpoint,
    upsert_pncp_opportunities,
)


async def run(
    start_date: date,
    end_date: date,
    max_pages_per_modality: int,
    page_size: int,
    uf: str | None,
    client: Any | None = None,
    session_factory: Any | None = None,
    resume_run_id: int | None = None,
) -> dict[str, Any]:
    client = client or PNCPClient(
        base_url=settings.pncp_base_url,
        domain_base_url=settings.pncp_domain_base_url,
        timeout_seconds=settings.pncp_timeout_seconds,
        max_page_size=settings.pncp_max_page_size,
    )
    factory = session_factory or require_session_factory()
    filters = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "page_size": page_size,
        "max_pages_per_modality": max_pages_per_modality,
        "uf": uf.upper() if uf else None,
    }
    resume_pages: dict[int, int] = {}
    if resume_run_id is None:
        async with factory() as session:
            run_id = await create_ingestion_run(
                session, endpoint="atualizacao", filters=filters
            )
    else:
        async with factory() as session:
            previous = await get_ingestion_run(session, run_id=resume_run_id)
        if previous is None:
            raise ValueError(f"Execução de ingestão {resume_run_id} não encontrada.")
        if previous["endpoint"] != "atualizacao" or previous["filters"] != filters:
            raise ValueError("Os filtros da retomada não correspondem à execução original.")
        if previous["status"] == "completed":
            raise ValueError("Esta execução já foi concluída e não pode ser retomada.")
        run_id = resume_run_id
        for checkpoint in previous["checkpoints"]:
            modality_id = checkpoint["modality_id"]
            resume_pages[modality_id] = max(resume_pages.get(modality_id, 1), checkpoint["page"] + 1)
        async with factory() as session:
            from sqlalchemy import update
            from orion_api.models import IngestionRun
            await session.execute(update(IngestionRun).where(IngestionRun.id == run_id).values(status="running", finished_at=None, failures=[]))
            await session.commit()
    persisted = {
        "received": 0,
        "inserted_or_updated": 0,
        "versions_created": 0,
        "skipped_without_id": 0,
    }

    async def persist_page(
        modality_id: int, page: int, records: list[dict[str, Any]]
    ) -> None:
        async with factory() as session:
            result = (
                await upsert_pncp_opportunities(
                    session, records, source_endpoint="pncp:atualizacao"
                )
                if records
                else {
                    "received": 0,
                    "inserted_or_updated": 0,
                    "versions_created": 0,
                    "skipped_without_id": 0,
                }
            )
        for key in persisted:
            persisted[key] += result[key]
        async with factory() as session:
            await record_ingestion_checkpoint(
                session,
                run_id=run_id,
                modality_id=modality_id,
                page=page,
                pages_total=None,
                records_received=len(records),
            )

    try:
        collection = await client.collect_all_updated(
            start_date=start_date,
            end_date=end_date,
            max_pages_per_modality=max_pages_per_modality,
            page_size=page_size,
            uf=uf,
            on_page=persist_page,
            retain_records=False,
            resume_pages=resume_pages,
        )
        async with factory() as session:
            await finish_ingestion_run(
                session,
                run_id=run_id,
                complete=collection["collection_complete"],
                failures=[
                    item for item in collection["modality_results"] if item.get("error")
                ],
            )
    except Exception as exc:
        async with factory() as session:
            await finish_ingestion_run(
                session,
                run_id=run_id,
                complete=False,
                failures=[{"error": str(exc)[:1000]}],
            )
        raise

    return {
        "source": "PNCP",
        "run_id": run_id,
        "collection_type": "global_update",
        "collected_at": datetime.now(UTC).isoformat(),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "modalities_discovered": collection["modalities_discovered"],
        "modalities_completed": collection["modalities_completed"],
        "collection_complete": collection["collection_complete"],
        "modality_results": collection["modality_results"],
        **persisted,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Coleta contratações atualizadas no PNCP em todas as modalidades ativas."
    )
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--max-pages-per-modality", type=int, default=100)
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--uf", type=str, default=None)
    parser.add_argument("--resume-run-id", type=int, default=None)
    args = parser.parse_args()

    result = asyncio.run(
        run(
            start_date=args.start_date,
            end_date=args.end_date,
            max_pages_per_modality=args.max_pages_per_modality,
            page_size=args.page_size,
            uf=args.uf,
            resume_run_id=args.resume_run_id,
        )
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if not result["collection_complete"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
