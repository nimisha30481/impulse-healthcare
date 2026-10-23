import pytest
from botocore.exceptions import ClientError
from conftest import PASSWORD, PHONE, Api

from app.core.config import get_settings
from app.integrations import aws_services, cognito


class FakeIdp:
    """In-memory stand-in for the Cognito user APIs DoseWISE calls."""

    def __init__(self):
        self.users, self.calls = {}, []

    def _err(self, code):
        raise ClientError({"Error": {"Code": code, "Message": code}}, "op")

    def sign_up(self, **kw):
        self.calls.append(("sign_up", kw))
        if kw["Username"] in self.users:
            self._err("UsernameExistsException")
        self.users[kw["Username"]] = {"pw": kw["Password"], "confirmed": False, "sub": f"sub-{len(self.users)}"}
        return {"UserSub": self.users[kw["Username"]]["sub"]}

    def confirm_sign_up(self, **kw):
        self.calls.append(("confirm_sign_up", kw))
        if kw["ConfirmationCode"] != "123456":
            self._err("CodeMismatchException")
        self.users[kw["Username"]]["confirmed"] = True

    def resend_confirmation_code(self, **kw):
        self.calls.append(("resend_confirmation_code", kw))

    def initiate_auth(self, **kw):
        self.calls.append(("initiate_auth", kw))
        p = kw["AuthParameters"]
        u = self.users.get(p["USERNAME"])
        if not u or u["pw"] != p["PASSWORD"]:
            self._err("NotAuthorizedException")
        if not u["confirmed"]:
            self._err("UserNotConfirmedException")
        return {"AuthenticationResult": {"IdToken": u["sub"], "AccessToken": "at"}}

    def forgot_password(self, **kw):
        self.calls.append(("forgot_password", kw))

    def confirm_forgot_password(self, **kw):
        if kw["ConfirmationCode"] != "654321":
            self._err("CodeMismatchException")
        self.users[kw["Username"]]["pw"] = kw["Password"]


@pytest.fixture
def idp(monkeypatch):
    s = get_settings()
    fake = FakeIdp()
    for k, v in {"auth_provider": "cognito", "cognito_region": "ap-south-1", "cognito_user_pool_id": "pool",
                 "cognito_client_id": "client", "cognito_client_secret": "secret"}.items():
        monkeypatch.setattr(s, k, v)
    monkeypatch.setattr(aws_services, "client", lambda *a, **k: fake)
    monkeypatch.setattr(cognito, "verify_id_token", lambda token: {"sub": token})  # fake IdToken = sub
    return fake


def test_cognito_signup_verify_login_and_reset(idp):
    api, email = Api(), "new.patient@example.com"
    body = {"role": "patient", "full_name": "New Patient", "email": email, "password": PASSWORD,
            "phone": PHONE, "accept_terms": True}
    r = api.post("/api/auth/register", body)
    assert r.json()["status"] == "verify_code" and "dev_link" not in r.json()
    sent = idp.calls[0][1]
    assert sent["SecretHash"] and {"Name": "phone_number", "Value": "+919876543210"} in sent["UserAttributes"]
    # duplicate sign-up looks identical (no account enumeration) and emails a fresh code
    assert api.post("/api/auth/register", body).json()["status"] == "verify_code"
    assert idp.calls[-1][0] == "resend_confirmation_code"

    assert api.post("/api/auth/login", {"email": email, "password": PASSWORD}).status_code == 403  # code not entered
    assert api.post("/api/auth/verify-email", {"email": email, "code": "000000"}).status_code == 400
    assert api.post("/api/auth/verify-email", {"email": email, "code": "123456"}).status_code == 200
    assert api.post("/api/auth/login", {"email": email, "password": "Wrong_Pass1"}).status_code == 401
    r = api.post("/api/auth/login", {"email": email, "password": PASSWORD})
    assert r.status_code == 200 and r.json()["user"]["email"] == email
    assert api.get("/api/auth/me").json()["patient_id"]

    assert Api().post("/api/auth/forgot-password", {"email": email}).json()["status"] == "code_sent"
    assert Api().post("/api/auth/reset-password", {"email": email, "code": "654321", "password": "N3w_Passw0rd"}).status_code == 200
    assert Api().post("/api/auth/login", {"email": email, "password": "N3w_Passw0rd"}).status_code == 200


def test_token_check_failure_is_a_clear_503_not_a_crash(idp, monkeypatch):
    api, email = Api(), "token.check@example.com"
    api.post("/api/auth/register", {"role": "patient", "full_name": "Token Check", "email": email, "password": PASSWORD,
                                    "phone": PHONE, "accept_terms": True})
    api.post("/api/auth/verify-email", {"email": email, "code": "123456"})

    def boom(token):
        raise RuntimeError("JWKS unreachable")

    monkeypatch.setattr(cognito, "verify_id_token", boom)
    r = api.post("/api/auth/login", {"email": email, "password": PASSWORD})
    assert r.status_code == 503 and "temporarily unavailable" in r.json()["detail"]


def test_region_needs_a_state():
    from conftest import register

    api, _ = register("patient")
    assert api.patch("/api/account/preferences", {"country": "India", "state": ""}).status_code == 400
    assert api.patch("/api/account/preferences", {"country": "India", "state": "Karnataka"}).status_code == 200


def test_local_accounts_still_sign_in_when_cognito_is_on(idp):
    from conftest import register

    get_settings().auth_provider = "local"
    api, me = register("patient")  # created before Cognito was switched on
    get_settings().auth_provider = "cognito"
    r = Api().post("/api/auth/login", {"email": me["email"], "password": PASSWORD})
    assert r.status_code == 200
    assert not [c for c in idp.calls if c[0] == "initiate_auth"]
