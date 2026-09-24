"""services/storage.py — Cloud Storage upload / signed-URL helpers.

Bucket layout (Implementation Plan §6.3):
    catalog/images/{sku_id}.jpg          public-read
    returns/{store_id}/{assessment_id}.jpg   private, V4 signed URL (1h)
    shelf/{store_id}/{timestamp}.jpg     private (future: planogram)
    imports/{store_id}/{job_id}/...      private, admin-only signed URL

Client-freshness / correctness note (audited when this file was
integrated into the common/core scaffold): `blob.generate_signed_url()`
with no extra arguments only works when the active credentials carry a
private key (a downloaded service-account JSON key file). On Cloud Run,
the default Application Default Credentials come from the metadata
server and have *no* private key — calling `generate_signed_url()`
unmodified there raises
`AttributeError: you need a private key to sign credentials` (a very
common, easy-to-miss production gotcha for this exact deployment target).
The documented fix is to sign via the IAM API instead, passing the
runtime service account's email + a fresh access token explicitly —
`generate_signed_url` below now does this by default (it works the same
way against a local key file too, so no environment-specific branching
is needed at call sites).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from config import Settings
from core.exceptions import StorageError, error_boundary
from core.logging import get_logger
from core.retry import retry_gcp_call

logger = get_logger(__name__)


class StorageService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._project_id = settings.gcp_project_id
        self._bucket_name = settings.gcs_bucket
        self._client: Any = None

    @property
    def bucket(self) -> Any:
        if self._client is None:
            from google.cloud import storage  # type: ignore[attr-defined]

            self._client = storage.Client(project=self._project_id)
        return self._client.bucket(self._bucket_name)

    @retry_gcp_call()
    def upload_bytes(
        self, object_path: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        """Upload raw bytes to `object_path`; returns the `gs://` URI."""
        with error_boundary(
            logger, wrap=StorageError, event="storage_upload_failed",
            message="failed to upload object", object_path=object_path,
        ):
            blob = self.bucket.blob(object_path)
            blob.upload_from_string(data, content_type=content_type)
            logger.debug("storage_upload_ok", object_path=object_path, bytes=len(data))
            return f"gs://{self._bucket_name}/{object_path}"

    def public_url(self, object_path: str) -> str:
        """CDN-style public URL — only valid for objects under `catalog/images/`."""
        return f"https://storage.googleapis.com/{self._bucket_name}/{object_path}"

    @retry_gcp_call()
    def generate_signed_url(self, object_path: str, ttl: timedelta = timedelta(hours=1)) -> str:
        """V4 signed URL for private objects (`returns/`, `imports/`).

        Signs via the IAM API using the current runtime credentials'
        service-account email + a fresh access token, so this works both
        against a local service-account key file (local dev) and Cloud
        Run's metadata-server credentials (staging/production) without a
        code branch for either. Set `settings.gcp_service_account_email`
        to sign as a *different* service account than the runtime
        identity (impersonation); otherwise it's inferred automatically.
        """
        import google.auth
        import google.auth.transport.requests

        with error_boundary(
            logger, wrap=StorageError, event="storage_signed_url_failed",
            message="failed to generate signed URL", object_path=object_path,
        ):
            credentials, _ = google.auth.default()
            credentials.refresh(google.auth.transport.requests.Request())  # type: ignore[no-untyped-call]

            service_account_email = (
                self._settings.gcp_service_account_email
                or getattr(credentials, "service_account_email", None)
            )

            blob = self.bucket.blob(object_path)
            return blob.generate_signed_url(  # type: ignore[no-any-return]
                version="v4",
                expiration=ttl,
                method="GET",
                service_account_email=service_account_email,
                access_token=credentials.token,
            )

    @retry_gcp_call()
    def download_bytes(self, object_path: str) -> bytes:
        with error_boundary(
            logger, wrap=StorageError, event="storage_download_failed",
            message="failed to download object", object_path=object_path,
        ):
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
