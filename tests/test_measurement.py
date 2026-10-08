"""Coordinate science and unsupported-geometry unit tests."""

import pytest
from pyproj import CRS
from shapely.geometry import GeometryCollection, LineString, Point, Polygon
from shapely import transform
from pyproj import Transformer

from app.services.measurement import measure


def test_one_degree_line_is_not_one_meter():
    line = LineString([(77.0, 12.0), (77.0, 13.0)])
    result = measure(line, CRS.from_epsg(4326))
    assert result.status == "MEASURED"
    assert 110_000 < result.value < 112_000


def test_projected_meters_round_trip():
    poly = Polygon([(77, 12), (77.001, 12), (77.001, 12.001), (77, 12.001)])
    meter_poly = transform(
        poly,
        Transformer.from_crs(4326, 3857, always_xy=True).transform,
        interleaved=False,
    )
    from_geo = measure(poly, CRS.from_epsg(4326))
    from_mercator = measure(meter_poly, CRS.from_epsg(3857))
    assert from_geo.status == "MEASURED"
    assert from_geo.value == pytest.approx(from_mercator.value, rel=1e-7)


def test_polygon_with_hole_subtracts_area():
    outer = [(77, 12), (77.01, 12), (77.01, 12.01), (77, 12.01)]
    inner = [(77.002, 12.002), (77.008, 12.002), (77.008, 12.008), (77.002, 12.008)]
    with_hole = measure(Polygon(outer, [inner]), CRS.from_epsg(4326))
    without_hole = measure(Polygon(outer), CRS.from_epsg(4326))
    assert with_hole.value < without_hole.value


def test_empty_or_unsupported_geometry():
    assert measure(GeometryCollection(), CRS.from_epsg(4326)).status == "UNSUPPORTED"
    assert (
        measure(GeometryCollection([Point(1, 1), Point(2, 2)]), CRS.from_epsg(4326)).status == "UNSUPPORTED"
    )
    assert measure(Point(77, 12), CRS.from_epsg(4326)).status == "NOT_APPLICABLE"


def test_polar_fallback():
    line = LineString([(10, 85), (10.001, 85.001)])
    result = measure(line, CRS.from_epsg(4326))
    assert result.status == "MEASURED"
    assert "+proj=aeqd" in result.projected_crs
    assert 100 < result.value < 120


def test_large_polygon_fallback():
    poly = Polygon([(70, 10), (85, 10), (85, 20), (70, 20)])
    result = measure(poly, CRS.from_epsg(4326))
    assert result.status == "MEASURED"
    assert "+proj=laea" in result.projected_crs
    assert result.value > 0
