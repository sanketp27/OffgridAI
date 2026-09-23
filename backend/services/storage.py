"""services/storage.py — Cloud Storage upload / signed-URL helpers.

Bucket layout (Implementation Plan §6.3):
    catalog/images/{sku_id}.jpg          public-read
    returns/{store_id}/{assessment_id}.jpg   private, V4 signed URL (1h)
    shelf/{store_id}/{timestamp}.jpg     private (future: planogram)
    imports/{store_id}/{job_id}/...      private, admin-only signed URL
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any


class StorageService:
    def __init__(self, project_id: str, bucket_name: str) -> None:
        self._project_id = project_id
        self._bucket_name = bucket_name
        self._client: Any = None

    @property
    def bucket(self) -> Any:
        if self._client is None:
            from google.cloud import storage

            self._client = storage.Client(project=self._project_id)
        return self._client.bucket(self._bucket_name)

    def upload_bytes(
        self, object_path: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        """Upload raw bytes to `object_path`; returns the `gs://` URI."""
        blob = self.bucket.blob(object_path)
        blob.upload_from_string(data, content_type=content_type)
        return f"gs://{self._bucket_name}/{object_path}"

    def public_url(self, object_path: str) -> str:
        """CDN-style public URL — only valid for objects under `catalog/images/`."""
        return f"https://storage.googleapis.com/{self._bucket_name}/{object_path}"

    def generate_signed_url(self, object_path: str, ttl: timedelta = timedelta(hours=1)) -> str:
        """V4 signed URL for private objects (`returns/`, `imports/`)."""
        blob = self.bucket.blob(object_path)
        return blob.generate_signed_url(version="v4", expiration=ttl, method="GET")  # type: ignore[no-any-return]

    def download_bytes(self, object_path: str) -> bytes:
        blob = self.bucket.blob(object_path)
        return blob.download_as_bytes()  # type: ignore[no-any-return]

    # --- Path builders (keep the bucket layout centralized in one place) ---
    @staticmethod
    def catalog_image_path(sku_id: str, ext: str = "jpg") -> str:
        return f"catalog/images/{sku_id}.{ext}"

    @staticmethod
    def return_photo_path(store_id: str, assessment_id: str, ext: str = "jpg") -> str:
        return f"returns/{store_id}/{assessment_id}.{ext}"

    @staticmethod
    def import_source_path(store_id: str, job_id: str, ext: str) -> str:
        return f"imports/{store_id}/{job_id}/source.{ext}"

    @staticmethod
    def import_page_path(store_id: str, job_id: str, page_n: int) -> str:
        return f"imports/{store_id}/{job_id}/extracted_pages/page_{page_n}.json"

    @staticmethod
    def import_report_path(store_id: str, job_id: str) -> str:
        return f"imports/{store_id}/{job_id}/report.json"
