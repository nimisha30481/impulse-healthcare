"""Private document storage: Amazon S3 (SSE-KMS) when configured, else a private local directory.

Files are never served from a public URL. Downloads go through an authorised API call that
either streams the bytes (local) or returns a short-lived presigned URL (S3, 5 minutes).
"""
import hashlib
from pathlib import Path

from app.core.config import get_settings
from app.integrations.registry import client

ALLOWED_TYPES = {
    "application/pdf": b"%PDF",
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/jpeg": b"\xff\xd8\xff",
}


class UploadRejected(ValueError):
    pass


def validate_upload(data: bytes, declared_type: str) -> str:
    """Checks size and that the file's magic bytes match an allowed type (not just the
    browser-supplied content type). Returns the detected mime type."""
    s = get_settings()
    if not data:
        raise UploadRejected("The file is empty.")
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise UploadRejected(f"Files must be {s.max_upload_mb} MB or smaller.")
    detected = next((mt for mt, magic in ALLOWED_TYPES.items() if data.startswith(magic)), None)
    if not detected:
        raise UploadRejected("Only PDF, JPG and PNG files are supported.")
    if declared_type and declared_type != detected and not (declared_type == "image/jpg" and detected == "image/jpeg"):
        raise UploadRejected("The file contents do not match its type.")
    if detected == "application/pdf" and (b"/JavaScript" in data or b"/JS " in data or b"/Launch" in data):
        raise UploadRejected("PDFs containing scripts or launch actions are not accepted.")
    return detected


def backend_name() -> str:
    return "s3" if get_settings().s3_documents_bucket else "local"


def put(key: str, data: bytes, mime: str) -> str:
    s = get_settings()
    if s.s3_documents_bucket:
        extra = {"ServerSideEncryption": "aws:kms"}
        if s.kms_key_id:
            extra["SSEKMSKeyId"] = s.kms_key_id
        client("s3").put_object(Bucket=s.s3_documents_bucket, Key=key, Body=data, ContentType=mime, **extra)
        return "s3"
    path = Path(s.local_storage_dir) / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return "local"


def get_bytes(backend: str, key: str) -> bytes:
    s = get_settings()
    if backend == "s3":
        return client("s3").get_object(Bucket=s.s3_documents_bucket, Key=key)["Body"].read()
    path = (Path(s.local_storage_dir) / key).resolve()
    root = Path(s.local_storage_dir).resolve()
    if root not in path.parents:
        raise UploadRejected("Invalid storage key")
    return path.read_bytes()


def presigned_url(key: str, filename: str) -> str:
    s = get_settings()
    return client("s3").generate_presigned_url(
        "get_object",
        Params={
            "Bucket": s.s3_documents_bucket,
            "Key": key,
            "ResponseContentDisposition": f'attachment; filename="{filename}"',
        },
        ExpiresIn=300,
    )


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
