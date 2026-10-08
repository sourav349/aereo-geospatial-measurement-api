"""Parse untrusted uploaded KML and zipped Shapefiles without extracting to disk."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
import zipfile
from typing import Any

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException
from fastapi.encoders import jsonable_encoder
from pyproj import CRS
import shapefile
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
    shape,
)
from shapely.geometry.base import BaseGeometry

from app.config import Settings
from app.errors import InputError


@dataclass
class ParsedFeature:
    identifier: str | None
    geometry: BaseGeometry
    properties: dict[str, Any]


@dataclass
class ParsedFile:
    crs: CRS
    features: list[ParsedFeature]
    file_format: str


def _name(element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _children(element, tag: str):
    return [child for child in element if _name(child) == tag]


def _child(element, tag: str):
    return next(iter(_children(element, tag)), None)


def _path(element, *tags: str):
    current = element
    for tag in tags:
        if current is None:
            return None
        current = _child(current, tag)
    return current


def _coords(value: str | None) -> list[tuple[float, float]]:
    if not value or not value.strip():
        raise InputError("KML geometry has no coordinates")
    points = []
    for part in value.split():
        pieces = part.split(",")
        if len(pieces) < 2:
            raise InputError("Invalid KML coordinate tuple")
        try:
            points.append((float(pieces[0]), float(pieces[1])))
        except ValueError as exc:
            raise InputError("Invalid numeric KML coordinate") from exc
    return points


def _geometry(node) -> BaseGeometry:
    tag = _name(node)
    if tag == "Point":
        pts = _coords(_path(node, "coordinates").text if _path(node, "coordinates") is not None else None)
        if len(pts) != 1:
            raise InputError("KML Point must contain exactly one coordinate")
        return Point(pts[0])
    if tag == "LineString":
        elem = _path(node, "coordinates")
        pts = _coords(elem.text if elem is not None else None)
        if len(pts) < 2:
            raise InputError("KML LineString needs at least two coordinates")
        return LineString(pts)
    if tag == "Polygon":
        outer = _path(node, "outerBoundaryIs", "LinearRing", "coordinates")
        exterior = _coords(outer.text if outer is not None else None)
        if len(exterior) < 3:
            raise InputError("KML Polygon requires at least three coordinates")
        holes = []
        for inner in _children(node, "innerBoundaryIs"):
            coords = _path(inner, "LinearRing", "coordinates")
            holes.append(_coords(coords.text if coords is not None else None))
        return Polygon(exterior, holes)
    if tag == "MultiGeometry":
        items = [
            _geometry(item)
            for item in node
            if _name(item) in {"Point", "LineString", "Polygon", "MultiGeometry"}
        ]
        # Homogeneous KML MultiGeometry maps naturally to measurable collections.
        if items and all(item.geom_type == "Polygon" for item in items):
            return MultiPolygon(items)
        if items and all(item.geom_type == "LineString" for item in items):
            return MultiLineString(items)
        if items and all(item.geom_type == "Point" for item in items):
            return MultiPoint(items)
        return GeometryCollection(items)
    raise InputError(f"Unsupported KML geometry element: {tag}")


def _kml_properties(placemark) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for key in ("name", "description"):
        element = _child(placemark, key)
        if element is not None and element.text:
            properties[key] = element.text.strip()
    ext = _child(placemark, "ExtendedData")
    if ext is not None:
        for node in ext.iter():
            if _name(node) == "Data" and node.attrib.get("name"):
                val = _child(node, "value")
                properties[node.attrib["name"]] = (val.text or "") if val is not None else ""
            if _name(node) == "SimpleData" and node.attrib.get("name"):
                properties[node.attrib["name"]] = (node.text or "").strip()
    return properties


def parse_kml(data: bytes, settings: Settings) -> ParsedFile:
    try:
        root = SafeET.fromstring(data)
    except (SafeET.ParseError, ValueError, DefusedXmlException) as exc:
        raise InputError("Invalid or unsafe KML XML") from exc
    if _name(root) != "kml":
        raise InputError("Expected a KML document")
    placemarks = (node for node in root.iter() if _name(node) == "Placemark")
    features: list[ParsedFeature] = []
    for pm in placemarks:
        if len(features) >= settings.max_features:
            raise InputError("Too many features in file", status_code=413)
        geometry_nodes = [
            node for node in pm if _name(node) in {"Point", "LineString", "Polygon", "MultiGeometry"}
        ]
        if not geometry_nodes:
            continue
        try:
            geometry = (
                _geometry(geometry_nodes[0])
                if len(geometry_nodes) == 1
                else GeometryCollection([_geometry(n) for n in geometry_nodes])
            )
        except (TypeError, ValueError) as exc:
            raise InputError("Invalid KML geometry") from exc
        features.append(ParsedFeature(pm.attrib.get("id"), geometry, _kml_properties(pm)))
    if not features:
        raise InputError("No supported geometries found in KML")
    # Per OGC KML specification, longitude/latitude coordinates use WGS84.
    return ParsedFile(CRS.from_epsg(4326), features, "KML")


def _validate_zip_member(name: str) -> None:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or "\x00" in name or name.startswith("\\"):
        raise InputError("Unsafe filename inside ZIP archive")
    if any(part.endswith(":") for part in path.parts):
        raise InputError("Unsafe filename inside ZIP archive")


def parse_shapefile_zip(data: bytes, settings: Settings) -> ParsedFile:
    try:
        archive = zipfile.ZipFile(BytesIO(data))
    except (zipfile.BadZipFile, ValueError) as exc:
        raise InputError("Invalid ZIP archive") from exc

    with archive:
        members = [item for item in archive.infolist() if not item.is_dir()]
        if len(members) > settings.max_zip_members:
            raise InputError("ZIP archive contains too many files", status_code=413)
        for item in members:
            _validate_zip_member(item.filename)
        if sum(item.file_size for item in members) > settings.max_uncompressed_bytes:
            raise InputError("Uncompressed ZIP contents exceed size limit", status_code=413)
        by_name = {item.filename.lower(): item for item in members}
        shp_items = [item for item in members if item.filename.lower().endswith(".shp")]
        if len(shp_items) != 1:
            raise InputError("ZIP must contain exactly one .shp file")
        shp_member = shp_items[0]
        base = shp_member.filename[:-4].lower()
        needed = {extension: by_name.get(base + extension) for extension in (".shp", ".shx", ".dbf", ".prj")}
        if any(value is None for value in needed.values()):
            raise InputError("Shapefile must include .shp, .shx, .dbf and .prj files")
        try:
            wkt = archive.read(needed[".prj"]).decode("utf-8-sig").strip()
            crs = CRS.from_wkt(wkt)
        except (UnicodeError, ValueError) as exc:
            raise InputError("Missing or invalid Shapefile CRS (.prj)") from exc
        cpg_member = by_name.get(base + ".cpg")
        encoding = archive.read(cpg_member).decode("ascii", "replace").strip() if cpg_member else "utf-8"
        if not encoding:
            encoding = "utf-8"
        try:
            reader = shapefile.Reader(
                shp=BytesIO(archive.read(needed[".shp"])),
                shx=BytesIO(archive.read(needed[".shx"])),
                dbf=BytesIO(archive.read(needed[".dbf"])),
                encoding=encoding,
            )
            if len(reader) > settings.max_features:
                raise InputError("Too many features in file", status_code=413)
            features: list[ParsedFeature] = []
            for idx, record in enumerate(reader.iterShapeRecords()):
                # NULL Shape is a legal Shapefile record; keep it as unsupported.
                if record.shape.shapeType == shapefile.NULL:
                    geo = GeometryCollection()
                else:
                    geo = shape(record.shape.__geo_interface__)
                # DBF date values are native Python dates; persist ISO strings in JSON.
                attributes = jsonable_encoder(record.record.as_dict())
                features.append(ParsedFeature(str(idx), geo, attributes))
            reader.close()
        except InputError:
            raise
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            UnicodeError,
            EOFError,
            zipfile.BadZipFile,
            shapefile.ShapefileException,
        ) as exc:
            raise InputError("Invalid or damaged Shapefile components") from exc
        if not features:
            raise InputError("Shapefile contains no features")
    return ParsedFile(crs, features, "SHAPEFILE")


def parse_file(filename: str, data: bytes, settings: Settings) -> ParsedFile:
    lower = filename.lower()
    if lower.endswith(".kml"):
        return parse_kml(data, settings)
    if lower.endswith(".zip"):
        return parse_shapefile_zip(data, settings)
    raise InputError("Only .kml and .zip (containing Shapefile) are accepted", status_code=415)
