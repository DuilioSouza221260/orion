import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from orion_api.models import DocumentAsset, DocumentAssetVersion, Opportunity, OpportunityVersion


def _payload_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def upsert_pncp_opportunities(
    session: AsyncSession,
    records: list[dict[str, Any]],
    *,
    source_endpoint: str = "pncp:unknown",
) -> dict[str, int]:
    now = datetime.now(UTC)
    prepared_by_id: dict[str, dict[str, Any]] = {}
    skipped = 0

    for record in records:
        external_id = record.get("numeroControlePNCP")
        if not isinstance(external_id, str) or not external_id.strip():
            skipped += 1
            continue
        prepared_by_id[external_id.strip()] = {
            "source": "PNCP",
            "external_id": external_id.strip(),
            "payload_hash": _payload_hash(record),
            "raw_payload": record,
            "last_seen_at": now,
        }

    prepared = list(prepared_by_id.values())
    if not prepared:
        return {
            "received": len(records),
            "inserted_or_updated": 0,
            "versions_created": 0,
            "skipped_without_id": skipped,
        }

    statement = insert(Opportunity).values(prepared)
    statement = statement.on_conflict_do_update(
        constraint="uq_opportunities_source_external_id",
        set_={
            "payload_hash": statement.excluded.payload_hash,
            "raw_payload": statement.excluded.raw_payload,
            "last_seen_at": statement.excluded.last_seen_at,
        },
        where=Opportunity.payload_hash.is_distinct_from(statement.excluded.payload_hash),
    ).returning(
        Opportunity.id,
        Opportunity.payload_hash,
        Opportunity.raw_payload,
    )
    changed = (await session.execute(statement)).mappings().all()

    # A unchanged record must still update last_seen_at without creating a version.
    await session.execute(
        update(Opportunity)
        .where(
            Opportunity.source == "PNCP",
            Opportunity.external_id.in_(list(prepared_by_id)),
        )
        .values(last_seen_at=now)
    )

    if changed:
        versions = [
            {
                "opportunity_id": row["id"],
                "payload_hash": row["payload_hash"],
                "raw_payload": row["raw_payload"],
                "source_endpoint": source_endpoint[:120],
                "observed_at": now,
            }
            for row in changed
        ]
        await session.execute(insert(OpportunityVersion).values(versions))

    await session.commit()
    return {
        "received": len(records),
        "inserted_or_updated": len(changed),
        "versions_created": len(changed),
        "skipped_without_id": skipped,
    }


async def upsert_document_asset(
    session: AsyncSession,
    *,
    sha256: str,
    external_id: str,
    document_sequence: int,
    content_type: str,
    byte_size: int,
    storage_backend: str,
    storage_key: str,
    filename: str | None = None,
) -> None:
    if len(sha256) != 64 or any(char not in "0123456789abcdef" for char in sha256.lower()):
        raise ValueError("SHA-256 inválido.")
    if not external_id.strip() or document_sequence < 1 or byte_size < 1:
        raise ValueError("Metadados do documento inválidos.")
    now = datetime.now(UTC)
    statement = insert(DocumentAsset).values(
        sha256=sha256.lower(),
        source="PNCP",
        external_id=external_id.strip(),
        document_sequence=document_sequence,
        filename=filename,
        content_type=content_type[:160],
        byte_size=byte_size,
        storage_backend=storage_backend,
        storage_key=storage_key,
        status="present",
        first_seen_at=now,
        last_seen_at=now,
    )
    statement = statement.on_conflict_do_update(
        constraint="uq_document_assets_source_reference",
        set_={
            "sha256": statement.excluded.sha256,
            "filename": statement.excluded.filename,
            "content_type": statement.excluded.content_type,
            "byte_size": statement.excluded.byte_size,
            "storage_backend": statement.excluded.storage_backend,
            "storage_key": statement.excluded.storage_key,
            "status": "present",
            "last_seen_at": now,
        },
        where=(
            DocumentAsset.sha256.is_distinct_from(statement.excluded.sha256)
            | DocumentAsset.filename.is_distinct_from(statement.excluded.filename)
            | DocumentAsset.content_type.is_distinct_from(statement.excluded.content_type)
            | DocumentAsset.byte_size.is_distinct_from(statement.excluded.byte_size)
            | DocumentAsset.storage_backend.is_distinct_from(statement.excluded.storage_backend)
            | DocumentAsset.storage_key.is_distinct_from(statement.excluded.storage_key)
            | DocumentAsset.status.is_distinct_from("present")
        ),
    ).returning(
        DocumentAsset.id,
        DocumentAsset.sha256,
        DocumentAsset.filename,
        DocumentAsset.content_type,
        DocumentAsset.byte_size,
        DocumentAsset.storage_backend,
        DocumentAsset.storage_key,
        DocumentAsset.status,
    )
    changed = (await session.execute(statement)).mappings().all()
    if changed:
        versions = [
            {
                "asset_id": row["id"],
                "sha256": row["sha256"],
                "filename": row["filename"],
                "content_type": row["content_type"],
                "byte_size": row["byte_size"],
                "storage_backend": row["storage_backend"],
                "storage_key": row["storage_key"],
                "status": row["status"],
                "observed_at": now,
            }
            for row in changed
        ]
        await session.execute(insert(DocumentAssetVersion).values(versions))
    await session.commit()


async def mark_missing_document_assets_removed(
    session: AsyncSession,
    *,
    external_id: str,
    listed_sequences: list[int],
    listing_complete: bool,
) -> int:
    """Mark missing documents only after an authoritative, complete PNCP listing."""
    if not external_id.strip():
        raise ValueError("Referência da contratação inválida.")
    if not listing_complete:
        return 0
    if any(sequence < 1 for sequence in listed_sequences):
        raise ValueError("Sequência de documento inválida.")

    now = datetime.now(UTC)
    statement = (
        update(DocumentAsset)
        .where(
            DocumentAsset.source == "PNCP",
            DocumentAsset.external_id == external_id.strip(),
            DocumentAsset.status == "present",
            ~DocumentAsset.document_sequence.in_(listed_sequences),
        )
        .values(status="removed", last_seen_at=now)
        .returning(
            DocumentAsset.id,
            DocumentAsset.sha256,
            DocumentAsset.filename,
            DocumentAsset.content_type,
            DocumentAsset.byte_size,
            DocumentAsset.storage_backend,
            DocumentAsset.storage_key,
            DocumentAsset.status,
        )
    )
    removed = (await session.execute(statement)).mappings().all()
    if removed:
        versions = [
            {
                "asset_id": row["id"],
                "sha256": row["sha256"],
                "filename": row["filename"],
                "content_type": row["content_type"],
                "byte_size": row["byte_size"],
                "storage_backend": row["storage_backend"],
                "storage_key": row["storage_key"],
                "status": "removed",
                "observed_at": now,
            }
            for row in removed
        ]
        await session.execute(insert(DocumentAssetVersion).values(versions))
    await session.commit()
    return len(removed)


async def get_opportunity_versions(
    session: AsyncSession,
    *,
    external_id: str,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any] | None:
    if not external_id.strip() or page < 1 or not 1 <= page_size <= 100:
        raise ValueError("Parâmetros de histórico inválidos.")

    opportunity_result = await session.execute(
        select(Opportunity).where(
            Opportunity.source == "PNCP",
            Opportunity.external_id == external_id.strip(),
        )
    )
    opportunity = opportunity_result.scalar_one_or_none()
    if opportunity is None:
        return None

    count_result = await session.execute(
        select(func.count(OpportunityVersion.id)).where(
            OpportunityVersion.opportunity_id == opportunity.id
        )
    )
    total = count_result.scalar_one()

    versions_result = await session.execute(
        select(OpportunityVersion)
        .where(OpportunityVersion.opportunity_id == opportunity.id)
        .order_by(OpportunityVersion.observed_at.desc(), OpportunityVersion.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    versions = versions_result.scalars().all()

    return {
        "opportunity": {
            "id": opportunity.id,
            "source": opportunity.source,
            "external_id": opportunity.external_id,
            "first_seen_at": opportunity.first_seen_at.isoformat(),
            "last_seen_at": opportunity.last_seen_at.isoformat(),
        },
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size,
        },
        "versions": [
            {
                "id": version.id,
                "payload_hash": version.payload_hash,
                "source_endpoint": version.source_endpoint,
                "observed_at": version.observed_at.isoformat(),
                "payload": version.raw_payload,
            }
            for version in versions
        ],
    }
