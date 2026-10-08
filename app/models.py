"""Normalized file and feature records."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GeoFile(Base):
    __tablename__ = "geo_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_format: Mapped[str] = mapped_column(String(12), nullable=False)
    crs: Mapped[str] = mapped_column(Text, nullable=False)
    feature_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    features: Mapped[list["GeoFeature"]] = relationship(back_populates="file", cascade="all, delete-orphan")


class GeoFeature(Base):
    __tablename__ = "geo_features"
    __table_args__ = (UniqueConstraint("file_id", "feature_index"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[str] = mapped_column(
        ForeignKey("geo_files.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feature_index: Mapped[int] = mapped_column(Integer, nullable=False)
    feature_identifier: Mapped[str | None] = mapped_column(String(255))
    geometry_type: Mapped[str] = mapped_column(String(64), nullable=False)
    geometry: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    measurement_status: Mapped[str] = mapped_column(String(24), nullable=False)
    measurement_type: Mapped[str | None] = mapped_column(String(16))
    measurement_value: Mapped[float | None] = mapped_column(Float)
    measurement_unit: Mapped[str | None] = mapped_column(String(12))
    projected_crs: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)

    file: Mapped[GeoFile] = relationship(back_populates="features")
