# AEREO Geospatial File Measurement API

A Python **FastAPI** backend that accepts **KML** and **zipped ESRI Shapefiles**, extracts geospatial features, and calculates **polygon area** and **line length** using coordinate reference system (CRS) transformations.

Built as a practical engineering submission for **AEREO — Software Development Engineer Intern**. This repository emphasizes clear API contracts, correct spatial calculations, defensive file parsing, database persistence, automated tests, and maintainable Python code.

> **Project scope:** This is a locally runnable engineering assignment, not a publicly deployed service. Processing is synchronous and intentionally bounded by upload, archive, and feature limits. Authentication, rate limiting, and production infrastructure are not implemented.

## Contents

- [Features](#features)
- [Technology stack](#technology-stack)
- [Prerequisites](#prerequisites)
- [Mac M5 / Apple Silicon setup](#mac-m5--apple-silicon-setup)
- [Run with Docker](#run-with-docker)
- [API endpoints](#api-endpoints)
- [Try the sample files](#try-the-sample-files)
- [Example API responses](#example-api-responses)
- [System architecture](#system-architecture)
- [CRS and measurement logic](#crs-and-measurement-logic)
- [Supported geometries](#supported-geometries)
- [Database design](#database-design)
- [Validation and error handling](#validation-and-error-handling)
- [Configuration](#configuration)
- [Tests and code quality](#tests-and-code-quality)
- [Project structure](#project-structure)
- [Design decisions](#design-decisions)
- [Troubleshooting on macOS](#troubleshooting-on-macos)
- [Limitations and future work](#limitations-and-future-work)
- [Learnings](#learnings)
- [GitHub submission](#github-submission)

## Features

- Upload a `.kml` file or a `.zip` archive containing an ESRI Shapefile.
- Read feature identifiers, geometry types, coordinates, source CRS, and attributes.
- Measure areas of `Polygon`/`MultiPolygon` features in **square meters (m²)**.
- Measure lengths of `LineString`/`MultiLineString`/`LinearRing` features in **meters (m)**.
- Return `NOT_APPLICABLE` for point measurements; keep unsupported/invalid geometries with a readable reason.
- Choose a suitable projected metric CRS rather than measuring latitude/longitude in degrees.
- Persist file metadata and individual results using SQLAlchemy and SQLite.
- Provide paginated measurement retrieval via REST APIs.
- Validate archive contents and limit potentially unsafe uploads.
- Include example input files, automated tests, Docker support, and GitHub Actions CI.

## Technology stack

| Component | Choice | Purpose |
| --- | --- | --- |
| Language | Python 3.12 (recommended locally) | Application and processing logic |
| API framework | FastAPI + Pydantic | Endpoints, validation, OpenAPI docs |
| Database | SQLite + SQLAlchemy 2 | Relational persistence for local execution |
| Spatial geometry | Shapely 2 | Geometry handling and planar measurements |
| CRS transformations | PyProj | Coordinate transformations and projection selection |
| Shapefile reader | pyshp | Parse zipped Shapefile components |
| KML parsing | defusedxml | Parse KML with protections against unsafe XML entities |
| Testing | Pytest + HTTPX | API, parser, and measurement tests |
| Optional deployment | Docker Compose | Reproducible containerized execution |
| CI | GitHub Actions | Test on Python 3.12 and 3.13 |

**Note for Apple Silicon:** This project does **not** require GeoPandas, Fiona, or a separate GDAL installation. Use an ARM64 Python environment for the smoothest Mac M5 setup.

## Prerequisites

For a local Mac installation:

- macOS on Apple Silicon (M5, M4, M3, M2, or M1); Intel macOS can also work.
- Terminal or VS Code terminal.
- Python **3.12** and `pip`.
- Git (for source control).
- Internet access for initial package installation.

Optional: Docker Desktop for Apple Silicon if using the container method.

## Mac M5 / Apple Silicon setup

### 1. Install Homebrew if it is not installed

Check:

```bash
brew --version
```

If that fails, install Homebrew:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

If Terminal still cannot find `brew`, initialize the usual Apple Silicon Homebrew location:

```bash
eval "$(/opt/homebrew/bin/brew shellenv)"
```

Follow any Homebrew instructions printed by the installer to make that configuration persistent.

### 2. Install Python 3.12 and Git

```bash
brew update
brew install python@3.12 git
```

Verify versions and architecture:

```bash
python3.12 --version
git --version
uname -m
python3.12 -c "import platform; print(platform.machine())"
```

On an M5 Mac, both architecture checks should normally report `arm64`. Avoid mixing a Rosetta/Intel Python with native ARM64 packages.

### 3. Download and extract the repository

If you received the project as `aereo-geospatial-measurement-api.zip`, put it in `~/Downloads` and run:

```bash
cd ~/Downloads
unzip aereo-geospatial-measurement-api.zip
cd aereo-geospatial-measurement-api
```

If you cloned from GitHub instead, enter the cloned repository directory. Run all subsequent commands **from the project root**, where `requirements-dev.txt` exists.

### 4. Create and activate a Python virtual environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

You should now see `(.venv)` in the terminal. Check that the active Python is the virtual environment's Python:

```bash
python --version
python -c "import platform, sys; print(platform.machine()); print(sys.executable)"
```

### 5. Install project dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

The developer requirements include the runtime dependencies, Pytest, HTTPX, and Ruff.

### 6. Start the API

```bash
python -m uvicorn app.main:app --reload
```

Visit:

- **Swagger UI:** http://127.0.0.1:8000/docs
- **OpenAPI schema:** http://127.0.0.1:8000/openapi.json
- **Health check:** http://127.0.0.1:8000/health

A local SQLite database named `geospatial.db` is created in the working directory at startup. It is ignored by Git.

To stop the application, press **Control + C**.

### 7. Optional: Open in VS Code

```bash
code .
```

In VS Code, run **Command + Shift + P → Python: Select Interpreter** and select `.venv/bin/python`. If `code` is not found, launch VS Code normally and install its shell command from VS Code's Command Palette.

## Run with Docker

If you have **Docker Desktop for Apple Silicon** installed and running, you can run the backend without creating a local virtual environment:

```bash
docker compose up --build
```

Open http://localhost:8000/docs.

Stop:

```bash
docker compose down
```

Docker Compose uses a named volume (`geospatial_data`) for the SQLite database. `docker compose down` does not normally remove this volume; `docker compose down -v` **does delete the stored data**.

> Run the local Python server **or** Docker server on port 8000, not both at the same time.

## API endpoints

| Method | Endpoint | Description | Successful response |
| --- | --- | --- | --- |
| `POST` | `/api/files/` | Upload and process KML or zipped Shapefile | `201 Created` |
| `GET` | `/api/files/{id}/` | Retrieve uploaded file metadata | `200 OK` |
| `GET` | `/api/files/{id}/measurements/` | Retrieve feature details and measurements | `200 OK` |
| `GET` | `/health` | Basic application health response | `200 OK` |

The upload request is `multipart/form-data` with form field **`file`**.

A valid Shapefile ZIP contains **exactly one** `.shp` file and matching `.shx`, `.dbf`, and `.prj` components sharing the same filename stem. A matching `.cpg` encoding file is optional. The `.prj` is necessary to determine the source CRS.

### Pagination

The measurements endpoint supports:

| Query parameter | Default | Validation |
| --- | --- | --- |
| `offset` | `0` | Must be `>= 0` |
| `limit` | `100` | Between `1` and `500` |

The response's `total` is the total number of features in that upload, not merely the number returned in the current page.

## Try the sample files

Keep the FastAPI server running in the first Terminal window. Open a **second Terminal** in the project directory for these requests.

### Upload sample KML

The included KML contains a polygon, a line, and a point around Bengaluru:

```bash
curl -X POST 'http://127.0.0.1:8000/api/files/' \
  -F 'file=@samples/example.kml'
```

### Upload sample zipped Shapefile

```bash
curl -X POST 'http://127.0.0.1:8000/api/files/' \
  -F 'file=@samples/example-shapefile.zip'
```

Each successful upload returns a unique `id`. Copy the ID from the response, then run:

```bash
# Replace YOUR_FILE_ID with the UUID from your upload response.
curl 'http://127.0.0.1:8000/api/files/YOUR_FILE_ID/'
curl 'http://127.0.0.1:8000/api/files/YOUR_FILE_ID/measurements/'
curl 'http://127.0.0.1:8000/api/files/YOUR_FILE_ID/measurements/?offset=0&limit=25'
```

You can also test uploads, parameters, and responses directly in the interactive `/docs` interface using **Try it out**.

## Example API responses

The IDs, timestamps, and measurement values below are **illustrative**, not guaranteed outputs from a particular run.

### `POST /api/files/`

```json
{
  "id": "8ee6ff6d-19f6-4c46-b4d4-4c62faed5c35",
  "filename": "example.kml",
  "file_format": "KML",
  "crs": "EPSG:4326",
  "feature_count": 3,
  "status": "COMPLETED",
  "created_at": "2026-10-08T08:00:00Z"
}
```

### `GET /api/files/{id}/measurements/`

A shortened response showing **one** of three features:

```json
{
  "file_id": "8ee6ff6d-19f6-4c46-b4d4-4c62faed5c35",
  "total": 3,
  "offset": 0,
  "limit": 100,
  "measurements": [
    {
      "feature_index": 0,
      "feature_id": "plot-01",
      "geometry_type": "Polygon",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[77.59, 12.97], [77.591, 12.97], [77.591, 12.971], [77.59, 12.971], [77.59, 12.97]]]
      },
      "crs": "EPSG:4326",
      "properties": {
        "name": "Survey plot",
        "site": "Bengaluru"
      },
      "measurement": {
        "status": "MEASURED",
        "type": "area",
        "value": 12016.9702,
        "unit": "m2",
        "projected_crs": "EPSG:32643",
        "message": null
      }
    }
  ]
}
```

The complete response for `example.kml` normally includes polygon, line, and point entries. For a point, the measurement status is `NOT_APPLICABLE`, the value is `null`, and a message explains why.

## System architecture

```mermaid
flowchart TD
    Client[Swagger UI / REST Client] --> API[FastAPI Upload Endpoint]
    API --> Validate[Extension / Size / Archive Validation]
    Validate --> Format{File Type}
    Format -->|KML| KML[defusedxml KML Parser]
    Format -->|ZIP Shapefile| SHP[pyshp Shapefile Parser]
    KML --> Features[Normalized Geometry, Attributes, CRS]
    SHP --> Features
    Features --> Measure[Shapely + PyProj Measurement Service]
    Measure --> DB[(SQLAlchemy / SQLite)]
    DB --> Read[File Info and Measurements APIs]
    Read --> Client
```

### Processing sequence

1. **Receive** the multipart upload in `POST /api/files/`.
2. **Validate** filename extension, nonempty payload, file-size limit, and archive contents.
3. **Parse** the KML or zipped Shapefile into normalized features.
4. **Identify** each feature's geometry type, properties, and source CRS.
5. **Select** an appropriate projected CRS for measurable features.
6. **Transform and measure** geometry: area in m² or length in m.
7. **Persist** the file record and associated feature records in a single database transaction.
8. **Return** a file ID and make the stored results accessible through GET endpoints.

## CRS and measurement logic

**CRS (Coordinate Reference System)** describes how coordinates correspond to geographic locations. For example, `EPSG:4326` stores longitude and latitude in **degrees**, not meters.

Directly calling `.area` or `.length` on geometry coordinates expressed in degrees gives values in square degrees or degrees—not meaningful square meters or meters.

For supported geometry types, the measurement service:

1. Reads the source CRS (`EPSG:4326` for KML; parsed from `.prj` for Shapefile).
2. Transforms a copy of the geometry to geographic WGS84 to determine a suitable local projection.
3. Uses a local **UTM** zone when the geometry has a relatively small geographic extent (no more than 6° longitude and 6° latitude) and its center lies in the usual UTM latitude range.
4. For larger or polar features, chooses a locally centered **Lambert Azimuthal Equal Area (LAEA)** projection for area or **Azimuthal Equidistant (AEQD)** projection for length.
5. Transforms the geometry from the original CRS into the chosen metric CRS with `pyproj.Transformer` and `always_xy=True`.
6. Calculates planar area or length using Shapely, rounds to four decimal places, and records the chosen projected CRS with the result.

**Example:** A polygon near Bengaluru with a WGS84 source CRS can be measured in a locally appropriate UTM projection such as `EPSG:32643` (UTM Zone 43N).

**Accuracy limitation:** Projection-based planar measurements introduce distortion, particularly across very large regions or around the antimeridian. The implementation is appropriate as a practical local/regional demo; it does not claim universal survey-grade accuracy. KML altitude is ignored because the assignment requests 2D measurements.

## Supported geometries

| Geometry type | Behavior | Unit |
| --- | --- | --- |
| `Polygon` | Calculate projected area | `m2` |
| `MultiPolygon` | Calculate total projected area | `m2` |
| `LineString` | Calculate projected length | `m` |
| `MultiLineString` | Calculate total projected length | `m` |
| `LinearRing` | Calculate projected length when present | `m` |
| `Point`, `MultiPoint` | No measurement applicable | — |
| Other / empty / invalid geometry | Preserve feature with `UNSUPPORTED` status and reason | — |

The original geometry coordinates and CRS remain in the result. Only a temporary transformed copy is measured.

## Database design

SQLAlchemy models implement two tables:

**`geo_files`** stores an upload's UUID, filename, format, source CRS, feature count, completion status, and creation timestamp.

**`geo_features`** stores the parent file ID, feature index/identifier, geometry type, geometry JSON, source attributes, measurement status/type/value/unit, projected CRS, and an optional error message.

Relationship: **one `geo_files` row → many `geo_features` rows**, using `geo_features.file_id` as the foreign key.

The API commits file metadata and feature results together. An unexpected persistence error triggers a rollback rather than leaving a partly committed completed file.

## Validation and error handling

| HTTP status | Condition | Example |
| --- | --- | --- |
| `201` | File successfully processed | Upload returns file ID |
| `404` | File ID does not exist | `File not found` |
| `413` | Configured size/member/feature limit exceeded | Upload too large |
| `415` | File extension is unsupported | `.txt` instead of `.kml` or `.zip` |
| `422` | Missing file parameter, invalid KML/ZIP, bad geometry input, missing/invalid `.prj`, or invalid query parameters | Descriptive `detail` response |

Protective checks include:

- Maximum incoming file payload: **10 MiB** by default, read in bounded chunks.
- Maximum total uncompressed ZIP member sizes: **50 MiB** by default.
- Maximum entries in a ZIP: **100** by default.
- Maximum features per upload: **5,000** by default.
- No archive extraction to arbitrary filesystem paths; ZIP member paths are screened for traversal.
- KML is parsed through `defusedxml`, with unsafe XML constructs rejected.
- Invalid or unsupported *individual* geometries do not stop other valid features from being measured.

> **Security boundary:** These checks reduce some common file-ingestion risks but are **not** a substitute for authentication, rate limiting, comprehensive resource controls, security review, and secure hosting. Do not expose this demo to arbitrary public uploads unchanged.

## Configuration

The application reads environment variables directly. Defaults are:

| Variable | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./geospatial.db` | SQLAlchemy database connection |
| `MAX_UPLOAD_BYTES` | `10485760` | Incoming payload limit (10 MiB) |
| `MAX_UNCOMPRESSED_BYTES` | `52428800` | ZIP uncompressed-size limit (50 MiB) |
| `MAX_FEATURES` | `5000` | Maximum number of features |
| `MAX_ZIP_MEMBERS` | `100` | Maximum entries in a ZIP |

The `.env.example` file is a reference template. **The application does not automatically load `.env` files.** To change settings, export environment variables in the shell before starting it. For example:

```bash
export MAX_FEATURES=3000
export DATABASE_URL='sqlite:///./geospatial.db'
python -m uvicorn app.main:app --reload
```

### Optional PostgreSQL

SQLite is sufficient for this assignment. To use a running PostgreSQL database:

```bash
python -m pip install -r requirements-postgres.txt
export DATABASE_URL='postgresql+psycopg://USER:PASSWORD@HOST:5432/geospatial'
python -m uvicorn app.main:app
```

Replace the placeholders with your actual PostgreSQL connection details. The database and permissions must already exist. This code uses SQLAlchemy `create_all()` at startup; a production deployment should use a migration tool such as Alembic.

## Tests and code quality

From the repository root, with the virtual environment active:

```bash
python -m pytest -v
python -m pytest -q
python -m compileall -q app
```

The test suite covers:

- Uploading KML and zipped Shapefile files.
- Reading metadata and measurements through all assignment endpoints.
- Correct handling of geographic and projected input CRS.
- Polygon/line measurements and polygons with holes.
- Point and unsupported geometry behavior.
- Invalid XML, ZIP archives, missing `.prj`, and suspicious archive paths.
- Upload/feature limits and malformed input.
- Pagination and unknown file IDs.

Optional Ruff checks:

```bash
python -m ruff check .
```

GitHub Actions (`.github/workflows/ci.yml`) executes Pytest on Python 3.12 and 3.13 after pushes and pull requests. **Passing tests does not prove geometric accuracy for every CRS or every possible worldwide dataset**; see the accuracy limitation above.

## Project structure

```text
aereo-geospatial-measurement-api/
├── app/
│   ├── __init__.py
│   ├── main.py                     # App factory, health endpoint, error handler
│   ├── config.py                   # Environment-driven runtime limits
│   ├── db.py                       # Database engine and sessions
│   ├── models.py                   # Relational file and feature models
│   ├── schemas.py                  # API response models
│   ├── errors.py                   # Typed upload validation errors
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py                # Upload / file info / measurements endpoints
│   └── services/
│       ├── __init__.py
│       ├── parsers.py              # KML and zipped Shapefile parsing
│       └── measurement.py          # Projection selection, area and length
├── samples/
│   ├── example.kml
│   └── example-shapefile.zip
├── scripts/
│   └── create_sample_shapefile.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── helpers.py
│   ├── test_api.py
│   ├── test_measurement.py
│   └── test_parsers.py
├── .github/workflows/ci.yml
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── requirements-postgres.txt
└── README.md
```

## Design decisions

| Decision | Reason | Trade-off / alternative |
| --- | --- | --- |
| FastAPI | Type validation, focused REST implementation, automatic docs | Django REST Framework adds more built-in functionality but also more setup |
| pyshp + Shapely + PyProj | Keep parsing and calculation decoupled, avoid a separate GDAL install | GeoPandas/Fiona may be useful for advanced workflows |
| SQLite by default | Simple local setup with real persistence | PostgreSQL/PostGIS scales better for shared spatial workloads |
| Synchronous upload processing | Easy to reason about for bounded workloads | Background workers/queues for very large files |
| One SQL transaction per upload | Consistent metadata and feature persistence | Very large uploads would benefit from job state and staged writes |
| Per-feature error status | Preserve useful data even when a geometry cannot be measured | Fail-fast is simpler but less informative |
| Preserve original geometry | Keep original coordinates and source CRS accessible | Add normalized spatial columns for fast spatial queries later |
| Docker + CI | Reproducible execution and repeatable tests | Not a full deployment/observability platform |

## Troubleshooting on macOS

**`zsh: command not found: python3.12`**

Make sure `brew install python@3.12` completed. Check `brew --prefix python@3.12` and reopen Terminal or fix the Homebrew PATH.

**`zsh: command not found: brew`**

Try `eval "$(/opt/homebrew/bin/brew shellenv)"` and add Homebrew's installer-recommended initialization to your shell profile.

**`ModuleNotFoundError: No module named 'fastapi'`**

Activate the virtual environment and install the requirements:

```bash
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

**`ERROR: Could not import module "app.main"`**

Run the server **from the repository root**, not from inside `app/`:

```bash
pwd
python -m uvicorn app.main:app --reload
```

**`Address already in use` on port 8000**

Stop the other local server or run:

```bash
python -m uvicorn app.main:app --reload --port 8001
```

Then use `http://127.0.0.1:8001/docs` and change the port in `curl` examples.

**Python package architecture mismatch (`x86_64` vs `arm64`)**

Run:

```bash
uname -m
python -c "import platform; print(platform.machine())"
```

Use an ARM64 Python 3.12 interpreter, recreate `.venv`, and reinstall dependencies. Don't mix Rosetta Python and native arm64 wheels.

**Docker is unavailable**

Use the Python virtual-environment instructions instead. Docker is optional.

**The ZIP upload returns HTTP 422**

Check that it contains **one** `.shp`, matching `.shx`, `.dbf`, and `.prj`, and a valid CRS in `.prj`. A ZIP containing only `.shp` is not a complete Shapefile dataset.

## Limitations and future work

This submission intentionally does not include:

- User authentication or authorization.
- Upload ownership, tenant isolation, or rate limiting.
- Distributed/asynchronous job processing.
- Object storage of original uploaded files.
- Public deployment, monitoring dashboards, or production migrations.
- Universally accurate geodesic calculations for extreme geographic extents.

Possible future enhancements:

1. **PostgreSQL + PostGIS** for spatial indexing and bounding-box queries.
2. **Redis + background workers** for processing large files with job progress and retries.
3. **S3 or Azure Blob Storage** for source-file retention, checksums, and auditability.
4. **JWT authentication and tenant ownership** to separate users' data.
5. **Geodesic accuracy validation** against trusted reference datasets.
6. **Structured logging, metrics, tracing, and load tests**.
7. **An optional map viewer** to visually inspect geospatial features and results.

## Learnings

- **Geospatial correctness starts with CRS awareness.** Latitude and longitude are angular coordinates and cannot be treated as meters.
- **File upload is a security boundary.** Malformed ZIP/XML input, unsafe archive paths, and resource exhaustion deserve explicit limits and error handling.
- **Separating concerns improves maintainability.** Parsing, measurement, persistence, and HTTP endpoints are isolated into testable modules.
- **Small, complete systems are better than oversized demos.** The implementation prioritizes the requested functionality, repeatable tests, and explainable trade-offs.

## GitHub submission

1. Run the local API and upload **both** sample formats.
2. Run all tests successfully and inspect returned measurements.
3. Confirm you understand why the geometry is transformed before measurement.
4. Create an **empty public GitHub repository** (for example, `aereo-geospatial-measurement-api`).
5. From the local project root, commit the source:

```bash
git init
git add .
git commit -m "Build CRS-aware geospatial file measurement API"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/aereo-geospatial-measurement-api.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub username. Complete GitHub authentication when prompted; do not commit passwords, secrets, your local `.env`, `.venv`, or SQLite database.

6. Open the repository on GitHub and verify the rendered README, sample files, and **Actions** test results.
7. Share the **public repository URL** as your AEREO assignment submission.

**Interview preparation:** Be ready to explain why the API uses a projected CRS, how a zipped Shapefile is validated, why unsupported geometry does not crash the entire upload, what the database stores, and what you would change for a million features.
