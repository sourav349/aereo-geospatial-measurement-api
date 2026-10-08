"""Black-box coverage of all three assignment endpoints."""

from io import BytesIO
import zipfile

from .helpers import KML_SAMPLE, shapefile_archive


def upload(client, name="survey.kml", data=KML_SAMPLE):
    return client.post("/api/files/", files={"file": (name, data, "application/octet-stream")})


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_upload_kml_and_get_metadata_and_measurements(client):
    response = upload(client)
    assert response.status_code == 201, response.text
    meta = response.json()
    assert meta["filename"] == "survey.kml"
    assert meta["feature_count"] == 3
    assert meta["crs"] == "EPSG:4326"
    assert meta["status"] == "COMPLETED"
    fid = meta["id"]

    info = client.get(f"/api/files/{fid}/")
    assert info.status_code == 200
    assert info.json() == meta

    resp = client.get(f"/api/files/{fid}/measurements/")
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["total"] == 3
    poly, line, point = result["measurements"]
    assert poly["feature_id"] == "zone-1"
    assert poly["properties"]["owner"] == "AEREO"
    assert poly["geometry"]["type"] == "Polygon"
    assert poly["geometry_type"] == "Polygon"
    assert poly["measurement"]["status"] == "MEASURED"
    assert poly["measurement"]["type"] == "area"
    assert poly["measurement"]["unit"] == "m2"
    assert 10_000 < poly["measurement"]["value"] < 14_000
    assert poly["measurement"]["projected_crs"].startswith("EPSG:326")
    assert line["geometry_type"] == "LineString"
    assert line["measurement"]["type"] == "length"
    assert line["measurement"]["unit"] == "m"
    assert 100 < line["measurement"]["value"] < 120
    assert point["geometry_type"] == "Point"
    assert point["measurement"]["status"] == "NOT_APPLICABLE"
    assert point["measurement"]["value"] is None


def test_upload_shapefile_zip(client):
    response = upload(client, "survey.zip", shapefile_archive())
    assert response.status_code == 201, response.text
    info = response.json()
    assert info["file_format"] == "SHAPEFILE"
    assert info["feature_count"] == 1
    feature = client.get(f"/api/files/{info['id']}/measurements/").json()["measurements"][0]
    assert feature["properties"]["zone"] == "Zone A"
    assert feature["measurement"]["status"] == "MEASURED"
    assert feature["measurement"]["type"] == "area"
    assert feature["measurement"]["value"] > 0


def test_shapefile_projected_input(client):
    response = upload(client, "area.zip", shapefile_archive(crs_epsg=3857))
    assert response.status_code == 201, response.text
    info = response.json()
    assert info["crs"] == "EPSG:3857"
    feature = client.get(f"/api/files/{info['id']}/measurements/").json()["measurements"][0]
    # Projection is not blindly treated as degrees, nor are coordinates treated as already UTM.
    assert 9000 < feature["measurement"]["value"] < 11000


def test_pagination(client):
    fid = upload(client).json()["id"]
    response = client.get(f"/api/files/{fid}/measurements/?offset=1&limit=1")
    assert response.status_code == 200
    assert response.json()["total"] == 3
    assert len(response.json()["measurements"]) == 1
    assert response.json()["measurements"][0]["geometry_type"] == "LineString"
    assert client.get(f"/api/files/{fid}/measurements/?limit=501").status_code == 422


def test_unknown_file_is_404(client):
    assert client.get("/api/files/nonexistent/").status_code == 404
    assert client.get("/api/files/nonexistent/measurements/").status_code == 404


def test_invalid_file_type(client):
    response = upload(client, "bad.txt", b"hello")
    assert response.status_code == 415


def test_empty_upload(client):
    assert upload(client, "empty.kml", b"").status_code == 422


def test_invalid_xml(client):
    assert upload(client, "bad.kml", b"<kml><Placemark>").status_code == 422


def test_reject_xml_entity_expansion(client):
    xml = b'<!DOCTYPE kml [<!ENTITY boom "bad">]><kml><Placemark><name>&boom;</name></Placemark></kml>'
    assert upload(client, "bad.kml", xml).status_code == 422


def test_invalid_archive(client):
    assert upload(client, "bad.zip", b"not-a-zip").status_code == 422


def test_missing_prj(client):
    response = upload(client, "no-crs.zip", shapefile_archive(with_prj=False))
    assert response.status_code == 422
    assert ".prj" in response.json()["detail"]


def test_zip_traversal_rejected(client):
    archive = BytesIO()
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("../evil.shp", b"malicious")
    response = upload(client, "evil.zip", archive.getvalue())
    assert response.status_code == 422
    assert "Unsafe" in response.json()["detail"]


def test_multi_geometry_unsupported_without_crashing(client):
    data = b"""<kml><Document><Placemark id="multi"><MultiGeometry>
    <Point><coordinates>77,12</coordinates></Point>
    <LineString><coordinates>77,12 77.01,12.01</coordinates></LineString>
    </MultiGeometry></Placemark></Document></kml>"""
    response = upload(client, "multi.kml", data)
    assert response.status_code == 201, response.text
    fid = response.json()["id"]
    measurement = client.get(f"/api/files/{fid}/measurements/").json()["measurements"][0]
    assert measurement["geometry_type"] == "GeometryCollection"
    assert measurement["measurement"]["status"] == "UNSUPPORTED"


def test_invalid_geometry_does_not_abort_other_features(client):
    # A self-intersecting polygon is not measured, but a valid sibling still is.
    data = b"""<kml><Document>
      <Placemark><Polygon><outerBoundaryIs><LinearRing><coordinates>
      77,12 78,13 78,12 77,13 77,12
      </coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
      <Placemark><Point><coordinates>77,12</coordinates></Point></Placemark>
    </Document></kml>"""
    res = upload(client, "bowtie.kml", data)
    assert res.status_code == 201, res.text
    fid = res.json()["id"]
    rows = client.get(f"/api/files/{fid}/measurements/").json()["measurements"]
    assert rows[0]["measurement"]["status"] == "UNSUPPORTED"
    assert rows[1]["measurement"]["status"] == "NOT_APPLICABLE"


def test_missing_file_param(client):
    assert client.post("/api/files/").status_code == 422


def test_homogeneous_kml_multi_polygon_is_measured(client):
    polygon = b"""<Polygon><outerBoundaryIs><LinearRing><coordinates>
    77,12 77.001,12 77.001,12.001 77,12.001 77,12
    </coordinates></LinearRing></outerBoundaryIs></Polygon>"""
    polygon2 = polygon.replace(b"77,12", b"77.002,12").replace(b"77.001,12", b"77.003,12")
    data = b"<kml><Placemark><MultiGeometry>" + polygon + polygon2 + b"</MultiGeometry></Placemark></kml>"
    response = upload(client, "multi.kml", data)
    assert response.status_code == 201, response.text
    fid = response.json()["id"]
    result = client.get(f"/api/files/{fid}/measurements/").json()["measurements"][0]
    assert result["geometry_type"] == "MultiPolygon"
    assert result["measurement"]["status"] == "MEASURED"
    assert result["measurement"]["unit"] == "m2"


def test_upload_size_limit_is_enforced(client):
    from dataclasses import replace

    client.app.state.settings = replace(client.app.state.settings, max_upload_bytes=50)
    response = upload(client)
    assert response.status_code == 413


def test_payload_rejects_missing_file_geometries(client):
    data = b"<kml><Document><name>No features</name></Document></kml>"
    response = upload(client, "empty.kml", data)
    assert response.status_code == 422


def test_kml_filepath_sanitized(client):
    response = upload(client, "folder\\survey.kml", KML_SAMPLE)
    assert response.status_code == 201
    assert response.json()["filename"] == "survey.kml"
