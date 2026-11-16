import argparse
import asyncio
import sys
from datetime import UTC, date, datetime
from typing import Any

from orion_api.config import settings
from orion_api.db import require_session_factory
from orion_api.pncp import PNCPClient
from orion_api.repository import upsert_pncp_opportunities


async def run(
    start_date: date,
    end_date: date,
    max_pages_per_modality: int,
    page_size: int,
    uf: str | None,
) -> dict[str, Any]:
    client = PNCPClient(
        base_url=settings.pncp_base_url,
        domain_base_url=settings.pncp_domain_base_url,
        timeout_seconds=settings.pncp_timeout_seconds,
        max_page_size=settings.pncp_max_page_size,
    )
    collection = await client.collect_all_updated(
        start_date=start_date,
        end_date=end_date,
        max_pages_per_modality=max_pages_per_modality,
        page_size=page_size,
        uf=uf,
    )

    session_factory = require_session_factory()
    async with session_factory() as session:
        persisted = await upsert_pncp_opportunities(\n            session, collection["data"], source_endpoint="pncp:atualizacao"\n        )

    return {
        "source": "PNCP",
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
    print(result)
    if not result["collection_complete"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
