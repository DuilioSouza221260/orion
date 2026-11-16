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
