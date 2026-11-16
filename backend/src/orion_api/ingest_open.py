import argparse
import asyncio
from datetime import UTC, date, datetime

from orion_api.config import settings
from orion_api.db import require_session_factory
from orion_api.pncp import PNCPClient
from orion_api.repository import upsert_pncp_opportunities


async def run(end_date: date, max_pages: int, page_size: int, uf: str | None) -> None:
    client = PNCPClient(
        base_url=settings.pncp_base_url,
        timeout_seconds=settings.pncp_timeout_seconds,
        max_page_size=settings.pncp_max_page_size,
    )
    result = await client.collect_open_proposals(
        end_date=end_date,
        max_pages=max_pages,
        page_size=page_size,
        uf=uf,
    )
    session_factory = require_session_factory()
    async with session_factory() as session:
        persisted = await upsert_pncp_opportunities(session, result["data"])

    print(
        {
            "source": "PNCP",
            "collected_at": datetime.now(UTC).isoformat(),
            "pages_collected": result["pages_collected"],
            "source_total_pages": result["source_total_pages"],
            "collection_complete": result["collection_complete"],
            **persisted,
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Coleta oportunidades abertas do PNCP para o ORION.")
    parser.add_argument("--end-date", type=date.fromisoformat, default=None)
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--uf", type=str, default=None)
    args = parser.parse_args()
    end_date = args.end_date or datetime.now(UTC).date()
    asyncio.run(run(end_date, args.max_pages, args.page_size, args.uf))


if __name__ == "__main__":
    main()
