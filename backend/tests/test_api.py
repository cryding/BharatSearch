import os
import tempfile
from fastapi.testclient import TestClient

_fd, _db = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["BHARATSEARCH_DB"] = _db

from app.main import app, init_db  # noqa: E402

client = TestClient(app)


def setup_module():
    init_db()


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_search_rejects_empty_query():
    response = client.get("/api/search", params={"q": ""})
    assert response.status_code == 400


def test_search_empty_index_returns_empty_results():
    response = client.get("/api/search", params={"q": "notfoundtoken"})
    assert response.status_code == 200
    assert response.json()["results"] == []


def test_crawl_rejects_localhost():
    response = client.post("/api/crawl", json={"seed_urls": ["http://127.0.0.1/"]})
    assert response.status_code == 400


def test_stats_shape():
    response = client.get("/api/stats")
    assert response.status_code == 200
    assert "indexed_pages" in response.json()
