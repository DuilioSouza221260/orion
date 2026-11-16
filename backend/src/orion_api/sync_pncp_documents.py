import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from typing import Any

from orion_api.config import settings
from orion_api.db import require_session_factory
from orion_api.pncp import PNCPClient
from orion_api.storage import configured_object_store, synchronize_pncp_procurement_documents
from orion_api.repository import (
    create_document_sync_operation, finish_document_sync_operation,
)


async def run(
    *,
    cnpj: str,
    year: int,
    sequence: int,
    client: Any | None = None,
    store: Any | None = None,
    session_factory: Any | None = None,
) -> dict[str, Any]:
    pncp_client = client or PNCPClient(
        base_url=settings.pncp_base_url,
        domain_base_url=settings.pncp_domain_base_url,
        timeout_seconds=settings.pncp_timeout_seconds,
        max_page_size=settings.pncp_max_page_size,
    )
    object_store = store or configured_object_store()
    factory = session_factory or require_session_factory()

    external_id = f"{cnpj}-{year}-{sequence}"
    async with factory() as session:
        operation_id = await create_document_sync_operation(
            session, external_id=external_id
        )

    started_at = datetime.now(UTC).isoformat()
    try:
        async with factory() as session:
            result = await synchronize_pncp_procurement_documents(
                session,
                client=pncp_client,
                store=object_store,
                cnpj=cnpj,
                year=year,
                sequence=sequence,
                max_bytes=settings.pncp_max_document_bytes,
            )
        async with factory() as session:
            await finish_document_sync_operation(
                session, operation_id=operation_id, result=result
            )
    except Exception as exc:
        async with factory() as session:
            await finish_document_sync_operation(
                session, operation_id=operation_id, error=str(exc)
            )
        raise

    return {
        "operation": "pncp_document_sync",
        "operation_id": operation_id,
        "started_at": started_at,
        **result,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sincroniza e arquiva todos os documentos de uma contratação do PNCP."
    )
    parser.add_argument("--cnpj", required=True, help="CNPJ do órgão, com 14 dígitos.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--sequence", type=int, required=True, help="Sequencial da contratação.")
    args = parser.parse_args()

    result = asyncio.run(run(cnpj=args.cnpj, year=args.year, sequence=args.sequence))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if not result["complete"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
