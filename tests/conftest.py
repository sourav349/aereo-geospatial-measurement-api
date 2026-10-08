"""Isolated temporary database for every API test."""

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.main import create_app


@pytest.fixture
def client(tmp_path: Path):
    app = create_app(database_url=f"sqlite:///{tmp_path / 'test.db'}")
    with TestClient(app) as test_client:
        yield test_client
