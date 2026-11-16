import argparse
import asyncio
import json
from datetime import UTC, datetime

from orion_api.config import settings
from orion_api.db import require_session_factory
from orion_api.pncp import PNCPClient
from orion_api.storage import archive_pncp_document, configured_object_store


async def run(
    *,
    cnpj: str,
    year: int,
    sequence: int,
    document_sequence: int,
) -> dict:
    client = PNCPClient(
        base_url=settings.pncp_base_url,
        domain_base_url=settings.pncp_domain_base_url,
        timeout_seconds=settings.pncp_timeout_seconds,
        max_page_size=settings.pncp_max_page_size,
    )
    content, content_type = await client.download_contracting_document(
        cnpj=cnpj,
        year=year,
        sequence=sequence,
        document_sequence=document_sequence,
        max_bytes=settings.pncp_max_document_bytes,
    )
    external_id = f"{cnpj}-{year}-{sequence}"
    session_factory = require_session_factory()
    store = configured_object_store()
    async with session_factory() as session:
        archived = await archive_pncp_document(
            session,
            store=store,
            content=content,
            content_type=content_type,
            external_id=external_id,
            document_sequence=document_sequence,
            filename=f"pncp-{external_id}-{document_sequence}",
        )
    return {
        "source": "PNCP",
        "archived_at": datetime.now(UTC).isoformat(),
        **archived,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Baixa um documento do PNCP e arquiva o binário no S3 com catálogo PostgreSQL."
    )
    parser.add_argument("--cnpj", required=True, help="CNPJ do órgão, com 14 dígitos.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--sequence", type=int, required=True, help="Sequencial da contratação.")
    parser.add_argument("--document-sequence", type=int, required=True)
    args = parser.parse_args()
    result = asyncio.run(
        run(
            cnpj=args.cnpj,
            year=args.year,
            sequence=args.sequence,
            document_sequence=args.document_sequence,
        )
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
