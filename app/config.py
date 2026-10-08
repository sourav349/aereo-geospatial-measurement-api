"""Runtime limits and configuration; environment variables override defaults."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./geospatial.db")
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
    max_uncompressed_bytes: int = int(os.getenv("MAX_UNCOMPRESSED_BYTES", str(50 * 1024 * 1024)))
    max_features: int = int(os.getenv("MAX_FEATURES", "5000"))
    max_zip_members: int = int(os.getenv("MAX_ZIP_MEMBERS", "100"))
