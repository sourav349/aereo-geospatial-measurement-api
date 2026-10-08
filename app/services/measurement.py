"""CRS-aware measurements on Shapely geometries.

Coordinates are ALWAYS transformed into meters before `.area` or `.length`.
Small regional geometries use a UTM zone selected per feature.
For larger features or polar areas, use local equal-area /
equidistant projections.
"""

from dataclasses import dataclass
import math
import json

from pyproj import CRS, Transformer
from pyproj.exceptions import ProjError
from shapely import transform
from shapely.errors import GEOSException
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry


@dataclass(frozen=True)
class Result:
    status: str
    kind: str | None = None
    value: float | None = None
    unit: str | None = None
    projected_crs: str | None = None
    message: str | None = None


def _projected_crs(geo: BaseGeometry, kind: str) -> CRS:
    """Select UTM for local data or a locally centered projection.

    The feature must already be expressed in EPSG:4326.
    """

    west, south, east, north = geo.bounds

    center = geo.representative_point()

    longitude = center.x
    latitude = center.y

    # Validate geographic coordinates
    if not all(
        map(
            math.isfinite,
            (west, south, east, north, latitude, longitude),
        )
    ):
        raise ValueError("Non-finite geographic coordinates")

    if not (-90 <= south <= 90 and -90 <= north <= 90):
        raise ValueError("Latitude outside [-90, 90]")

    # Use local UTM projection for small geographic features
    if -80 <= latitude <= 84 and east - west <= 6 and north - south <= 6:
        zone = min(
            60,
            max(1, int((longitude + 180) // 6) + 1),
        )

        epsg_code = (32600 if latitude >= 0 else 32700) + zone

        return CRS.from_epsg(epsg_code)

    # Fallback projection for larger or polar geometries
    projection = "laea" if kind == "area" else "aeqd"

    return CRS.from_proj4(
        f"+proj={projection} +lat_0={latitude} +lon_0={longitude} +datum=WGS84 +units=m +no_defs +type=crs"
    )


def measure(
    geometry: BaseGeometry,
    original_crs: CRS,
) -> Result:
    """Calculate the area or length of a geospatial geometry.

    Polygon / MultiPolygon:
        Returns area in square meters.

    LineString / MultiLineString / LinearRing:
        Returns length in meters.

    Point / MultiPoint:
        Returns NOT_APPLICABLE.

    Invalid or unsupported geometry:
        Returns UNSUPPORTED.
    """

    # Step 1: Validate geometry
    if geometry.is_empty:
        return Result(
            status="UNSUPPORTED",
            message="Empty geometry",
        )

    if not geometry.is_valid:
        return Result(
            status="UNSUPPORTED",
            message="Invalid geometry topology",
        )

    # Step 2: Identify measurement type
    if geometry.geom_type in {"Point", "MultiPoint"}:
        return Result(
            status="NOT_APPLICABLE",
            message="Points have no area/length measurement",
        )

    if geometry.geom_type in {"Polygon", "MultiPolygon"}:
        kind = "area"
        unit = "m2"

    elif geometry.geom_type in {
        "LineString",
        "MultiLineString",
        "LinearRing",
    }:
        kind = "length"
        unit = "m"

    else:
        return Result(
            status="UNSUPPORTED",
            message=f"Unsupported geometry: {geometry.geom_type}",
        )

    # Step 3: CRS transformation and measurement
    try:
        # Convert original coordinates to geographic WGS84
        geographic_transformer = Transformer.from_crs(
            original_crs,
            CRS.from_epsg(4326),
            always_xy=True,
        )

        geographic = transform(
            geometry,
            geographic_transformer.transform,
            interleaved=False,
        )

        # Step 4: Choose an appropriate metric CRS
        projected_crs = _projected_crs(
            geographic,
            kind,
        )

        # Step 5: Convert source coordinates into metric coordinates
        projected_transformer = Transformer.from_crs(
            original_crs,
            projected_crs,
            always_xy=True,
        )

        projected = transform(
            geometry,
            projected_transformer.transform,
            interleaved=False,
        )

        # Step 6: Calculate area or length
        if kind == "area":
            value = projected.area
        else:
            value = projected.length

        # Step 7: Validate the calculated result
        if not math.isfinite(value):
            raise ValueError("Non-finite measurement")

        # Step 8: Return successful measurement
        return Result(
            status="MEASURED",
            kind=kind,
            value=round(float(value), 4),
            unit=unit,
            projected_crs=projected_crs.to_string(),
        )

    except (
        ValueError,
        OverflowError,
        ProjError,
        GEOSException,
    ) as exc:
        return Result(
            status="UNSUPPORTED",
            message=f"Could not measure geometry: {exc}",
        )


def geometry_as_json(geometry: BaseGeometry) -> dict:
    """Convert geometry into JSON-compatible GeoJSON-style data.

    Preserve original spatial coordinates while converting
    Python tuples into JSON arrays.
    """

    return json.loads(json.dumps(mapping(geometry)))
