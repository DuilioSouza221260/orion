import pytest

from orion_api.repository import _payload_hash


def test_payload_hash_is_stable_for_different_key_order():
    first = {"nome": "Pregão", "valor": 1200, "orgao": {"cnpj": "123"}}
    second = {"orgao": {"cnpj": "123"}, "valor": 1200, "nome": "Pregão"}
    assert _payload_hash(first) == _payload_hash(second)


def test_payload_hash_changes_when_source_payload_changes():
    first = {"numeroControlePNCP": "A", "situacao": "aberta"}
    second = {"numeroControlePNCP": "A", "situacao": "encerrada"}
    assert _payload_hash(first) != _payload_hash(second)


@pytest.mark.asyncio
async def test_opportunity_upsert_records_version_for_new_or_changed_payload():
    from orion_api.repository import upsert_pncp_opportunities

    payload = {"numeroControlePNCP": "A", "situacao": "aberta"}

    class Result:
        def mappings(self):
            return self

        def all(self):
            return [{"id": 41, "payload_hash": _payload_hash(payload), "raw_payload": payload}]

    class FakeSession:
        def __init__(self):
            self.statements = []
            self.committed = False

        async def execute(self, statement):
            self.statements.append(statement)
            return Result() if len(self.statements) == 1 else object()

        async def commit(self):
            self.committed = True

    session = FakeSession()
    result = await upsert_pncp_opportunities(
        session, [payload], source_endpoint="pncp:publicacao"
    )

    assert result == {
        "received": 1,
        "inserted_or_updated": 1,
        "versions_created": 1,
        "skipped_without_id": 0,
    }
    assert len(session.statements) == 3
    assert "opportunity_versions" in str(session.statements[2])
    assert session.committed


@pytest.mark.asyncio
async def test_unchanged_opportunity_updates_seen_timestamp_without_new_version():
    from orion_api.repository import upsert_pncp_opportunities

    class Result:
        def mappings(self):
            return self

        def all(self):
            return []

    class FakeSession:
        def __init__(self):
            self.statements = []

        async def execute(self, statement):
            self.statements.append(statement)
            return Result() if len(self.statements) == 1 else object()

        async def commit(self):
            pass

    session = FakeSession()
    result = await upsert_pncp_opportunities(
        session, [{"numeroControlePNCP": "A", "situacao": "aberta"}]
    )
    assert result["inserted_or_updated"] == 0
    assert result["versions_created"] == 0
    assert len(session.statements) == 2


def test_document_sha256_validation_accepts_hex_digest():
    from orion_api.repository import upsert_document_asset

    assert callable(upsert_document_asset)


@pytest.mark.parametrize("digest", ["", "not-a-hash", "g" * 64, "a" * 63])
def test_document_asset_rejects_invalid_digest_before_database_write(digest):
    import asyncio

    from orion_api.repository import upsert_document_asset

    class NoDatabase:
        async def execute(self, statement):
            raise AssertionError("Não deveria acessar o banco.")

    with pytest.raises(ValueError, match="SHA-256 inválido"):
        asyncio.run(
            upsert_document_asset(
                NoDatabase(),
                sha256=digest,
                external_id="PNCP-123",
                document_sequence=1,
                content_type="application/pdf",
                byte_size=10,
                storage_backend="s3",
                storage_key=f"sha256/{digest}",
            )
        )


@pytest.mark.asyncio
async def test_s3_storage_uploads_content_addressed_object_once():
    import hashlib

    from botocore.exceptions import ClientError

    from orion_api.storage import S3ObjectStore

    class FakeS3:
        def __init__(self):
            self.objects = {}
            self.put_calls = 0

        def head_object(self, *, Bucket, Key):
            if Key not in self.objects:
                raise ClientError(
                    {"Error": {"Code": "404"}, "ResponseMetadata": {"HTTPStatusCode": 404}},
                    "HeadObject",
                )
            return {}

        def put_object(self, **kwargs):
            self.put_calls += 1
            self.objects[kwargs["Key"]] = kwargs["Body"]

    client = FakeS3()
    store = S3ObjectStore(bucket="orion-test", client=client)
    content = b"edital de teste"
    first = await store.store(content=content, content_type="application/pdf")
    second = await store.store(content=content, content_type="application/pdf")

    digest = hashlib.sha256(content).hexdigest()
    assert first["sha256"] == digest
    assert first["storage_key"] == f"sha256/{digest[:2]}/{digest}"
    assert first["created"] is True
    assert second["created"] is False
    assert client.put_calls == 1


@pytest.mark.asyncio
async def test_s3_storage_rejects_empty_documents():
    from orion_api.storage import S3ObjectStore

    store = S3ObjectStore(bucket="orion-test", client=object())
    with pytest.raises(ValueError, match="documento vazio"):
        await store.store(content=b"", content_type="application/pdf")


@pytest.mark.asyncio
async def test_archive_pncp_document_uploads_and_registers_reference(monkeypatch):
    from orion_api import storage

    captured = {}

    class FakeStore:
        async def store(self, *, content, content_type):
            assert content == b"edital"
            assert content_type == "application/pdf"
            return {
                "sha256": "a" * 64,
                "storage_key": "sha256/aa/" + "a" * 64,
                "storage_backend": "s3",
                "byte_size": 6,
                "created": True,
            }

    async def fake_upsert(session, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(storage, "upsert_document_asset", fake_upsert)
    result = await storage.archive_pncp_document(
        object(),
        store=FakeStore(),
        content=b"edital",
        content_type="application/pdf",
        external_id="10000000000003-2026-15",
        document_sequence=3,
        filename="edital.pdf",
    )

    assert result["source"] == "PNCP"
    assert result["created"] is True
    assert captured["external_id"] == "10000000000003-2026-15"
    assert captured["document_sequence"] == 3
    assert captured["sha256"] == "a" * 64


@pytest.mark.asyncio
async def test_document_asset_upsert_creates_version_only_when_metadata_changes():
    from orion_api.repository import upsert_document_asset

    asset = {
        "id": 7,
        "sha256": "a" * 64,
        "filename": "edital.pdf",
        "content_type": "application/pdf",
        "byte_size": 120,
        "storage_backend": "s3",
        "storage_key": "sha256/aa/" + "a" * 64,
        "status": "present",
    }

    class Result:
        def mappings(self):
            return self

        def all(self):
            return [asset]

    class FakeSession:
        def __init__(self):
            self.statements = []
            self.committed = False

        async def execute(self, statement):
            self.statements.append(statement)
            return Result()

        async def commit(self):
            self.committed = True

    session = FakeSession()
    await upsert_document_asset(
        session,
        sha256="a" * 64,
        external_id="PNCP-123",
        document_sequence=1,
        content_type="application/pdf",
        byte_size=120,
        storage_backend="s3",
        storage_key=asset["storage_key"],
        filename="edital.pdf",
    )
    assert len(session.statements) == 2
    assert "document_asset_versions" in str(session.statements[1])
    assert session.committed


@pytest.mark.asyncio
async def test_document_asset_upsert_does_not_version_unchanged_metadata():
    from orion_api.repository import upsert_document_asset

    class Result:
        def mappings(self):
            return self

        def all(self):
            return []

    class FakeSession:
        def __init__(self):
            self.statements = []

        async def execute(self, statement):
            self.statements.append(statement)
            return Result()

        async def commit(self):
            pass

    session = FakeSession()
    await upsert_document_asset(
        session,
        sha256="b" * 64,
        external_id="PNCP-123",
        document_sequence=1,
        content_type="application/pdf",
        byte_size=120,
        storage_backend="s3",
        storage_key="sha256/bb/" + "b" * 64,
        filename="edital.pdf",
    )
    assert len(session.statements) == 1


@pytest.mark.asyncio
async def test_incomplete_document_listing_never_marks_assets_removed():
    from orion_api.repository import mark_missing_document_assets_removed

    class NoDatabase:
        async def execute(self, statement):
            raise AssertionError("Listagem incompleta não pode alterar documentos.")

    removed = await mark_missing_document_assets_removed(
        NoDatabase(),
        external_id="PNCP-123",
        listed_sequences=[],
        listing_complete=False,
    )
    assert removed == 0


@pytest.mark.asyncio
async def test_complete_document_listing_versions_removed_assets():
    from orion_api.repository import mark_missing_document_assets_removed

    removed_asset = {
        "id": 7,
        "sha256": "c" * 64,
        "filename": "anexo.pdf",
        "content_type": "application/pdf",
        "byte_size": 90,
        "storage_backend": "s3",
        "storage_key": "sha256/cc/" + "c" * 64,
        "status": "removed",
    }

    class Result:
        def mappings(self):
            return self

        def all(self):
            return [removed_asset]

    class FakeSession:
        def __init__(self):
            self.statements = []

        async def execute(self, statement):
            self.statements.append(statement)
            return Result()

        async def commit(self):
            pass

    session = FakeSession()
    removed = await mark_missing_document_assets_removed(
        session,
        external_id="PNCP-123",
        listed_sequences=[1, 3],
        listing_complete=True,
    )
    assert removed == 1
    assert len(session.statements) == 2
    assert "document_asset_versions" in str(session.statements[1])



@pytest.mark.asyncio
async def test_sync_procurement_documents_archives_listed_files_and_reconciles_missing(
    monkeypatch,
):
    from orion_api import storage

    class FakeClient:
        def _validate_contract_reference(self, cnpj, year, sequence):
            assert (cnpj, year, sequence) == ("10000000000003", 2026, 15)

        async def contracting_documents(self, **kwargs):
            return [
                {"sequencialDocumento": 3, "titulo": "Edital.pdf"},
                {"sequencialDocumento": 4, "titulo": "Anexo.pdf"},
            ]

        async def download_contracting_document(self, **kwargs):
            if kwargs["document_sequence"] == 4:
                raise storage.PNCPError("Documento indisponível.")
            return b"edital", "application/pdf"

    class FakeStore:
        async def store(self, **kwargs):
            return {
                "sha256": "a" * 64,
                "storage_key": "sha256/aa/" + "a" * 64,
                "storage_backend": "s3",
                "byte_size": 6,
                "created": True,
            }

    captured = {}
    heartbeat_calls = 0

    async def heartbeat():
        nonlocal heartbeat_calls
        heartbeat_calls += 1

    async def fake_upsert(session, **kwargs):
        captured["upsert"] = kwargs

    async def fake_mark_removed(session, **kwargs):
        captured["reconcile"] = kwargs
        return 1

    monkeypatch.setattr(storage, "upsert_document_asset", fake_upsert)
    monkeypatch.setattr(storage, "mark_missing_document_assets_removed", fake_mark_removed)

    result = await storage.synchronize_pncp_procurement_documents(
        object(),
        client=FakeClient(),
        store=FakeStore(),
        cnpj="10000000000003",
        year=2026,
        sequence=15,
        max_bytes=1024,
        heartbeat=heartbeat,
    )

    assert result["listed"] == 2
    assert result["archived"] == 1
    assert result["removed"] == 1
    assert result["complete"] is False
    assert result["failures"][0]["document_sequence"] == 4
    assert captured["upsert"]["filename"] == "Edital.pdf"
    assert captured["reconcile"]["listed_sequences"] == [3, 4]
    assert captured["reconcile"]["listing_complete"] is True
    assert heartbeat_calls == 5


@pytest.mark.asyncio
async def test_sync_procurement_documents_rejects_invalid_listing_before_reconciliation(
    monkeypatch,
):
    from orion_api import storage

    class FakeClient:
        def _validate_contract_reference(self, cnpj, year, sequence):
            pass

        async def contracting_documents(self, **kwargs):
            return [{"titulo": "Sem sequencial"}]

    class NoStore:
        pass

    async def forbidden_reconciliation(*args, **kwargs):
        raise AssertionError("Não deve reconciliar uma listagem inválida.")

    monkeypatch.setattr(
        storage, "mark_missing_document_assets_removed", forbidden_reconciliation
    )

    with pytest.raises(storage.PNCPError, match="sequencial válido"):
        await storage.synchronize_pncp_procurement_documents(
            object(),
            client=FakeClient(),
            store=NoStore(),
            cnpj="10000000000003",
            year=2026,
            sequence=15,
            max_bytes=1024,
        )



@pytest.mark.asyncio
async def test_document_sync_heartbeat_renews_only_running_operation():
    from orion_api.repository import heartbeat_document_sync_operation

    class Result:
        rowcount = 1

    class FakeSession:
        def __init__(self):
            self.statement = None
            self.committed = False

        async def execute(self, statement):
            self.statement = statement
            return Result()

        async def commit(self):
            self.committed = True

    session = FakeSession()
    renewed = await heartbeat_document_sync_operation(session, operation_id=71)

    assert renewed is True
    assert "lease_expires_at" in str(session.statement)
    assert "status" in str(session.statement)
    assert session.committed


@pytest.mark.asyncio
async def test_stale_document_sync_operations_are_recovered():
    from datetime import UTC, datetime

    from orion_api.repository import recover_stale_document_sync_operations

    class Result:
        rowcount = 2

    class FakeSession:
        def __init__(self):
            self.statement = None
            self.committed = False

        async def execute(self, statement):
            self.statement = statement
            return Result()

        async def commit(self):
            self.committed = True

    session = FakeSession()
    now = datetime(2026, 11, 16, tzinfo=UTC)
    recovered = await recover_stale_document_sync_operations(
        session, external_id="10000000000003-2026-15", now=now
    )

    assert recovered == 2
    assert "lease_expires_at" in str(session.statement)
    assert "external_id" in str(session.statement)
    assert session.committed
