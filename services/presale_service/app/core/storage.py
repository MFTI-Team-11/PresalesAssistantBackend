from io import BytesIO

from minio import Minio
from minio.error import S3Error

from app.core.config import settings


class FileStorage:
    def __init__(self) -> None:
        self.client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.bucket = settings.minio_bucket

    def ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def put_file(
        self,
        object_key: str,
        content: bytes,
        content_type: str | None,
    ) -> None:
        self.ensure_bucket()
        self.client.put_object(
            bucket_name=self.bucket,
            object_name=object_key,
            data=BytesIO(content),
            length=len(content),
            content_type=content_type or "application/octet-stream",
        )

    def presigned_get_url(self, object_key: str) -> str | None:
        try:
            return self.client.presigned_get_object(self.bucket, object_key)
        except S3Error:
            return None
