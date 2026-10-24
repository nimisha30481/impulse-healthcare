from conftest import PASSWORD, PHONE, Api, grant_doctor, make_doctor, register


def test_registration_requires_verification_and_strong_password():
    api = Api()
    base = {"role": "patient", "full_name": "A B", "email": "a@example.com", "phone": PHONE, "accept_terms": True}
    for weak in ("password123", "Passw0rd!", "Sh0rt_a"):  # no upper/special · '!' not allowed · too short
        assert api.post("/api/auth/register", {**base, "password": weak}).status_code in (400, 422)
    assert api.post("/api/auth/register", {**base, "phone": "98765", "password": PASSWORD}).status_code == 422
    assert api.post("/api/auth/register", {**{k: v for k, v in base.items() if k != "phone"},
                                           "password": PASSWORD}).status_code == 422
    r = api.post("/api/auth/register", {**base, "password": PASSWORD})
    assert r.status_code == 200
    login = api.post("/api/auth/login", {"email": "a@example.com", "password": PASSWORD})
    assert login.status_code == 403  # email not verified yet


def test_login_wrong_password_and_lockout():
    api, me = register("patient")
    api.post("/api/auth/logout")
    other = Api()
    for _ in range(5):
        assert other.post("/api/auth/login", {"email": me["email"], "password": "Wrong!Pass123"}).status_code == 401
    assert other.post("/api/auth/login", {"email": me["email"], "password": PASSWORD}).status_code == 423


def test_csrf_required_for_state_changes():
    api, me = register("patient")
    r = api.c.patch("/api/account/preferences", json={"theme": "dark"})  # no CSRF header
    assert r.status_code == 403


def test_role_cannot_be_escalated_at_registration():
    api = Api()
    r = api.post("/api/auth/register", {"role": "admin", "full_name": "X Y", "email": "x@example.com",
                                        "password": PASSWORD, "accept_terms": True})
    assert r.status_code == 422


def test_new_doctor_works_immediately_but_sees_no_patients_without_access(db):
    # the council registration number is the check: no staff verification step
    doc_api, doc = register("doctor", speciality="Cardiology", registration_number="R-9")
    assert doc_api.get("/api/doctor/dashboard").status_code == 200
    p_api, patient = register("patient")
    assert doc_api.get(f"/api/patients/{patient['patient_id']}/records").status_code == 403


def test_doctor_cannot_read_unrelated_patient_and_denial_is_audited(db):
    p_api, patient = register("patient")
    doc_api, doc = make_doctor()
    r = doc_api.get(f"/api/patients/{patient['patient_id']}/records")
    assert r.status_code == 403
    from app.models import AuditLog

    assert db.query(AuditLog).filter(AuditLog.action == "access_denied").count() == 1
    grant_doctor(p_api, doc["id"])
    assert doc_api.get(f"/api/patients/{patient['patient_id']}/records").status_code == 200


def test_caregiver_invite_accept_authorize_and_revoke():
    p_api, patient = register("patient")
    cg_api, cg = register("caregiver")
    pid = patient["patient_id"]
    inv = p_api.post("/api/me/caregivers/invite", {"contact": cg["email"], "scopes": ["medications.view"]})
    assert inv.status_code == 200, inv.text
    token = inv.json()["dev_link"].split("token=")[1]
    # not active until accepted AND authorised by the patient
    assert cg_api.get(f"/api/patients/{pid}/medications").status_code == 403
    assert cg_api.post("/api/caregiver/invitations/accept", {"token": token}).status_code == 200
    assert cg_api.get(f"/api/patients/{pid}/medications").status_code == 403
    rel_id = inv.json()["relationship"]["id"]
    assert p_api.post(f"/api/me/caregivers/{rel_id}/authorize").status_code == 200
    assert cg_api.get(f"/api/patients/{pid}/medications").status_code == 200
    # scope limits: records.view was not granted
    assert cg_api.get(f"/api/patients/{pid}/records").status_code == 403
    # revocation takes effect on the very next request
    assert p_api.post(f"/api/me/caregivers/{rel_id}/revoke", {"reason": "test"}).status_code == 200
    assert cg_api.get(f"/api/patients/{pid}/medications").status_code == 403


def test_invitation_cannot_be_accepted_by_someone_else():
    p_api, patient = register("patient")
    _, cg = register("caregiver")
    other_api, _ = register("caregiver")
    inv = p_api.post("/api/me/caregivers/invite", {"contact": cg["email"], "scopes": ["medications.view"]}).json()
    token = inv["dev_link"].split("token=")[1]
    assert other_api.post("/api/caregiver/invitations/accept", {"token": token}).status_code == 403


def test_caregiver_cannot_prescribe_or_grant():
    _, patient = register("patient")
    cg_api, _ = register("caregiver")
    assert cg_api.post("/api/doctor/prescriptions", {"patient_id": patient["patient_id"], "items": []}).status_code == 403
    assert cg_api.post("/api/me/caregivers/invite", {"contact": "z@example.com", "scopes": ["records.view"]}).status_code == 403


def test_preferences_persist():
    api, _ = register("patient")
    assert api.patch("/api/account/preferences", {"language": "kn", "theme": "dark"}).status_code == 200
    assert api.get("/api/auth/me").json()["preferences"]["language"] == "kn"


def test_mfa_enrollment_and_login():
    import pyotp

    api, me = register("patient")
    secret = api.post("/api/account/mfa/setup").json()["secret"]
    r = api.post("/api/account/mfa/enable", {"code": pyotp.TOTP(secret).now()})
    assert r.status_code == 200 and len(r.json()["backup_codes"]) == 8
    fresh = Api()
    login = fresh.post("/api/auth/login", {"email": me["email"], "password": PASSWORD}).json()
    assert login["mfa_required"] is True
    assert fresh.get("/api/auth/me").status_code == 401
    assert fresh.post("/api/auth/mfa/verify", {"code": pyotp.TOTP(secret).now()}).status_code == 200
    assert fresh.get("/api/auth/me").status_code == 200


def test_audit_chain_is_tamper_evident(db):
    register("patient")
    from app.core import audit
    from app.models import AuditLog

    assert audit.verify_chain(db)["valid"]
    row = db.query(AuditLog).order_by(AuditLog.seq).first()
    row.action = "tampered"
    db.commit()
    assert audit.verify_chain(db)["valid"] is False
