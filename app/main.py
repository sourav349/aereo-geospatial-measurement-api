"""Application entrypoint: `uvicorn app.main:app --reload`."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import Settings
from app.db import Base, build_engine, build_session_factory
from app.errors import InputError
from app import models  # noqa: F401 - register SQLAlchemy tables


def create_app(database_url: str | None = None, settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    engine = build_engine(database_url or config.database_url)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        Base.metadata.create_all(engine)
        yield
        engine.dispose()

    application = FastAPI(
        title="AEREO Geospatial File Measurement API",
        description="Upload KML or zipped Shapefiles, inspect features, and calculate projected area/length.",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.state.engine = engine
    application.state.session_factory = build_session_factory(engine)
    application.state.settings = config
    application.include_router(router)

    @application.exception_handler(InputError)
    async def handle_input_error(request: Request, error: InputError):
        return JSONResponse(status_code=error.status_code, content={"detail": error.detail})

    @application.get("/health", tags=["operations"])
    def health():
        return {"status": "ok"}

    return application


app = create_app()
