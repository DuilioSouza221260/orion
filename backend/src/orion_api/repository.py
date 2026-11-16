import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from orion_api.models import Opportunity


def _payload_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def upsert_pncp_opportunities(
    session: AsyncSession,
    records: list[dict[str, Any]],
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
        return {"received": len(records), "inserted_or_updated": 0, "skipped_without_id": skipped}

    statement = insert(Opportunity).values(prepared)
    statement = statement.on_conflict_do_update(
        constraint="uq_opportunities_source_external_id",
        set_={
            "payload_hash": statement.excluded.payload_hash,
            "raw_payload": statement.excluded.raw_payload,
            "last_seen_at": statement.excluded.last_seen_at,
        },
    )
    result = await session.execute(statement)
    await session.commit()
    return {
        "received": len(records),
        "inserted_or_updated": result.rowcount or 0,
        "skipped_without_id": skipped,
    }
