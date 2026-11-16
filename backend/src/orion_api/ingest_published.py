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
    async with factory() as session:
        run_id = await create_ingestion_run(
            session, endpoint="publicacao", filters=filters
        )
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
                    session, records, source_endpoint="pncp:publicacao"
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
        collection = await client.collect_all_published(
            start_date=start_date,
            end_date=end_date,
            max_pages_per_modality=max_pages_per_modality,
            page_size=page_size,
            uf=uf,
            on_page=persist_page,
            retain_records=False,
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
        description="Coleta publicações do PNCP em todas as modalidades ativas."
    )
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--max-pages-per-modality", type=int, default=100)
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--uf", type=str, default=None)
    args = parser.parse_args()

    result = asyncio.run(
        run(
            start_date=args.start_date,
            end_date=args.end_date,
            max_pages_per_modality=args.max_pages_per_modality,
            page_size=args.page_size,
            uf=args.uf,
        )
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if not result["collection_complete"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
