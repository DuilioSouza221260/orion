import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from orion_api.models import (
    DocumentAsset,
    DocumentAssetVersion,
    IngestionCheckpoint,
    IngestionRun,
    Opportunity,
    OpportunityVersion,
)


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



async def get_document_asset_versions(
    session: AsyncSession,
    *,
    external_id: str,
    document_sequence: int,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any] | None:
    if (
        not external_id.strip()
        or document_sequence < 1
        or page < 1
        or not 1 <= page_size <= 100
    ):
        raise ValueError("Parâmetros de histórico do documento inválidos.")

    asset_result = await session.execute(
        select(DocumentAsset).where(
            DocumentAsset.source == "PNCP",
            DocumentAsset.external_id == external_id.strip(),
            DocumentAsset.document_sequence == document_sequence,
        )
    )
    asset = asset_result.scalar_one_or_none()
    if asset is None:
        return None

    count_result = await session.execute(
        select(func.count(DocumentAssetVersion.id)).where(
            DocumentAssetVersion.asset_id == asset.id
        )
    )
    total = count_result.scalar_one()

    versions_result = await session.execute(
        select(DocumentAssetVersion)
        .where(DocumentAssetVersion.asset_id == asset.id)
        .order_by(
            DocumentAssetVersion.observed_at.desc(),
            DocumentAssetVersion.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    versions = versions_result.scalars().all()

    return {
        "document": {
            "id": asset.id,
            "source": asset.source,
            "external_id": asset.external_id,
            "document_sequence": asset.document_sequence,
            "status": asset.status,
            "first_seen_at": asset.first_seen_at.isoformat(),
            "last_seen_at": asset.last_seen_at.isoformat(),
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
                "sha256": version.sha256,
                "filename": version.filename,
                "content_type": version.content_type,
                "byte_size": version.byte_size,
                "storage_backend": version.storage_backend,
                "storage_key": version.storage_key,
                "status": version.status,
                "observed_at": version.observed_at.isoformat(),
            }
            for version in versions
        ],
    }


DOCUMENT_SYNC_LEASE_SECONDS = 900


class DocumentSyncAlreadyRunning(RuntimeError):
    """A contratação já possui uma sincronização ativa."""


async def recover_stale_document_sync_operations(
    session: AsyncSession,
    *,
    external_id: str | None = None,
    now: datetime | None = None,
) -> int:
    from orion_api.models import DocumentSyncOperation

    current_time = now or datetime.now(UTC)
    statement = (
        update(DocumentSyncOperation)
        .where(
            DocumentSyncOperation.status == "running",
            DocumentSyncOperation.lease_expires_at.is_not(None),
            DocumentSyncOperation.lease_expires_at <= current_time,
        )
        .values(
            status="failed",
            finished_at=current_time,
            lease_expires_at=None,
            last_error="Lease expirado: operação interrompida ou sem heartbeat.",
            failures=[{"error": "Lease expirado: operação interrompida ou sem heartbeat."}],
        )
    )
    if external_id is not None:
        statement = statement.where(DocumentSyncOperation.external_id == external_id)
    result = await session.execute(statement)
    await session.commit()
    return max(result.rowcount or 0, 0)


async def create_document_sync_operation(
    session: AsyncSession, *, external_id: str
) -> int:
    from sqlalchemy.exc import IntegrityError

    from orion_api.models import DocumentSyncOperation

    now = datetime.now(UTC)
    await recover_stale_document_sync_operations(
        session, external_id=external_id, now=now
    )
    operation = DocumentSyncOperation(
        external_id=external_id,
        status="running",
        listed=0,
        archived=0,
        removed=0,
        failures=[],
        heartbeat_at=now,
        lease_expires_at=now + timedelta(seconds=DOCUMENT_SYNC_LEASE_SECONDS),
    )
    session.add(operation)
    try:
        await session.flush()
        operation_id = operation.id
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise DocumentSyncAlreadyRunning(
            "Já existe uma sincronização ativa para esta contratação."
        ) from exc
    return operation_id


async def heartbeat_document_sync_operation(
    session: AsyncSession, *, operation_id: int
) -> bool:
    from orion_api.models import DocumentSyncOperation

    now = datetime.now(UTC)
    result = await session.execute(
        update(DocumentSyncOperation)
        .where(
            DocumentSyncOperation.id == operation_id,
            DocumentSyncOperation.status == "running",
        )
        .values(
            heartbeat_at=now,
            lease_expires_at=now + timedelta(seconds=DOCUMENT_SYNC_LEASE_SECONDS),
        )
    )
    await session.commit()
    return bool(result.rowcount)


async def finish_document_sync_operation(
    session: AsyncSession,
    *,
    operation_id: int,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    from orion_api.models import DocumentSyncOperation

    values: dict[str, Any] = {
        "status": (
            "completed" if result and result.get("complete")
            else "partial" if result
            else "failed"
        ),
        "finished_at": datetime.now(UTC),
        "lease_expires_at": None,
        "last_error": error[:1000] if error else None,
    }
    if result:
        values.update({
            "listed": result.get("listed", 0),
            "archived": result.get("archived", 0),
            "removed": result.get("removed", 0),
            "failures": result.get("failures", []),
        })
    elif error:
        values["failures"] = [{"error": error[:1000]}]
    await session.execute(
        update(DocumentSyncOperation)
        .where(
            DocumentSyncOperation.id == operation_id,
            DocumentSyncOperation.status == "running",
        )
        .values(**values)
    )
    await session.commit()


async def get_document_sync_operation(
    session: AsyncSession, *, operation_id: int
) -> dict[str, Any] | None:
    from orion_api.models import DocumentSyncOperation

    result = await session.execute(
        select(DocumentSyncOperation).where(DocumentSyncOperation.id == operation_id)
    )
    operation = result.scalar_one_or_none()
    if operation is None:
        return None
    return _serialize_document_sync_operation(operation)


async def list_document_sync_operations(
    session: AsyncSession, *, page: int = 1, page_size: int = 20
) -> dict[str, Any]:
    from orion_api.models import DocumentSyncOperation

    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("Parâmetros de operações inválidos.")
    count = await session.execute(select(func.count(DocumentSyncOperation.id)))
    total = count.scalar_one()
    rows = await session.execute(
        select(DocumentSyncOperation)
        .order_by(DocumentSyncOperation.started_at.desc(), DocumentSyncOperation.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    operations = rows.scalars().all()
    return {
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size,
        },
        "operations": [_serialize_document_sync_operation(item) for item in operations],
    }


def _serialize_document_sync_operation(operation: Any) -> dict[str, Any]:
    return {
        "id": operation.id,
        "source": operation.source,
        "external_id": operation.external_id,
        "status": operation.status,
        "listed": operation.listed,
        "archived": operation.archived,
        "removed": operation.removed,
        "failures": operation.failures,
        "heartbeat_at": operation.heartbeat_at.isoformat() if operation.heartbeat_at else None,
        "lease_expires_at": operation.lease_expires_at.isoformat() if operation.lease_expires_at else None,
        "last_error": operation.last_error,
        "started_at": operation.started_at.isoformat(),
        "finished_at": (
            operation.finished_at.isoformat() if operation.finished_at else None
        ),
    }



async def create_ingestion_run(
    session: AsyncSession, *, endpoint: str, filters: dict[str, Any]
) -> int:
    if endpoint not in {"publicacao", "atualizacao"}:
        raise ValueError("Endpoint de ingestão inválido.")
    now = datetime.now(UTC)
    run = IngestionRun(
        endpoint=endpoint,
        filters=filters,
        status="running",
        counters={},
        failures=[],
        heartbeat_at=now,
        lease_expires_at=now + timedelta(seconds=DOCUMENT_SYNC_LEASE_SECONDS),
    )
    session.add(run)
    await session.flush()
    run_id = run.id
    await session.commit()
    return run_id


async def record_ingestion_checkpoint(
    session: AsyncSession,
    *,
    run_id: int,
    modality_id: int,
    page: int,
    pages_total: int | None,
    records_received: int,
) -> None:
    if run_id < 1 or modality_id < 1 or page < 1 or records_received < 0:
        raise ValueError("Checkpoint de ingestão inválido.")
    if pages_total is not None and pages_total < 1:
        raise ValueError("Total de páginas inválido.")
    now = datetime.now(UTC)
    statement = insert(IngestionCheckpoint).values(
        ingestion_run_id=run_id,
        modality_id=modality_id,
        page=page,
        pages_total=pages_total,
        records_received=records_received,
        completed_at=now,
    )
    statement = statement.on_conflict_do_update(
        constraint="uq_ingestion_checkpoint_run_modality_page",
        set_={
            "pages_total": statement.excluded.pages_total,
            "records_received": statement.excluded.records_received,
            "completed_at": now,
        },
    )
    await session.execute(statement)
    await session.execute(
        update(IngestionRun)
        .where(IngestionRun.id == run_id, IngestionRun.status == "running")
        .values(
            heartbeat_at=now,
            lease_expires_at=now + timedelta(seconds=DOCUMENT_SYNC_LEASE_SECONDS),
        )
    )
    await session.commit()


async def get_ingestion_run(session: AsyncSession, *, run_id: int) -> dict[str, Any] | None:
    result = await session.execute(select(IngestionRun).where(IngestionRun.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        return None
    checkpoints = await session.execute(
        select(IngestionCheckpoint)
        .where(IngestionCheckpoint.ingestion_run_id == run_id)
        .order_by(IngestionCheckpoint.modality_id, IngestionCheckpoint.page)
    )
    pages = checkpoints.scalars().all()
    return {
        "id": run.id,
        "source": run.source,
        "endpoint": run.endpoint,
        "filters": run.filters,
        "status": run.status,
        "counters": run.counters,
        "failures": run.failures,
        "heartbeat_at": run.heartbeat_at.isoformat() if run.heartbeat_at else None,
        "lease_expires_at": run.lease_expires_at.isoformat() if run.lease_expires_at else None,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "checkpoints": [
            {
                "modality_id": item.modality_id,
                "page": item.page,
                "pages_total": item.pages_total,
                "records_received": item.records_received,
                "completed_at": item.completed_at.isoformat(),
            }
            for item in pages
        ],
    }


async def finish_ingestion_run(
    session: AsyncSession, *, run_id: int, complete: bool, failures: list[dict[str, Any]]
) -> None:
    now = datetime.now(UTC)
    await session.execute(
        update(IngestionRun)
        .where(IngestionRun.id == run_id, IngestionRun.status == "running")
        .values(
            status="completed" if complete else "partial",
            failures=failures,
            finished_at=now,
            heartbeat_at=now,
            lease_expires_at=None,
        )
    )
    await session.commit()
