import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="impulse-test-")
os.environ.update({
    "ENVIRONMENT": "test",
    "DATABASE_URL": f"sqlite:///{_tmp}/test.db",
    "LOCAL_STORAGE_DIR": f"{_tmp}/storage",
    "RUN_BACKGROUND_JOBS": "false",
    "SECRET_KEY": "test-secret",
})

from app.core.config import Settings  # noqa: E402

# Tests never read backend/.env, so a developer's linked AWS account is never called from a test.
Settings.model_config["env_file"] = None

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import DoctorProfile, User  # noqa: E402

PASSWORD = "Str0ng_Pass"
PHONE = "9876543210"
COUNCIL = "Karnataka Medical Council"


class Api:
    """TestClient wrapper that sends the CSRF header like the real frontend."""

    def __init__(self):
        self.c = TestClient(app)

    def _h(self):
        tok = self.c.cookies.get("impulse_csrf")
        return {"X-CSRF-Token": tok} if tok else {}

    def get(self, url, **kw):
        return self.c.get(url, **kw)

    def post(self, url, json=None, **kw):
        return self.c.post(url, json=json, headers=self._h(), **kw)

    def put(self, url, json=None):
        return self.c.put(url, json=json, headers=self._h())

    def patch(self, url, json=None):
        return self.c.patch(url, json=json, headers=self._h())

    def delete(self, url):
        return self.c.delete(url, headers=self._h())


@pytest.fixture(autouse=True)
def fresh_db():
    from app.api import auth

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    auth._attempts.clear()  # the in-process rate limiter would otherwise throttle test registrations
    yield


def register(role="patient", email=None, **extra) -> tuple[Api, dict]:
    api = Api()
    email = email or f"{role}-{os.urandom(3).hex()}@example.com"
    body = {"role": role, "full_name": f"Test {role.title()}", "email": email, "password": PASSWORD,
            "phone": PHONE, "accept_terms": True, **extra}
    if role == "doctor":
        body.setdefault("registration_council", COUNCIL)
    r = api.post("/api/auth/register", body)
    assert r.status_code == 200, r.text
    token = r.json()["dev_link"].split("token=")[1]
    assert api.post("/api/auth/verify-email", {"token": token}).status_code == 200
    r = api.post("/api/auth/login", {"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    me = api.get("/api/auth/me").json()
    return api, me


def verify_doctor(user_id: str):
    db = SessionLocal()
    db.query(DoctorProfile).filter(DoctorProfile.user_id == user_id).update({"verification_status": "verified"})
    db.commit()
    db.close()


def make_doctor() -> tuple[Api, dict]:
    api, me = register("doctor", speciality="General Medicine", registration_number="TEST-1")
    verify_doctor(me["id"])
    return api, me


def grant_doctor(patient_api: Api, doctor_id: str):
    r = patient_api.post("/api/me/doctors/grant", {"doctor_id": doctor_id})
    assert r.status_code == 200, r.text


def order(**over):
    from datetime import date

    base = {"generic_name": "Metformin", "strength": "500 mg", "dosage_form": "tablet", "dose_amount": 1,
            "dose_unit": "tablet", "route": "oral", "frequency_label": "Twice daily", "times_of_day": ["08:00", "20:00"],
            "start_date": date.today().isoformat()}
    base.update(over)
    return base


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


__all__ = ["Api", "register", "make_doctor", "grant_doctor", "order", "User"]
