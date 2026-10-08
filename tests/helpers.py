"""Construct realistic geospatial fixtures entirely in memory."""

from io import BytesIO
import zipfile

from pyproj import CRS
import shapefile


KML_SAMPLE = b"""<?xml version="1.0"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
  <Placemark id="zone-1"><name>Mining plot</name>
    <ExtendedData><Data name="owner"><value>AEREO</value></Data></ExtendedData>
    <Polygon><outerBoundaryIs><LinearRing><coordinates>
      77.59,12.97 77.591,12.97 77.591,12.971 77.59,12.971 77.59,12.97
    </coordinates></LinearRing></outerBoundaryIs></Polygon>
  </Placemark>
  <Placemark id="route-1"><name>Survey route</name>
    <LineString><coordinates>77.59,12.97 77.591,12.97</coordinates></LineString>
  </Placemark>
  <Placemark id="beacon-1"><name>Station</name>
    <Point><coordinates>77.59,12.97</coordinates></Point>
  </Placemark>
</Document>
</kml>"""


def shapefile_archive(*, with_prj: bool = True, crs_epsg: int = 4326) -> bytes:
    """A zipped polygon shapefile with an ESRI projection definition."""
    shp, shx, dbf = BytesIO(), BytesIO(), BytesIO()
    writer = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POLYGON)
    writer.field("zone", "C", size=30)
    if crs_epsg == 4326:
        # Clockwise exterior for proper Shapefile ring semantics.
        ring = [[77.59, 12.97], [77.59, 12.971], [77.591, 12.971], [77.591, 12.97], [77.59, 12.97]]
    else:
        ring = [[100000, 100000], [100000, 100100], [100100, 100100], [100100, 100000], [100000, 100000]]
    writer.poly([ring])
    writer.record("Zone A")
    writer.close()
    parts = {"area.shp": shp.getvalue(), "area.shx": shx.getvalue(), "area.dbf": dbf.getvalue()}
    if with_prj:
        parts["area.prj"] = CRS.from_epsg(crs_epsg).to_wkt(version="WKT1_ESRI").encode("utf-8")
    target = BytesIO()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():
            z.writestr(name, data)
    return target.getvalue()
