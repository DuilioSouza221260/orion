import asyncio
import hashlib
from typing import Any

import boto3
from botocore.exceptions import ClientError
from sqlalchemy.ext.asyncio import AsyncSession

from orion_api.config import settings
from orion_api.repository import upsert_document_asset


class ObjectStorageError(RuntimeError):
    """Falha ao armazenar ou verificar um objeto documental."""


class S3ObjectStore:
    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None = None,
        region: str = "us-east-1",
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        client: Any | None = None,
    ) -> None:
        if not bucket.strip():
            raise ValueError("O bucket S3 deve ser informado.")
        self.bucket = bucket
        self.client = client or boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

    def _put_if_missing(
        self, *, key: str, content: bytes, content_type: str, digest: str
    ) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return False
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if code not in {"404", "NoSuchKey", "NotFound"} and status != 404:
                raise ObjectStorageError("Não foi possível verificar o objeto no storage.") from exc

        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentLength=len(content),
                ContentType=content_type,
                Metadata={"sha256": digest},
            )
        except ClientError as exc:
            raise ObjectStorageError("Não foi possível gravar o objeto no storage.") from exc
        return True

    async def store(self, *, content: bytes, content_type: str) -> dict[str, Any]:
        if not content:
            raise ValueError("Não é permitido armazenar um documento vazio.")
        digest = hashlib.sha256(content).hexdigest()
        key = f"sha256/{digest[:2]}/{digest}"
        try:
            created = await asyncio.to_thread(
                self._put_if_missing,
                key=key,
                content=content,
                content_type=content_type,
                digest=digest,
            )
        except ObjectStorageError:
            raise
        except Exception as exc:
            raise ObjectStorageError("Falha inesperada no storage de documentos.") from exc
        return {
            "sha256": digest,
            "storage_key": key,
            "storage_backend": "s3",
            "byte_size": len(content),
            "created": created,
        }


async def archive_pncp_document(
    session: AsyncSession,
    *,
    store: S3ObjectStore,
    content: bytes,
    content_type: str,
    external_id: str,
    document_sequence: int,
    filename: str | None = None,
) -> dict[str, Any]:
    stored = await store.store(content=content, content_type=content_type)
    await upsert_document_asset(
        session,
        sha256=stored["sha256"],
        external_id=external_id,
        document_sequence=document_sequence,
        content_type=content_type,
        byte_size=stored["byte_size"],
        storage_backend=stored["storage_backend"],
        storage_key=stored["storage_key"],
        filename=filename,
    )
    return {
        **stored,
        "source": "PNCP",
        "external_id": external_id,
        "document_sequence": document_sequence,
    }


def configured_object_store() -> S3ObjectStore:
    if not settings.s3_bucket:
        raise RuntimeError("ORION_S3_BUCKET não foi configurado.")
    return S3ObjectStore(
        bucket=settings.s3_bucket,
        endpoint_url=settings.s3_endpoint_url,
        region=settings.s3_region,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key,
    )
