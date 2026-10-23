"""Synthetic demo data. Every person, organisation and record here is FICTIONAL.

    python -m app.seed           # create demo data if missing
    python -m app.seed --reset   # drop everything and recreate (SQLite/dev only)
"""
import io
import random
import sys
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw
from sqlalchemy import select

from app.core import audit
from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password, new_token
from app.integrations import storage
from app.models import (
    Allergy,
    AvailabilitySlot,
    CareRelationship,
    CaregiverProfile,
    ConsentRecord,
    Diagnosis,
    DoctorAvailability,
    DoctorPatientAccess,
    DoctorProfile,
    DoseOccurrence,
    EscalationCase,
    EscalationPolicy,
    FollowUpInstruction,
    HealthcareOrganization,
    MedicalRecord,
    MedicationCatalogue,
    MedicationEvent,
    MedicationSchedule,
    Message,
    Notification,
    OCRExtraction,
    PatientProfile,
    Prescription,
    PrescriptionItem,
    PrescriptionVersion,
    SupportProfile,
    UploadedDocument,
    User,
)
from app.models.base import utcnow
from app.services import booking, escalation

IST = ZoneInfo("Asia/Kolkata")
random.seed(42)


def mk_user(db, email, role, name, phone=None, color="#0f766e", preferred=None):
    u = User(email=email, role=role, full_name=name, phone=phone, avatar_color=color, preferred_name=preferred,
             password_hash=hash_password(new_token()), email_verified=True, is_demo=True,
             preferences={"language": "en", "theme": "system", "notifications": {
                 "medication_reminders": {"email": False, "sms": False},
                 "appointment_reminders": {"email": True, "sms": False}}})
    db.add(u)
    db.flush()
    return u


def org(db, kind, name, address, city, lat, lng, **kw):
    o = HealthcareOrganization(kind=kind, name=name, address=address, city=city, state="Karnataka", latitude=lat,
                               longitude=lng, data_source="demo", is_verified=False, **kw)
    db.add(o)
    db.flush()
    return o


def catalogue(db, generic, strength, form, ingredients, brands=()):
    c = MedicationCatalogue(generic_name=generic, strength=strength, dosage_form=form, ingredients=list(ingredients),
                            brand_names=list(brands), data_source="demo")
    db.add(c)
    db.flush()
    return c


def prescribe(db, patient, doctor, cat, *, dose, unit, times, freq, start, end=None, status="active", indication=None,
              food=None, special=None, created_days_ago=60, days_of_week=None, interval=1, org_id=None, brand=None,
              source="impulse"):
    created = utcnow() - timedelta(days=created_days_ago)
    rx = Prescription(patient_id=patient.id, prescriber_user_id=doctor.id if doctor else None, source=source,
                      issued_at=created, organization_id=org_id, created_at=created)
    db.add(rx)
    db.flush()
    it = PrescriptionItem(prescription_id=rx.id, patient_id=patient.id, catalogue_id=cat.id, status=status,
                          created_at=created)
    db.add(it)
    db.flush()
    v = PrescriptionVersion(item_id=it.id, version_no=1, status="current", generic_name=cat.generic_name,
                            brand_name=brand, strength=cat.strength, dosage_form=cat.dosage_form, dose_amount=dose,
                            dose_unit=unit, route="oral", frequency_label=freq, indication=indication,
                            start_date=start, end_date=end, food_instructions=food, special_instructions=special,
                            effective_from=datetime.combine(start, time.min, tzinfo=IST),
                            created_by=doctor.id if doctor else None, change_reason="Initial prescription",
                            refills_allowed=2, quantity="30", created_at=created)
    v.schedule = MedicationSchedule(times_of_day=times, days_of_week=days_of_week, interval_days=interval)
    db.add(v)
    db.flush()
    return it, v


def history(db, patient, it, v, days, pattern):
    """pattern(day_index, time) -> status for past doses."""
    now = utcnow()
    today = now.astimezone(IST).date()
    for d in range(days, 0, -1):
        day = today - timedelta(days=d)
        if v.schedule.days_of_week is not None and day.weekday() not in v.schedule.days_of_week:
            continue
        for t in v.schedule.times_of_day:
            at = datetime.combine(day, time.fromisoformat(t), tzinfo=IST).astimezone(ZoneInfo("UTC"))
            st = pattern(d, t)
            occ = DoseOccurrence(item_id=it.id, version_id=v.id, patient_id=patient.id, scheduled_at=at, status=st,
                                 reminder_sent_at=at, responded_at=at + timedelta(minutes=12) if st != "unconfirmed" else None)
            db.add(occ)
            db.flush()
            db.add(MedicationEvent(occurrence_id=occ.id, item_id=it.id, version_id=v.id, patient_id=patient.id,
                                   kind="reminder_sent", source="system", created_at=at))
            kind = {"taken_reported": "taken_reported", "missed_reported": "missed_reported", "skipped": "skipped",
                    "unconfirmed": "marked_unconfirmed"}[st]
            db.add(MedicationEvent(occurrence_id=occ.id, item_id=it.id, version_id=v.id, patient_id=patient.id,
                                   kind=kind, source="patient_app" if st != "unconfirmed" else "system",
                                   reason="forgot" if st == "missed_reported" else None,
                                   actor_user_id=patient.user_id if st != "unconfirmed" else None,
                                   created_at=at + timedelta(minutes=12)))


def demo_prescription_png() -> bytes:
    img = Image.new("RGB", (1200, 1600), "white")
    d = ImageDraw.Draw(img)
    lines = ["GREENLEAF DEMO CLINIC  (FICTIONAL - DEMO DATA)", "", "Patient: Ananya Rao", "Dr. Arjun Mehra",
             "Date: (demo)", "", "Rx", "1. Vitamin B12 500 mcg tablet", "   1 tablet oral once daily x 30 days",
             "", "Take after breakfast", "", "THIS IS A SYNTHETIC DOCUMENT FOR DEMONSTRATION ONLY"]
    for i, line in enumerate(lines):
        d.text((80, 100 + i * 70), line, fill="black")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def seed(db):
    if db.execute(select(User).where(User.is_demo.is_(True))).first():
        print("Demo data already present. Use --reset to recreate.")
        return
    now = utcnow()
    today = now.astimezone(IST).date()

    # ---------------- organisations (fictional) ----------------
    hosp = org(db, "hospital", "Lotus Demo Hospital", "14 Demo Ring Road, Indiranagar", "Bengaluru", 12.9719, 77.6412,
               phone="+91-80-0000-0101", opening_hours="24 hours", departments=["Endocrinology", "Cardiology",
               "General Medicine", "Emergency"], services=["Emergency care", "Inpatient", "Diagnostics"])
    clinic = org(db, "clinic", "Greenleaf Demo Clinic", "7 Sample Street, Koramangala", "Bengaluru", 12.9352, 77.6245,
                 phone="+91-80-0000-0202", opening_hours="Mon–Sat 9:00–19:00", departments=["General Medicine"],
                 services=["Consultations", "Vaccinations"])
    org(db, "pharmacy", "CarePlus Demo Pharmacy", "22 Example Lane, HSR Layout", "Bengaluru", 12.9116, 77.6474,
        phone="+91-80-0000-0303", opening_hours="Daily 8:00–22:00", services=["Prescriptions", "Home delivery (demo)"])
    org(db, "pharmacy", "Medway Demo Pharmacy", "3 Placeholder Road, Jayanagar", "Bengaluru", 12.9250, 77.5938,
        phone="+91-80-0000-0404", opening_hours="Daily 7:00–23:00", services=["Prescriptions"])
    org(db, "laboratory", "Clearpath Demo Diagnostics", "9 Mock Avenue, Whitefield", "Bengaluru", 12.9698, 77.7500,
        phone="+91-80-0000-0505", opening_hours="Mon–Sun 7:00–20:00", services=["Blood tests", "HbA1c", "Lipid profile"])
    org(db, "hospital", "Riverside Demo Medical Centre", "1 Fictional Marg, Mysuru Road", "Mysuru", 12.2958, 76.6394,
        phone="+91-821-000-0606", opening_hours="24 hours", departments=["Cardiology", "Orthopaedics"],
        services=["Emergency care", "Outpatient"])

    # ---------------- people (fictional) ----------------
    admin = mk_user(db, "admin.demo@impulse.test", "admin", "Demo Administrator", color="#334155")
    dr = mk_user(db, "dr.mehra.demo@impulse.test", "doctor", "Dr. Arjun Mehra", "+91-90000-00011", "#0e7490")
    db.add(DoctorProfile(user_id=dr.id, speciality="Endocrinology", registration_number="DEMO-KMC-10001",
                         registration_council="Demo Medical Council", verification_status="verified",
                         verified_by=admin.id, verified_at=now, organization_id=clinic.id,
                         bio="Fictional demo clinician.", languages=["English", "Hindi", "Kannada"],
                         consultation_types=["in_person"]))
    dr2 = mk_user(db, "dr.khan.demo@impulse.test", "doctor", "Dr. Sara Khan", "+91-90000-00012", "#7c3aed")
    db.add(DoctorProfile(user_id=dr2.id, speciality="Cardiology", registration_number="DEMO-KMC-10002",
                         registration_council="Demo Medical Council", verification_status="verified",
                         verified_by=admin.id, verified_at=now, organization_id=hosp.id,
                         bio="Fictional demo clinician.", languages=["English", "Tamil"]))
    dr3 = mk_user(db, "dr.nair.demo@impulse.test", "doctor", "Dr. Vikram Nair", color="#a16207")
    db.add(DoctorProfile(user_id=dr3.id, speciality="General Medicine", registration_number="DEMO-KMC-10003",
                         verification_status="pending"))
    gp = mk_user(db, "dr.iyer.demo@impulse.test", "doctor", "Dr. Leela Iyer", color="#be185d")
    db.add(DoctorProfile(user_id=gp.id, speciality="General Medicine", registration_number="DEMO-KMC-10004",
                         verification_status="verified", verified_by=admin.id, verified_at=now,
                         organization_id=hosp.id, languages=["English", "Telugu"]))

    ananya = mk_user(db, "ananya.demo@impulse.test", "patient", "Ananya Rao", "+91-90000-00021", "#0f766e", "Ananya")
    pa = PatientProfile(user_id=ananya.id, mrn="IMP-DEMO-0001", access_id="DW-ANANYA", access_id_created_at=now, date_of_birth=date(1961, 4, 12), sex="Female",
                        blood_group="B+", allergy_status="has_allergies", condition_status="has_conditions",
                        emergency_contact_name="Kavya Rao", emergency_contact_phone="+91-90000-00031",
                        emergency_contact_relation="Daughter", emergency_info_shareable=True)
    rahul = mk_user(db, "rahul.demo@impulse.test", "patient", "Rahul Verma", "+91-90000-00022", "#9333ea", "Rahul")
    pr = PatientProfile(user_id=rahul.id, mrn="IMP-DEMO-0002", access_id="DW-RAHULV", access_id_created_at=now, date_of_birth=date(1974, 9, 3), sex="Male",
                        allergy_status="unknown", condition_status="has_conditions")
    meera = mk_user(db, "meera.demo@impulse.test", "patient", "Meera Iyer", "+91-90000-00023", "#c2410c", "Meera")
    pm = PatientProfile(user_id=meera.id, mrn="IMP-DEMO-0003", access_id="DW-MEERA2", access_id_created_at=now, date_of_birth=date(1990, 1, 22), sex="Female",
                        allergy_status="none_known", condition_status="none_known")
    db.add_all([pa, pr, pm])
    kavya = mk_user(db, "kavya.demo@impulse.test", "caregiver", "Kavya Rao", "+91-90000-00031", "#db2777", "Kavya")
    db.add(CaregiverProfile(user_id=kavya.id, relationship_note="Daughter of Ananya Rao"))
    sup = mk_user(db, "support.demo@impulse.test", "support", "Priya Nair", "+91-90000-00041", "#2563eb", "Priya")
    db.add(SupportProfile(user_id=sup.id, team="Care coordination", on_duty=True))
    db.flush()

    # ---------------- access grants ----------------
    for p in (pa, pr, pm):
        db.add(DoctorPatientAccess(patient_id=p.id, doctor_user_id=dr.id, purpose="Ongoing treatment (demo)",
                                   granting_authority="patient_grant", granted_by=p.user_id,
                                   starts_at=now - timedelta(days=200), expires_at=now + timedelta(days=165),
                                   created_at=now - timedelta(days=200 if p is not pm else 5)))
    db.add(DoctorPatientAccess(patient_id=pa.id, doctor_user_id=dr2.id, purpose="Cardiology review (demo)",
                               granting_authority="referral", granted_by=ananya.id, starts_at=now - timedelta(days=40),
                               expires_at=now + timedelta(days=50)))
    rel = CareRelationship(patient_id=pa.id, caregiver_user_id=kavya.id, invite_contact=kavya.email,
                           relationship_label="Daughter", status="active", granted_by=ananya.id,
                           scopes=["medications.view", "adherence.notify", "appointments.view", "appointments.book",
                                   "checkin.submit", "concerns.report", "instructions.view", "messages.patient",
                                   "careteam.contact"],
                           accepted_at=now - timedelta(days=30), authorized_at=now - timedelta(days=30),
                           starts_at=now - timedelta(days=30), expires_at=now + timedelta(days=335))
    db.add(rel)
    db.flush()
    db.add(ConsentRecord(patient_id=pa.id, actor_user_id=ananya.id, subject_user_id=kavya.id, action="grant",
                         resource="care_relationship", resource_id=rel.id, scopes=rel.scopes,
                         created_at=now - timedelta(days=30)))
    db.add(EscalationPolicy(patient_id=pa.id, notify_caregiver_approved=True))
    db.add(EscalationPolicy(patient_id=None))

    # ---------------- catalogue (no education text: no reviewed source is connected) ----------------
    met = catalogue(db, "Metformin", "500 mg", "tablet", ["metformin"], ["Glycomet (example)"])
    aml = catalogue(db, "Amlodipine", "5 mg", "tablet", ["amlodipine"])
    ator = catalogue(db, "Atorvastatin", "10 mg", "tablet", ["atorvastatin"])
    vitd = catalogue(db, "Cholecalciferol", "60000 IU", "capsule", ["cholecalciferol"], ["Vitamin D3 (example)"])
    amox = catalogue(db, "Amoxicillin", "500 mg", "capsule", ["amoxicillin"])
    ibu = catalogue(db, "Ibuprofen", "400 mg", "tablet", ["ibuprofen"])
    tel = catalogue(db, "Telmisartan", "40 mg", "tablet", ["telmisartan"])
    catalogue(db, "Paracetamol", "500 mg", "tablet", ["paracetamol"])
    catalogue(db, "Vitamin B12 (Methylcobalamin)", "500 mcg", "tablet", ["methylcobalamin"])
    catalogue(db, "Pantoprazole", "40 mg", "tablet", ["pantoprazole"])
    catalogue(db, "Levothyroxine", "50 mcg", "tablet", ["levothyroxine"])
    catalogue(db, "Losartan", "50 mg", "tablet", ["losartan"])

    # ---------------- Ananya: upcoming meds, history, completed & discontinued ----------------
    it_met, v_met = prescribe(db, pa, dr, met, dose=1, unit="tablet", times=["08:00", "20:00"], freq="Twice daily",
                              start=today - timedelta(days=60), indication="Type 2 diabetes (documented)",
                              food="Take with meals", brand="Glycomet (example)", org_id=clinic.id)
    it_aml, v_aml = prescribe(db, pa, dr2, aml, dose=1, unit="tablet", times=["09:00"], freq="Once daily",
                              start=today - timedelta(days=40), indication="Hypertension (documented)", org_id=hosp.id,
                              created_days_ago=40)
    it_at, v_at = prescribe(db, pa, dr, ator, dose=1, unit="tablet", times=["21:00"], freq="Once daily at night",
                            start=today - timedelta(days=60), org_id=clinic.id)
    it_vd, v_vd = prescribe(db, pa, dr, vitd, dose=1, unit="capsule", times=["10:00"], freq="Once weekly (Sunday)",
                            start=today - timedelta(days=60), end=today + timedelta(days=30), days_of_week=[6],
                            food="Take after a meal", org_id=clinic.id)
    prescribe(db, pa, gp, amox, dose=1, unit="capsule", times=["08:00", "14:00", "20:00"], freq="Three times daily",
              start=today - timedelta(days=120), end=today - timedelta(days=113), status="completed",
              indication="Documented: upper respiratory infection", created_days_ago=120)
    it_ibu, _ = prescribe(db, pa, gp, ibu, dose=1, unit="tablet", times=["13:00"], freq="Once daily after lunch",
                          start=today - timedelta(days=90), status="discontinued", created_days_ago=90)
    it_ibu.discontinued_at = it_ibu.discontinue_effective = now - timedelta(days=75)
    it_ibu.discontinue_reason = "Pain resolved; avoid long-term NSAID use (demo)"
    # a version history example: metformin dose change
    v_met.status = "superseded"
    v2 = PrescriptionVersion(item_id=it_met.id, version_no=2, status="current", generic_name="Metformin",
                             brand_name="Glycomet (example)", strength="500 mg", dosage_form="tablet", dose_amount=1,
                             dose_unit="tablet", route="oral", frequency_label="Twice daily",
                             indication="Type 2 diabetes (documented)", start_date=today - timedelta(days=60),
                             food_instructions="Take with breakfast and dinner",
                             effective_from=now - timedelta(days=20), created_by=dr.id,
                             change_reason="Clarified food timing after review (demo)",
                             created_at=now - timedelta(days=20))
    v2.schedule = MedicationSchedule(times_of_day=["08:00", "20:00"])
    db.add(v2)
    it_met.current_version_no, it_met.lock_version = 2, 2
    db.flush()

    pattern = lambda d, t: ("taken_reported" if random.random() < 0.82 else  # noqa: E731
                            random.choice(["missed_reported", "unconfirmed", "skipped"]))
    history(db, pa, it_met, v2, 14, pattern)
    history(db, pa, it_aml, v_aml, 14, pattern)
    history(db, pa, it_at, v_at, 14, lambda d, t: "taken_reported" if d % 5 else "unconfirmed")

    for dx_name, code in (("Type 2 diabetes mellitus", "E11"), ("Essential hypertension", "I10")):
        db.add(Diagnosis(patient_id=pa.id, name=dx_name, code=code, status="active", recorded_by=dr.id,
                         onset_date=today - timedelta(days=900)))
    db.add(Allergy(patient_id=pa.id, substance="Sulfonamide antibiotics", substance_ingredient="sulfamethoxazole",
                   reaction="Skin rash", severity="moderate", recorded_by=dr.id))
    timeline = [
        ("consultation", "Diabetes review", "HbA1c trending down; continue current plan (demo).", 20, dr, clinic),
        ("lab_report", "HbA1c", "HbA1c 7.4% (demo value)", 25, dr, None),
        ("lab_report", "Lipid profile", "LDL 118 mg/dL (demo value)", 25, dr, None),
        ("hospital_visit", "Cardiology outpatient visit", "BP 148/92 (demo). Started amlodipine.", 40, dr2, hosp),
        ("consultation", "Respiratory infection", "Amoxicillin course prescribed (demo).", 120, gp, hosp),
        ("procedure", "Retinal screening", "No diabetic retinopathy seen (demo).", 200, None, hosp),
        ("discharge_summary", "Day-care discharge summary", "Observation after dizziness episode; discharged (demo).", 300, gp, hosp),
    ]
    for rtype, title, summary, ago, doc, o in timeline:
        db.add(MedicalRecord(patient_id=pa.id, record_type=rtype, title=title, summary=summary,
                             occurred_at=now - timedelta(days=ago), doctor_user_id=doc.id if doc else None,
                             organization_id=o.id if o else None, provenance="demo",
                             medication_names=["Amlodipine"] if "amlodipine" in summary.lower() else [],
                             data={"HbA1c": "7.4 %"} if title == "HbA1c" else {}))
    db.add(FollowUpInstruction(patient_id=pa.id, author_user_id=dr.id, kind="instruction", audience="both",
                               title="Check fasting blood sugar twice a week",
                               description="Record readings in DoseWISE or a notebook and bring them to your next visit.",
                               priority="normal", requires_ack=True))
    db.add(FollowUpInstruction(patient_id=pa.id, author_user_id=dr.id, kind="follow_up", audience="patient",
                               title="HbA1c review", description="Repeat HbA1c and review in clinic.",
                               timeframe="in 3 months", due_date=today + timedelta(days=70), appointment_request=True))
    db.add(Message(patient_id=pa.id, sender_user_id=dr.id, recipient_user_id=ananya.id, kind="message",
                   body="Hello Ananya, your recent HbA1c looks better. Keep going with the current plan. (demo)",
                   created_at=now - timedelta(days=19)))

    # uploaded prescription awaiting doctor verification
    png = demo_prescription_png()
    doc = UploadedDocument(patient_id=pa.id, uploaded_by=ananya.id, category="prescription",
                           title="Clinic prescription (photo)", original_filename="prescription-demo.png",
                           mime_type="image/png", size_bytes=len(png), sha256=storage.sha256(png),
                           storage_backend="local", storage_key="", is_demo=True)
    db.add(doc)
    db.flush()
    doc.storage_key = f"patients/{pa.id}/{doc.id}"
    doc.storage_backend = storage.put(doc.storage_key, png, "image/png")
    meds = [{"name": "Vitamin B12 (Methylcobalamin)", "strength": "500 mcg", "dose": "1 tablet", "route": "oral",
             "frequency": "once daily", "duration": "30 days"}]
    db.add(OCRExtraction(document_id=doc.id, patient_id=pa.id, engine="demo", quality={"kind": "image", "warnings": []},
                         raw_text="(demo) Vitamin B12 500 mcg tablet 1 tablet oral once daily x 30 days",
                         extracted={"medications": meds}, confidence=0.78, uncertain_fields=["medications[0].duration"],
                         status="patient_reviewed", patient_corrected={"doctor_name": "Dr. Arjun Mehra",
                                                                       "instructions": "Take after breakfast",
                                                                       "medications": meds},
                         reviewed_by_patient_at=now - timedelta(hours=5),
                         history=[{"at": (now - timedelta(hours=6)).isoformat(), "event": "extracted", "engine": "demo"},
                                  {"at": (now - timedelta(hours=5)).isoformat(), "event": "submitted_for_verification"}]))

    # ---------------- Rahul: unconfirmed streak -> escalation + support case ----------------
    it_tel, v_tel = prescribe(db, pr, dr, tel, dose=1, unit="tablet", times=["08:30"], freq="Once daily",
                              start=today - timedelta(days=30), indication="Hypertension (documented)")
    it_met2, v_met2 = prescribe(db, pr, dr, met, dose=1, unit="tablet", times=["08:30", "20:30"], freq="Twice daily",
                                start=today - timedelta(days=30))
    history(db, pr, it_tel, v_tel, 10, lambda d, t: "unconfirmed" if d <= 4 else "taken_reported")
    history(db, pr, it_met2, v_met2, 10, lambda d, t: "unconfirmed" if d <= 4 else "taken_reported")
    db.add(Diagnosis(patient_id=pr.id, name="Essential hypertension", code="I10", recorded_by=dr.id))
    db.flush()
    sc = escalation.open_support_case(db, pr.id, "missed_medication",
                                      "Repeated unconfirmed doses over 4 days after reminders and check-ins (demo).")
    db.add(EscalationCase(patient_id=pr.id, trigger="missed_medication", stage=5, consecutive_unconfirmed=12,
                          support_case_id=sc.id, history=[{"at": now.isoformat(), "stage": 5, "event": "case created (demo)"}]))

    # ---------------- Meera: completed course only ----------------
    prescribe(db, pm, dr, amox, dose=1, unit="capsule", times=["09:00", "21:00"], freq="Twice daily",
              start=today - timedelta(days=30), end=today - timedelta(days=23), status="completed", created_days_ago=30)
    db.add(MedicalRecord(patient_id=pm.id, record_type="consultation", title="Sore throat", provenance="demo",
                         summary="Short antibiotic course completed (demo).", occurred_at=now - timedelta(days=30),
                         doctor_user_id=dr.id, organization_id=clinic.id))

    # ---------------- availability + an upcoming appointment ----------------
    for d in range(5):
        db.add(DoctorAvailability(doctor_user_id=dr.id, organization_id=clinic.id, weekday=d, start_time="10:00",
                                  end_time="13:00", slot_minutes=20))
        db.add(DoctorAvailability(doctor_user_id=dr2.id, organization_id=hosp.id, weekday=d, start_time="14:00",
                                  end_time="17:00", slot_minutes=30))
    db.add(DoctorAvailability(doctor_user_id=gp.id, organization_id=hosp.id, weekday=5, start_time="09:00",
                              end_time="12:00", slot_minutes=15, capacity=2))
    db.flush()
    for d in (dr, dr2, gp):
        booking.materialize_slots(db, d.id)
    db.flush()
    slot = db.execute(select(AvailabilitySlot).where(AvailabilitySlot.doctor_user_id == dr.id,
                                                     AvailabilitySlot.starts_at > now + timedelta(days=2))
                      .order_by(AvailabilitySlot.starts_at)).scalars().first()
    if slot:
        h = booking.hold(db, ananya, pa, slot.id)
        booking.confirm(db, ananya, pa, h.id, "Diabetes follow-up (demo)")

    db.add(Notification(user_id=ananya.id, patient_id=pa.id, category="doctor_instruction", title="New instruction",
                        body="Check fasting blood sugar twice a week", channel="in_app", delivery_status="delivered",
                        created_at=now - timedelta(days=2)))
    db.add(Notification(user_id=kavya.id, patient_id=pa.id, category="caregiver_update", title="Weekly summary",
                        body="Ananya reported most doses this week.", channel="in_app", delivery_status="delivered",
                        created_at=now - timedelta(days=1)))
    audit.record(db, action="demo_seed", resource_type="system", reason="synthetic data created")
    db.commit()
    print("Demo data created. Personas: patient, patient2, doctor, caregiver, support, admin (use the demo login).")


def main():
    s = get_settings()
    if "--reset" in sys.argv:
        if not s.is_dev:
            raise SystemExit("--reset is only allowed in development")
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
