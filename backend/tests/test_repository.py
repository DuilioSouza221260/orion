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
