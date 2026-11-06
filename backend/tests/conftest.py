import os
import tempfile

# Must be set before the app is imported.
os.environ["SECRET_KEY"] = "test-secret-key-for-automated-tests-only"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite:///" + os.path.join(tempfile.gettempdir(), "brandguard_test.db"))
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="bg_uploads_")
os.environ["LLM_PROVIDER"] = "none"

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.services.seed import seed_demo

CREDS = {
    "admin": ("admin@technova.demo", "Admin@123"),
    "creator": ("creator@technova.demo", "Creator@123"),
    "reviewer": ("reviewer@technova.demo", "Reviewer@123"),
}


@pytest.fixture
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        seed_demo(s)
    yield


@pytest.fixture
def client(fresh_db):
    return TestClient(app)


@pytest.fixture
def auth(client):
    """auth('creator') -> headers with a valid token for the seeded demo user."""
    def _auth(role: str):
        email, pw = CREDS[role]
        r = client.post("/api/auth/login", json={"email": email, "password": pw})
        assert r.status_code == 200, r.text
        return {"Authorization": "Bearer " + r.json()["access_token"]}
    return _auth
