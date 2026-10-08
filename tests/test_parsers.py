"""Shapefile/KML defensive ingestion tests."""

from dataclasses import replace
from io import BytesIO
import zipfile

import pytest

from app.config import Settings
from app.errors import InputError
from app.services.parsers import parse_kml, parse_shapefile_zip
from .helpers import KML_SAMPLE, shapefile_archive


def test_kml_metadata_and_coordinates():
    result = parse_kml(KML_SAMPLE, Settings())
    assert result.crs.to_epsg() == 4326
    assert result.features[0].identifier == "zone-1"
    assert result.features[0].properties["name"] == "Mining plot"
    assert result.features[0].properties["owner"] == "AEREO"
    assert result.features[0].geometry.geom_type == "Polygon"


def test_file_feature_count_limit():
    with pytest.raises(InputError, match="Too many features"):
        parse_kml(KML_SAMPLE, replace(Settings(), max_features=2))


def test_shapefile_size_limit():
    with pytest.raises(InputError, match="Uncompressed ZIP"):
        parse_shapefile_zip(shapefile_archive(), replace(Settings(), max_uncompressed_bytes=50))


def test_polygon_hole_kml():
    content = b"""<kml><Placemark><Polygon>
     <outerBoundaryIs><LinearRing><coordinates>0,0 1,0 1,1 0,1 0,0</coordinates></LinearRing></outerBoundaryIs>
     <innerBoundaryIs><LinearRing><coordinates>0.2,0.2 0.8,0.2 0.8,0.8 0.2,0.8 0.2,0.2</coordinates></LinearRing></innerBoundaryIs>
     </Polygon></Placemark></kml>"""
    result = parse_kml(content, Settings())
    assert len(result.features[0].geometry.interiors) == 1


def test_backslash_zip_traversal_rejected():
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("..\\evil.shp", b"bad")
    with pytest.raises(InputError, match="Unsafe"):
        parse_shapefile_zip(buf.getvalue(), Settings())
