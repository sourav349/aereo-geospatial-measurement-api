"""Upload, inspect, and measure geographic file contents."""

from pathlib import PurePosixPath
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.errors import InputError
from app.models import GeoFeature, GeoFile
from app.schemas import FeatureInfo, FileInfo, Measurement, MeasurementsResponse
from app.services.measurement import geometry_as_json, measure
from app.services.parsers import parse_file

router = APIRouter(prefix="/api/files", tags=["geospatial files"])


def _get_file(db: Session, file_id: str) -> GeoFile:
    record = db.get(GeoFile, file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")
    return record


@router.post("/", response_model=FileInfo, status_code=201)
def upload_file(
    request: Request,
    file: UploadFile = File(..., description=".kml or .zip with .shp/.shx/.dbf/.prj"),
    db: Session = Depends(get_db),
):
    settings: Settings = request.app.state.settings
    raw_name = (file.filename or "").replace("\\", "/")
    filename = PurePosixPath(raw_name).name
    if not filename or len(filename) > 255:
        raise InputError("Missing or overly long filename")
    if not filename.lower().endswith((".kml", ".zip")):
        raise InputError("Only .kml and .zip files are supported", status_code=415)

    # A synchronous endpoint runs in FastAPI's thread pool. GIS parsing and
    # projection are CPU-bound and must not block the async event loop.
    # Read in capped chunks so a malicious client cannot exhaust server memory.
    buffer = bytearray()
    while chunk := file.file.read(1024 * 1024):
        buffer.extend(chunk)
        if len(buffer) > settings.max_upload_bytes:
            raise InputError("Upload exceeds configured size limit", status_code=413)
    if not buffer:
        raise InputError("Uploaded file is empty")

    parsed = parse_file(filename, bytes(buffer), settings)
    file_row = GeoFile(
        id=str(uuid4()),
        filename=filename,
        file_format=parsed.file_format,
        crs=parsed.crs.to_string(),
        feature_count=len(parsed.features),
        status="COMPLETED",
    )
    db.add(file_row)
    try:
        for index, feature in enumerate(parsed.features):
            result = measure(feature.geometry, parsed.crs)
            db.add(
                GeoFeature(
                    file_id=file_row.id,
                    feature_index=index,
                    feature_identifier=feature.identifier,
                    geometry_type=feature.geometry.geom_type,
                    geometry=geometry_as_json(feature.geometry),
                    attributes=feature.properties,
                    measurement_status=result.status,
                    measurement_type=result.kind,
                    measurement_value=result.value,
                    measurement_unit=result.unit,
                    projected_crs=result.projected_crs,
                    message=result.message,
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(file_row)
    return file_row


@router.get("/{file_id}/", response_model=FileInfo)
def get_file_info(file_id: str, db: Session = Depends(get_db)):
    return _get_file(db, file_id)


@router.get("/{file_id}/measurements/", response_model=MeasurementsResponse)
def get_measurements(
    file_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    geo_file = _get_file(db, file_id)
    rows = db.scalars(
        select(GeoFeature)
        .where(GeoFeature.file_id == file_id)
        .order_by(GeoFeature.feature_index)
        .offset(offset)
        .limit(limit)
    ).all()
    results = [
        FeatureInfo(
            feature_index=r.feature_index,
            feature_id=r.feature_identifier,
            geometry_type=r.geometry_type,
            geometry=r.geometry,
            crs=geo_file.crs,
            properties=r.attributes,
            measurement=Measurement(
                status=r.measurement_status,
                type=r.measurement_type,
                value=r.measurement_value,
                unit=r.measurement_unit,
                projected_crs=r.projected_crs,
                message=r.message,
            ),
        )
        for r in rows
    ]
    return MeasurementsResponse(
        file_id=file_id,
        total=geo_file.feature_count,
        offset=offset,
        limit=limit,
        measurements=results,
    )
