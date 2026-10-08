"""Generate a minimal real zipped Shapefile for manual API testing.

Run from repository root: `python scripts/create_sample_shapefile.py`
"""
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from pyproj import CRS
import shapefile


def main() -> None:
    shp, shx, dbf = BytesIO(), BytesIO(), BytesIO()
    writer = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POLYGON)
    writer.field("site", "C", size=40)
    writer.poly([[
        [77.5900, 12.9700], [77.5900, 12.9710], [77.5910, 12.9710],
        [77.5910, 12.9700], [77.5900, 12.9700],
    ]])
    writer.record("Survey plot")
    writer.close()

    output = Path(__file__).resolve().parents[1] / "samples" / "example-shapefile.zip"
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("survey.shp", shp.getvalue())
        archive.writestr("survey.shx", shx.getvalue())
        archive.writestr("survey.dbf", dbf.getvalue())
        archive.writestr("survey.prj", CRS.from_epsg(4326).to_wkt(version="WKT1_ESRI"))
    print(f"Created {output.relative_to(Path.cwd())} ({output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
