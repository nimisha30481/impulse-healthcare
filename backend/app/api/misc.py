"""Notifications inbox, real-time stream, healthcare directory, integration status, admin."""
import asyncio
import math
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api import serializers as S
from app.core import audit
from app.core.config import get_settings
from app.core.database import SessionLocal, get_db
from app.core.deps import current_user, require_roles
from app.core.errors import bad_request, not_found
from app.core.security import hash_password
from app.integrations import aws_services
from app.integrations.registry import integration_status
from app.models import (
    AuditLog,
    BreakGlassAccess,
    DoctorProfile,
    HealthcareOrganization,
    Notification,
    PatientProfile,
    SupportProfile,
    User,
)
from app.models.base import utcnow
from app.services import fhir, jobs, realtime

router = APIRouter(prefix="/api", tags=["misc"])


# ---------------- notifications ----------------
@router.get("/notifications")
def list_notifications(unread: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)):
    qy = select(Notification).where(Notification.user_id == user.id, Notification.channel == "in_app")
    if unread:
        qy = qy.where(Notification.read_at.is_(None))
    rows = db.execute(qy.order_by(Notification.created_at.desc()).limit(100)).scalars().all()
    # other-channel delivery state for transparency ("email not sent: provider not configured")
    others = db.execute(select(Notification).where(Notification.user_id == user.id, Notification.channel != "in_app")
                        .order_by(Notification.created_at.desc()).limit(100)).scalars().all()
    by_key: dict[str, list] = {}
    for o in others:
        if o.dedupe_key:
            by_key.setdefault(o.dedupe_key.rsplit(":", 1)[0], []).append({"channel": o.channel, "status": o.delivery_status})
    out = []
    for n in rows:
        row = S.notification(n)
        row["other_channels"] = by_key.get((n.dedupe_key or "").rsplit(":", 1)[0], []) if n.dedupe_key else []
        out.append(row)
    unread_count = db.scalar(select(func.count()).select_from(Notification).where(
        Notification.user_id == user.id, Notification.channel == "in_app", Notification.read_at.is_(None)))
    return {"items": out, "unread": unread_count}


@router.post("/notifications/{nid}/read")
def mark_read(nid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, nid)
    if not n or n.user_id != user.id:
        raise not_found("Notification")
    n.read_at = n.read_at or utcnow()
    db.commit()
    return {"status": "read"}


@router.post("/notifications/read-all")
def read_all(user: User = Depends(current_user), db: Session = Depends(get_db)):
    for n in db.execute(select(Notification).where(Notification.user_id == user.id,
                                                   Notification.read_at.is_(None))).scalars():
        n.read_at = utcnow()
    db.commit()
    return {"status": "ok"}


@router.post("/notifications/{nid}/acknowledge")
def acknowledge(nid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, nid)
    if not n or n.user_id != user.id:
        raise not_found("Notification")
    n.acknowledged_at = n.acknowledged_at or utcnow()
    n.read_at = n.read_at or utcnow()
    db.commit()
    return {"status": "acknowledged"}


# ---------------- real-time (SSE) ----------------
@router.get("/events/stream")
async def stream(request: Request, user: User = Depends(current_user)):
    realtime.bind_loop(asyncio.get_running_loop())
    q = realtime.subscribe(user.id)

    async def gen():
        try:
            yield "event: ready\ndata: {}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=20)
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            realtime.unsubscribe(user.id, q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


# ---------------- directory ----------------
def _haversine(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@router.get("/directory")
def directory(q: str | None = None, kind: str | None = Query(None, pattern="^(hospital|clinic|pharmacy|laboratory)$"),
              city: str | None = None, service: str | None = None, lat: float | None = None,
              lng: float | None = None, near: str | None = None, db: Session = Depends(get_db)):
    """Public directory search. Location is optional; users can type a place instead of sharing
    device location. Medicine availability is never shown without a verified pharmacy feed."""
    geocoded = None
    if near and lat is None:
        g = aws_services.geocode(near)
        if g.state == "ok" and g.data:
            lat, lng, geocoded = g.data["lat"], g.data["lng"], g.data["label"]
    ids = None
    engine = "sql"
    if q:
        os_res = aws_services.opensearch_query(q, kind)
        if os_res.state == "ok":
            ids, engine = os_res.data, "opensearch"
    qy = select(HealthcareOrganization)
    if ids is not None:
        qy = qy.where(HealthcareOrganization.id.in_(ids))
    elif q:
        like = f"%{q}%"
        qy = qy.where(or_(HealthcareOrganization.name.ilike(like), HealthcareOrganization.address.ilike(like),
                          HealthcareOrganization.city.ilike(like)))
    if kind:
        qy = qy.where(HealthcareOrganization.kind == kind)
    if city:
        qy = qy.where(HealthcareOrganization.city.ilike(city))
    rows = db.execute(qy.limit(200)).scalars().all()
    if service:
        rows = [o for o in rows if any(service.lower() in s.lower() for s in (o.services or []) + (o.departments or []))]
    out = []
    for o in rows:
        dist = round(_haversine(lat, lng, o.latitude, o.longitude), 1) if (lat is not None and o.latitude) else None
        out.append({"id": o.id, "kind": o.kind, "name": o.name, "address": o.address, "city": o.city,
                    "phone": o.phone, "opening_hours": o.opening_hours, "departments": o.departments,
                    "services": o.services, "distance_km": dist, "latitude": o.latitude, "longitude": o.longitude,
                    "data_source": o.data_source, "is_verified": o.is_verified,
                    "directions_url": f"https://www.openstreetmap.org/?mlat={o.latitude}&mlon={o.longitude}#map=17/{o.latitude}/{o.longitude}"
                    if o.latitude else None,
                    "medicine_availability": {"available": None, "note": "Not available — no verified pharmacy stock "
                                                                         "integration is connected."}
                    if o.kind == "pharmacy" else None})
    if lat is not None:
        out.sort(key=lambda r: (r["distance_km"] is None, r["distance_km"] or 0))
    return {"results": out, "search_engine": engine, "geocoded": geocoded,
            "notice": "Entries marked DEMO are fictional examples for demonstration and must not be used to seek care."}


@router.get("/directory/doctors")
def directory_doctors(q: str | None = None, speciality: str | None = None, db: Session = Depends(get_db)):
    qy = select(DoctorProfile).where(DoctorProfile.verification_status == "verified")
    if speciality:
        qy = qy.where(DoctorProfile.speciality == speciality)
    rows = db.execute(qy).scalars().all()
    if q:
        rows = [d for d in rows if q.lower() in d.user.full_name.lower() or q.lower() in d.speciality.lower()]
    return [{"id": d.user_id, "name": d.user.full_name, "speciality": d.speciality, "languages": d.languages,
             "organization": d.organization.name if d.organization else None,
             "is_demo": d.user.is_demo} for d in rows]


# ---------------- integrations ----------------
@router.get("/integrations/status")
def integrations(user: User = Depends(current_user)):
    s = get_settings()
    return {"environment": s.environment, "auth_provider": s.auth_provider, "services": integration_status(),
            # which notification channels can actually deliver here (Settings hides the rest)
            "channels": {"email": bool(s.ses_from_address),
                         "sms": bool(s.sns_sms_enabled or s.sms_origination_identity)}}


# ---------------- admin ----------------
Admin = require_roles("admin")


@router.get("/admin/doctors/pending")
def pending_doctors(user: User = Depends(Admin), db: Session = Depends(get_db)):
    rows = db.execute(select(DoctorProfile).where(DoctorProfile.verification_status == "pending")).scalars()
    return [{"user_id": d.user_id, "name": d.user.full_name, "email": d.user.email, "speciality": d.speciality,
             "registration_number": d.registration_number, "registration_council": d.registration_council,
             "registered_at": d.created_at, "email_verified": d.user.email_verified} for d in rows]


class DoctorDecision(BaseModel):
    approve: bool
    note: str = Field(min_length=3, max_length=500)


@router.post("/admin/doctors/{user_id}/verify")
def verify_doctor(user_id: str, body: DoctorDecision, user: User = Depends(Admin), db: Session = Depends(get_db)):
    d = db.execute(select(DoctorProfile).where(DoctorProfile.user_id == user_id)).scalar_one_or_none()
    if not d:
        raise not_found("Doctor")
    d.verification_status = "verified" if body.approve else "rejected"
    d.verified_by, d.verified_at = user.id, utcnow()
    audit.record(db, action=f"doctor_{d.verification_status}", resource_type="user", resource_id=user_id, user=user,
                 reason=body.note)
    db.commit()
    return {"status": d.verification_status,
            "note": "Verification here confirms registration details were checked by staff. It does not grant "
                    "access to any patient - patients or appointments grant that."}


class StaffIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: str
    phone: str | None = None
    temporary_password: str = Field(min_length=12)
    team: str = "Care coordination"


@router.post("/admin/support-staff")
def create_support(body: StaffIn, user: User = Depends(Admin), db: Session = Depends(get_db)):
    if db.execute(select(User).where(User.email == body.email.lower())).scalar_one_or_none():
        raise bad_request("Email already registered")
    u = User(email=body.email.lower(), phone=body.phone, full_name=body.full_name, role="support",
             password_hash=hash_password(body.temporary_password), email_verified=True)
    db.add(u)
    db.flush()
    db.add(SupportProfile(user_id=u.id, team=body.team))
    audit.record(db, action="support_account_created", resource_type="user", resource_id=u.id, user=user)
    db.commit()
    return {"id": u.id}


@router.get("/admin/audit")
def audit_log(action: str | None = None, patient_id: str | None = None, user_id: str | None = None,
              limit: int = Query(100, le=500), user: User = Depends(Admin), db: Session = Depends(get_db)):
    qy = select(AuditLog)
    if action:
        qy = qy.where(AuditLog.action.ilike(f"%{action}%"))
    if patient_id:
        qy = qy.where(AuditLog.patient_id == patient_id)
    if user_id:
        qy = qy.where(AuditLog.user_id == user_id)
    rows = db.execute(qy.order_by(AuditLog.seq.desc()).limit(limit)).scalars().all()
    audit.record(db, action="audit_log_access", resource_type="audit_log", user=user,
                 reason=f"action={action} patient={patient_id} user={user_id}")
    db.commit()
    return {"entries": [{"seq": a.seq, "at": a.created_at, "user_id": a.user_id, "role": a.user_role,
                         "action": a.action, "resource_type": a.resource_type, "resource_id": a.resource_id,
                         "patient_id": a.patient_id, "version_ref": a.version_ref, "reason": a.reason,
                         "auth_context": a.auth_context, "outcome": a.outcome, "source": a.source} for a in rows],
            "chain": audit.verify_chain(db)}


@router.get("/admin/break-glass")
def break_glass_list(user: User = Depends(Admin), db: Session = Depends(get_db)):
    rows = db.execute(select(BreakGlassAccess).order_by(BreakGlassAccess.created_at.desc())).scalars()
    return [{"id": b.id, "patient_id": b.patient_id, "user_id": b.user_id, "justification": b.justification,
             "created_at": b.created_at, "expires_at": b.expires_at, "reviewed_at": b.reviewed_at,
             "review_outcome": b.review_outcome} for b in rows]


class BGReview(BaseModel):
    outcome: str = Field(min_length=3, max_length=200)


@router.post("/admin/break-glass/{bg_id}/review")
def review_break_glass(bg_id: str, body: BGReview, user: User = Depends(Admin), db: Session = Depends(get_db)):
    b = db.get(BreakGlassAccess, bg_id)
    if not b:
        raise not_found("Access")
    b.reviewed_by, b.reviewed_at, b.review_outcome = user.id, utcnow(), body.outcome
    audit.record(db, action="break_glass_reviewed", resource_type="break_glass", resource_id=b.id,
                 patient_id=b.patient_id, user=user, reason=body.outcome)
    db.commit()
    return {"status": "reviewed"}


@router.post("/admin/fhir-sync/{patient_id}")
def fhir_sync(patient_id: str, user: User = Depends(Admin), db: Session = Depends(get_db)):
    p = db.get(PatientProfile, patient_id)
    if not p:
        raise not_found("Patient")
    out = fhir.sync_patient(db, p)
    audit.record(db, action="fhir_sync", resource_type="patient", resource_id=p.id, patient_id=p.id, user=user)
    db.commit()
    return out


@router.post("/dev/run-jobs")
def run_jobs(user: User = Depends(current_user)):
    """Development helper: runs one reminder/escalation tick immediately."""
    if not get_settings().is_dev:
        raise not_found()
    db = SessionLocal()
    try:
        jobs.tick(db)
    finally:
        db.close()
    return {"status": "tick complete", "at": datetime.now().isoformat()}
