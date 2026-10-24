"""Starter data for DoseWISE: 10 patients, 10 doctors, a caregiver, a care coordinator and an admin,
with real-looking links between them (doctors who treat each patient, prescriptions, visits,
appointments, follow-ups). Every person, organisation and record here is fictional.

    python -m app.seed           # create the starter data if missing
    python -m app.seed --reset   # recreate everything (SQLite/dev only). Accounts people registered
                                 # themselves are kept and restored after the reset.

Sign-in for every starter account: the email listed in docs/ACCOUNTS.md with password SEED_PASSWORD.
"""
import random
import shutil
import sys
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core import audit
from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models import (
    Allergy,
    Appointment,
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
    PatientProfile,
    Prescription,
    PrescriptionItem,
    PrescriptionVersion,
    SupportProfile,
    User,
)
from app.models.base import utcnow
from app.services import booking, escalation

IST = ZoneInfo("Asia/Kolkata")
SEED_PASSWORD = "Dosewise_2026"
DOMAIN = "dosewise.in"
random.seed(42)

_pw_hash = None


def mk_user(db, email, role, name, phone=None, color="#0f766e", preferred=None):
    global _pw_hash
    _pw_hash = _pw_hash or hash_password(SEED_PASSWORD)
    # is_demo marks starter accounts internally (so a reset can tell them from registered ones); it is
    # never shown in the interface. Email notifications stay off so nothing is sent to these addresses.
    u = User(email=email, role=role, full_name=name, phone=phone, avatar_color=color, preferred_name=preferred,
             password_hash=_pw_hash, email_verified=True, is_demo=True,
             preferences={"language": "en", "theme": "system", "notifications": {
                 "medication_reminders": {"email": False, "sms": False},
                 "appointment_reminders": {"email": False, "sms": False}}})
    db.add(u)
    db.flush()
    return u


def org(db, kind, name, address, city, lat, lng, **kw):
    o = HealthcareOrganization(kind=kind, name=name, address=address, city=city, state="Karnataka", latitude=lat,
                               longitude=lng, data_source="dosewise", is_verified=True, **kw)
    db.add(o)
    db.flush()
    return o


def catalogue(db, generic, strength, form, ingredients, brands=()):
    c = MedicationCatalogue(generic_name=generic, strength=strength, dosage_form=form, ingredients=list(ingredients),
                            brand_names=list(brands), data_source="dosewise")
    db.add(c)
    db.flush()
    return c


def prescribe(db, patient, doctor, cat, *, dose, unit, times, freq, start, end=None, status="active", indication=None,
              food=None, special=None, created_days_ago=60, days_of_week=None, interval=1, org_id=None, brand=None):
    created = utcnow() - timedelta(days=created_days_ago)
    rx = Prescription(patient_id=patient.id, prescriber_user_id=doctor.id, source="impulse",
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
                            created_by=doctor.id, change_reason="Initial prescription",
                            refills_allowed=2, quantity="30", created_at=created)
    v.schedule = MedicationSchedule(times_of_day=times, days_of_week=days_of_week, interval_days=interval)
    db.add(v)
    db.flush()
    return it, v


def history(db, patient, it, v, days, pattern):
    """pattern(day_index, time) -> status for past doses."""
    today = utcnow().astimezone(IST).date()
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


def grant(db, patient, doctor, days_ago, purpose, authority="patient_grant"):
    now = utcnow()
    db.add(DoctorPatientAccess(patient_id=patient.id, doctor_user_id=doctor.id, purpose=purpose,
                               granting_authority=authority, granted_by=patient.user_id,
                               scopes=["clinical.read", "clinical.write", "prescribe"],
                               starts_at=now - timedelta(days=days_ago), expires_at=now + timedelta(days=180),
                               created_at=now - timedelta(days=days_ago)))


def past_visit(db, patient, doctor, organization, days_ago, reason, hour=11):
    """A completed consultation in the patient's appointment history."""
    day = utcnow().astimezone(IST).date() - timedelta(days=days_ago)
    start = datetime.combine(day, time(hour, 0), tzinfo=IST)
    db.add(Appointment(patient_id=patient.id, doctor_user_id=doctor.id, organization_id=organization.id,
                       starts_at=start, ends_at=start + timedelta(minutes=20), status="completed", reason=reason,
                       booked_by=patient.user_id, history=[{"at": (start - timedelta(days=3)).isoformat(), "event": "booked"},
                                                           {"at": start.isoformat(), "event": "completed"}]))


def records(db, patient, items):
    """Exactly three medical-history entries per patient: (type, title, summary, days_ago, doctor, org, meds)."""
    assert len(items) == 3
    now = utcnow()
    for rtype, title, summary, ago, doc, o, meds in items:
        db.add(MedicalRecord(patient_id=patient.id, record_type=rtype, title=title, summary=summary,
                             occurred_at=now - timedelta(days=ago), doctor_user_id=doc.id,
                             organization_id=o.id if o else None, provenance="clinician_verified",
                             medication_names=meds, data={}))


def seed(db):
    if db.execute(select(User).where(User.is_demo.is_(True))).first():
        print("Starter data already present. Use --reset to recreate.")
        return
    now = utcnow()
    today = now.astimezone(IST).date()

    # ---------------- organisations ----------------
    lotus = org(db, "hospital", "Lotus Multispeciality Hospital", "14 Ring Road, Indiranagar", "Bengaluru", 12.9719, 77.6412,
                phone="+91-80-4110-2200", opening_hours="24 hours", departments=["Cardiology", "General Medicine",
                "Paediatrics", "Emergency"], services=["Emergency care", "Inpatient", "Diagnostics"])
    riverside = org(db, "hospital", "Riverside Medical Centre", "1 Kanakapura Road, Jayanagar", "Bengaluru", 12.9250, 77.5838,
                    phone="+91-80-4220-3300", opening_hours="24 hours", departments=["Orthopaedics", "Neurology", "Nephrology"],
                    services=["Emergency care", "Outpatient", "Dialysis"])
    greenleaf = org(db, "clinic", "Greenleaf Family Clinic", "7 80 Feet Road, Koramangala", "Bengaluru", 12.9352, 77.6245,
                    phone="+91-80-4330-4400", opening_hours="Mon–Sat 9:00–19:00",
                    departments=["Endocrinology", "Dermatology"], services=["Consultations", "Vaccinations"])
    sunrise = org(db, "clinic", "Sunrise Women & Chest Clinic", "22 Sampige Road, Malleshwaram", "Bengaluru", 13.0031, 77.5643,
                  phone="+91-80-4440-5500", opening_hours="Mon–Sat 10:00–20:00",
                  departments=["Obstetrics & Gynaecology", "Respiratory Medicine"], services=["Consultations", "Lung function tests"])
    org(db, "pharmacy", "CarePlus Pharmacy", "22 27th Main, HSR Layout", "Bengaluru", 12.9116, 77.6474,
        phone="+91-80-4550-6600", opening_hours="Daily 8:00–22:00", services=["Prescriptions", "Home delivery"])
    org(db, "pharmacy", "Medway Pharmacy", "3 11th Main, Jayanagar 4th Block", "Bengaluru", 12.9250, 77.5938,
        phone="+91-80-4660-7700", opening_hours="Daily 7:00–23:00", services=["Prescriptions"])
    org(db, "laboratory", "Clearpath Diagnostics", "9 ITPL Main Road, Whitefield", "Bengaluru", 12.9698, 77.7500,
        phone="+91-80-4770-8800", opening_hours="Mon–Sun 7:00–20:00", services=["Blood tests", "HbA1c", "Lipid profile"])

    # ---------------- staff ----------------
    admin = mk_user(db, f"admin@{DOMAIN}", "admin", "DoseWISE Administrator", color="#334155")
    sup = mk_user(db, f"priya.nair@{DOMAIN}", "support", "Priya Nair", "9000000041", "#2563eb", "Priya")
    db.add(SupportProfile(user_id=sup.id, team="Care coordination", on_duty=True))

    # ---------------- 10 doctors ----------------
    def doctor(first, last, speciality, reg, organization, color, languages, phone):
        u = mk_user(db, f"dr.{first.lower()}.{last.lower()}@{DOMAIN}", "doctor", f"Dr. {first} {last}", phone, color)
        db.add(DoctorProfile(user_id=u.id, speciality=speciality, registration_number=reg,
                             registration_council="Karnataka Medical Council", verification_status="verified",
                             verified_by=admin.id, verified_at=now, organization_id=organization.id,
                             bio=f"{speciality} consultant at {organization.name}.", languages=languages,
                             consultation_types=["in_person"]))
        return u

    mehra = doctor("Arjun", "Mehra", "Endocrinology", "KMC-48213", greenleaf, "#0e7490", ["English", "Hindi", "Kannada"], "9000000011")
    khan = doctor("Sara", "Khan", "Cardiology", "KMC-51907", lotus, "#7c3aed", ["English", "Hindi", "Tamil"], "9000000012")
    iyer = doctor("Leela", "Iyer", "General Medicine", "KMC-39466", lotus, "#be185d", ["English", "Telugu", "Kannada"], "9000000013")
    nair = doctor("Vikram", "Nair", "Orthopaedics", "KMC-44120", riverside, "#a16207", ["English", "Malayalam"], "9000000014")
    desai = doctor("Priyanka", "Desai", "Dermatology, Venereology & Leprosy", "KMC-57381", greenleaf, "#db2777", ["English", "Hindi"], "9000000015")
    kulkarni = doctor("Rohan", "Kulkarni", "Neurology", "KMC-46052", riverside, "#2563eb", ["English", "Kannada", "Hindi"], "9000000016")
    sheikh = doctor("Fatima", "Sheikh", "Paediatrics", "KMC-52814", lotus, "#059669", ["English", "Hindi", "Urdu"], "9000000017")
    reddy = doctor("Karthik", "Reddy", "Nephrology", "KMC-49735", riverside, "#c2410c", ["English", "Telugu"], "9000000018")
    sundaram = doctor("Meenakshi", "Sundaram", "Obstetrics & Gynaecology", "KMC-43598", sunrise, "#9333ea", ["English", "Tamil"], "9000000019")
    arao = doctor("Aditya", "Rao", "Respiratory Medicine", "KMC-55276", sunrise, "#0f766e", ["English", "Kannada"], "9000000020")
    doctors = [(mehra, greenleaf), (khan, lotus), (iyer, lotus), (nair, riverside), (desai, greenleaf),
               (kulkarni, riverside), (sheikh, lotus), (reddy, riverside), (sundaram, sunrise), (arao, sunrise)]

    # ---------------- 10 patients ----------------
    def patient(first, last, mrn, access_id, dob, sex, blood, allergy_status, condition_status, color, phone, **kw):
        u = mk_user(db, f"{first.lower()}.{last.lower()}@{DOMAIN}", "patient", f"{first} {last}", phone, color, first)
        p = PatientProfile(user_id=u.id, mrn=mrn, access_id=access_id, access_id_created_at=now, date_of_birth=dob,
                           sex=sex, blood_group=blood, allergy_status=allergy_status, condition_status=condition_status, **kw)
        db.add(p)
        db.flush()
        return u, p

    ananya_u, ananya = patient("Ananya", "Rao", "DWP-100101", "DW-ANANYA", date(1961, 4, 12), "Female", "B+",
                               "has_allergies", "has_conditions", "#0f766e", "9000000021",
                               emergency_contact_name="Kavya Rao", emergency_contact_phone="9000000031",
                               emergency_contact_relation="Daughter", emergency_info_shareable=True)
    rahul_u, rahul = patient("Rahul", "Verma", "DWP-100102", "DW-R7HKV2", date(1974, 9, 3), "Male", "O+",
                             "none_known", "has_conditions", "#9333ea", "9000000022")
    meera_u, meera = patient("Meera", "Iyer", "DWP-100103", "DW-M3ERQ8", date(1990, 1, 22), "Female", "A+",
                             "none_known", "none_known", "#c2410c", "9000000023")
    suresh_u, suresh = patient("Suresh", "Patil", "DWP-100104", "DW-S5PTL9", date(1958, 7, 30), "Male", "AB+",
                               "has_allergies", "has_conditions", "#0e7490", "9000000024",
                               emergency_contact_name="Shobha Patil", emergency_contact_phone="9000000034",
                               emergency_contact_relation="Wife", emergency_info_shareable=True)
    lakshmi_u, lakshmi = patient("Lakshmi", "Narayan", "DWP-100105", "DW-L4KNR6", date(1966, 11, 5), "Female", "B-",
                                 "none_known", "has_conditions", "#db2777", "9000000025")
    imran_u, imran = patient("Imran", "Qureshi", "DWP-100106", "DW-Q8RMN3", date(1982, 3, 17), "Male", "O-",
                             "has_allergies", "has_conditions", "#2563eb", "9000000026")
    divya_u, divya = patient("Divya", "Menon", "DWP-100107", "DW-D2MNV7", date(1995, 8, 9), "Female", "A-",
                             "none_known", "has_conditions", "#7c3aed", "9000000027")
    arvind_u, arvind = patient("Arvind", "Krishnan", "DWP-100108", "DW-K9RVD4", date(1949, 2, 26), "Male", "B+",
                               "none_known", "has_conditions", "#a16207", "9000000028",
                               emergency_contact_name="Ramesh Krishnan", emergency_contact_phone="9000000038",
                               emergency_contact_relation="Son", emergency_info_shareable=True)
    aarav_u, aarav = patient("Aarav", "Shetty", "DWP-100109", "DW-A6SHT5", date(2015, 6, 14), "Male", "O+",
                             "has_allergies", "has_conditions", "#059669", "9000000029",
                             emergency_contact_name="Rekha Shetty", emergency_contact_phone="9000000039",
                             emergency_contact_relation="Mother", emergency_info_shareable=True)
    neha_u, neha = patient("Neha", "Gupta", "DWP-100110", "DW-N5GPT8", date(1988, 12, 1), "Female", "AB-",
                           "none_known", "has_conditions", "#334155", "9000000030")

    # height (cm), weight (kg); BMI is calculated from these
    for p, h, w in ((ananya, 156, 68), (rahul, 172, 84), (meera, 162, 55), (suresh, 168, 74), (lakshmi, 154, 70),
                    (imran, 176, 79), (divya, 160, 63), (arvind, 170, 66), (aarav, 138, 32), (neha, 158, 72)):
        p.height_cm, p.weight_kg = h, w

    kavya = mk_user(db, f"kavya.rao@{DOMAIN}", "caregiver", "Kavya Rao", "9000000031", "#db2777", "Kavya")
    db.add(CaregiverProfile(user_id=kavya.id, relationship_note="Daughter of Ananya Rao"))
    db.flush()

    # ---------------- medicine catalogue ----------------
    met = catalogue(db, "Metformin", "500 mg", "tablet", ["metformin"], ["Glycomet"])
    aml = catalogue(db, "Amlodipine", "5 mg", "tablet", ["amlodipine"], ["Amlong"])
    ator = catalogue(db, "Atorvastatin", "10 mg", "tablet", ["atorvastatin"], ["Atorva"])
    vitd = catalogue(db, "Cholecalciferol", "60000 IU", "capsule", ["cholecalciferol"], ["D-Rise"])
    amox = catalogue(db, "Amoxicillin", "500 mg", "capsule", ["amoxicillin"], ["Mox"])
    tel = catalogue(db, "Telmisartan", "40 mg", "tablet", ["telmisartan"], ["Telma"])
    losartan = catalogue(db, "Losartan", "50 mg", "tablet", ["losartan"], ["Losar"])
    levo = catalogue(db, "Levothyroxine", "50 mcg", "tablet", ["levothyroxine"], ["Thyronorm"])
    monte = catalogue(db, "Montelukast", "10 mg", "tablet", ["montelukast"], ["Montair"])
    folic = catalogue(db, "Folic acid", "5 mg", "tablet", ["folic acid"], ["Folvite"])
    iron = catalogue(db, "Ferrous ascorbate", "100 mg", "tablet", ["ferrous ascorbate"], ["Orofer XT"])
    levet = catalogue(db, "Levetiracetam", "500 mg", "tablet", ["levetiracetam"], ["Levera"])
    glucos = catalogue(db, "Glucosamine", "500 mg", "tablet", ["glucosamine"])
    cetir = catalogue(db, "Cetirizine", "10 mg", "tablet", ["cetirizine"], ["Cetzine"])
    catalogue(db, "Paracetamol", "500 mg", "tablet", ["paracetamol"], ["Dolo"])
    catalogue(db, "Vitamin B12 (Methylcobalamin)", "500 mcg", "tablet", ["methylcobalamin"])
    catalogue(db, "Pantoprazole", "40 mg", "tablet", ["pantoprazole"], ["Pan"])
    catalogue(db, "Ibuprofen", "400 mg", "tablet", ["ibuprofen"])

    taken_mostly = lambda d, t: ("taken_reported" if random.random() < 0.85 else  # noqa: E731
                                 random.choice(["missed_reported", "unconfirmed", "skipped"]))

    # ---- Ananya Rao: diabetes + hypertension; Mehra, Khan, Iyer; caregiver Kavya ----
    for d, ago, why in ((mehra, 400, "Diabetes care"), (khan, 120, "Blood pressure review"), (iyer, 30, "General check-ups")):
        grant(db, ananya, d, ago, why)
    it, v = prescribe(db, ananya, mehra, met, dose=1, unit="tablet", times=["08:00", "20:00"], freq="Twice daily",
                      start=today - timedelta(days=90), indication="Type 2 diabetes", food="Take with breakfast and dinner",
                      brand="Glycomet", org_id=greenleaf.id, created_days_ago=90)
    history(db, ananya, it, v, 14, taken_mostly)
    it, v = prescribe(db, ananya, khan, aml, dose=1, unit="tablet", times=["09:00"], freq="Once daily",
                      start=today - timedelta(days=60), indication="Hypertension", org_id=lotus.id, created_days_ago=60)
    history(db, ananya, it, v, 14, taken_mostly)
    prescribe(db, ananya, mehra, ator, dose=1, unit="tablet", times=["21:00"], freq="Once daily at night",
              start=today - timedelta(days=90), indication="High cholesterol", org_id=greenleaf.id, created_days_ago=90)
    prescribe(db, ananya, iyer, vitd, dose=1, unit="capsule", times=["10:00"], freq="Once weekly (Sunday)",
              start=today - timedelta(days=30), end=today + timedelta(days=60), days_of_week=[6],
              food="Take after a meal", org_id=lotus.id, created_days_ago=30)
    for name, code in (("Type 2 diabetes mellitus", "E11"), ("Essential hypertension", "I10")):
        db.add(Diagnosis(patient_id=ananya.id, name=name, code=code, status="active", recorded_by=mehra.id,
                         onset_date=today - timedelta(days=1500)))
    db.add(Allergy(patient_id=ananya.id, substance="Sulfonamide antibiotics", substance_ingredient="sulfamethoxazole",
                   reaction="Skin rash", severity="moderate", recorded_by=mehra.id))
    records(db, ananya, [
        ("consultation", "Diabetes review", "HbA1c down from 8.1% to 7.4%. Continue metformin; diet advice given.", 21, mehra, greenleaf, ["Metformin"]),
        ("hospital_visit", "Cardiology outpatient visit", "BP 148/92 on two readings. Started amlodipine 5 mg.", 60, khan, lotus, ["Amlodipine"]),
        ("lab_report", "Lipid profile", "LDL 118 mg/dL, HDL 46 mg/dL. Continue atorvastatin.", 25, mehra, None, ["Atorvastatin"]),
    ])
    past_visit(db, ananya, mehra, greenleaf, 21, "Diabetes review")
    past_visit(db, ananya, khan, lotus, 60, "Blood pressure check", hour=15)
    rel = CareRelationship(patient_id=ananya.id, caregiver_user_id=kavya.id, invite_contact=kavya.email,
                           relationship_label="Daughter", status="active", granted_by=ananya_u.id,
                           scopes=["medications.view", "adherence.notify", "appointments.view", "appointments.book",
                                   "checkin.submit", "concerns.report", "instructions.view", "messages.patient",
                                   "careteam.contact"],
                           accepted_at=now - timedelta(days=30), authorized_at=now - timedelta(days=30),
                           starts_at=now - timedelta(days=30), expires_at=now + timedelta(days=335))
    db.add(rel)
    db.flush()
    db.add(ConsentRecord(patient_id=ananya.id, actor_user_id=ananya_u.id, subject_user_id=kavya.id, action="grant",
                         resource="care_relationship", resource_id=rel.id, scopes=rel.scopes, created_at=now - timedelta(days=30)))
    db.add(EscalationPolicy(patient_id=ananya.id, notify_caregiver_approved=True))
    db.add(FollowUpInstruction(patient_id=ananya.id, author_user_id=mehra.id, kind="instruction", audience="both",
                               title="Check fasting blood sugar twice a week",
                               description="Record readings in DoseWISE or a notebook and bring them to your next visit.",
                               priority="normal", requires_ack=True))
    db.add(FollowUpInstruction(patient_id=ananya.id, author_user_id=mehra.id, kind="follow_up", audience="patient",
                               title="HbA1c review", description="Repeat HbA1c and review in clinic.",
                               timeframe="in 3 months", due_date=today + timedelta(days=70), appointment_request=True))
    db.add(Message(patient_id=ananya.id, sender_user_id=mehra.id, recipient_user_id=ananya_u.id, kind="message",
                   body="Hello Ananya, your recent HbA1c looks better. Keep going with the current plan.",
                   created_at=now - timedelta(days=19)))

    # ---- Rahul Verma: hypertension + diabetes; Mehra, Khan; doses unconfirmed -> coordinator case ----
    grant(db, rahul, mehra, 200, "Diabetes care")
    grant(db, rahul, khan, 90, "Hypertension care")
    it, v = prescribe(db, rahul, khan, tel, dose=1, unit="tablet", times=["08:30"], freq="Once daily",
                      start=today - timedelta(days=45), indication="Hypertension", org_id=lotus.id, created_days_ago=45)
    history(db, rahul, it, v, 10, lambda d, t: "unconfirmed" if d <= 4 else "taken_reported")
    it, v = prescribe(db, rahul, mehra, met, dose=1, unit="tablet", times=["08:30", "20:30"], freq="Twice daily",
                      start=today - timedelta(days=45), indication="Type 2 diabetes", org_id=greenleaf.id, created_days_ago=45)
    history(db, rahul, it, v, 10, lambda d, t: "unconfirmed" if d <= 4 else "taken_reported")
    db.add(Diagnosis(patient_id=rahul.id, name="Essential hypertension", code="I10", recorded_by=khan.id))
    db.add(Diagnosis(patient_id=rahul.id, name="Type 2 diabetes mellitus", code="E11", recorded_by=mehra.id))
    records(db, rahul, [
        ("consultation", "Hypertension consultation", "BP 156/96. Started telmisartan 40 mg; reduce salt.", 45, khan, lotus, ["Telmisartan"]),
        ("lab_report", "Fasting blood sugar", "FBS 142 mg/dL; HbA1c 7.9%.", 50, mehra, None, []),
        ("consultation", "Diabetes consultation", "Started metformin 500 mg twice daily.", 45, mehra, greenleaf, ["Metformin"]),
    ])
    past_visit(db, rahul, khan, lotus, 45, "Hypertension consultation", hour=14)
    db.flush()
    sc = escalation.open_support_case(db, rahul.id, "missed_medication",
                                      "Repeated unconfirmed doses over 4 days after reminders and check-ins.")
    db.add(EscalationCase(patient_id=rahul.id, trigger="missed_medication", stage=5, consecutive_unconfirmed=12,
                          support_case_id=sc.id, history=[{"at": now.isoformat(), "stage": 5, "event": "case created"}]))

    # ---- Meera Iyer: completed antibiotic course; Iyer ----
    grant(db, meera, iyer, 40, "General check-ups")
    prescribe(db, meera, iyer, amox, dose=1, unit="capsule", times=["09:00", "21:00"], freq="Twice daily",
              start=today - timedelta(days=35), end=today - timedelta(days=28), status="completed",
              indication="Acute pharyngitis", org_id=lotus.id, created_days_ago=35)
    records(db, meera, [
        ("consultation", "Sore throat", "Acute pharyngitis. Amoxicillin for 7 days.", 35, iyer, lotus, ["Amoxicillin"]),
        ("consultation", "Follow-up visit", "Symptoms resolved after the antibiotic course.", 26, iyer, lotus, []),
        ("lab_report", "Complete blood count", "Haemoglobin 12.6 g/dL; all values within range.", 90, iyer, None, []),
    ])
    past_visit(db, meera, iyer, lotus, 35, "Sore throat and fever")
    past_visit(db, meera, iyer, lotus, 26, "Follow-up")

    # ---- Suresh Patil: chronic kidney disease + hypertension; Reddy, Khan ----
    grant(db, suresh, reddy, 300, "Kidney care")
    grant(db, suresh, khan, 150, "Blood pressure care")
    it, v = prescribe(db, suresh, reddy, losartan, dose=1, unit="tablet", times=["09:00"], freq="Once daily",
                      start=today - timedelta(days=120), indication="Hypertension with CKD", org_id=riverside.id,
                      created_days_ago=120)
    history(db, suresh, it, v, 10, taken_mostly)
    prescribe(db, suresh, khan, ator, dose=1, unit="tablet", times=["21:00"], freq="Once daily at night",
              start=today - timedelta(days=150), indication="High cholesterol", org_id=lotus.id, created_days_ago=150)
    db.add(Diagnosis(patient_id=suresh.id, name="Chronic kidney disease, stage 3", code="N18.3", recorded_by=reddy.id))
    db.add(Diagnosis(patient_id=suresh.id, name="Essential hypertension", code="I10", recorded_by=khan.id))
    db.add(Allergy(patient_id=suresh.id, substance="Ibuprofen", substance_ingredient="ibuprofen",
                   reaction="Worsened kidney function", severity="severe", recorded_by=reddy.id))
    records(db, suresh, [
        ("lab_report", "Kidney function test", "Creatinine 1.8 mg/dL; eGFR 41. Stable since last test.", 14, reddy, None, []),
        ("consultation", "Nephrology review", "CKD stage 3. Continue losartan; avoid NSAID pain killers.", 14, reddy, riverside, ["Losartan"]),
        ("hospital_visit", "Cardiology outpatient visit", "BP 138/84 on losartan. Lipids reviewed.", 150, khan, lotus, ["Atorvastatin"]),
    ])
    past_visit(db, suresh, reddy, riverside, 14, "Kidney function review")

    # ---- Lakshmi Narayan: hypothyroidism; Mehra, Desai ----
    grant(db, lakshmi, mehra, 250, "Thyroid care")
    grant(db, lakshmi, desai, 20, "Skin consultation")
    it, v = prescribe(db, lakshmi, mehra, levo, dose=1, unit="tablet", times=["06:30"], freq="Once daily, empty stomach",
                      start=today - timedelta(days=200), indication="Hypothyroidism", food="30 minutes before breakfast",
                      org_id=greenleaf.id, created_days_ago=200)
    history(db, lakshmi, it, v, 10, taken_mostly)
    db.add(Diagnosis(patient_id=lakshmi.id, name="Hypothyroidism", code="E03.9", recorded_by=mehra.id))
    records(db, lakshmi, [
        ("lab_report", "Thyroid profile", "TSH 3.1 mIU/L on levothyroxine 50 mcg.", 30, mehra, None, ["Levothyroxine"]),
        ("consultation", "Thyroid review", "Dose unchanged; repeat TSH in 6 months.", 28, mehra, greenleaf, ["Levothyroxine"]),
        ("consultation", "Dermatology consultation", "Mild seborrhoeic dermatitis; topical treatment advised.", 20, desai, greenleaf, []),
    ])
    past_visit(db, lakshmi, mehra, greenleaf, 28, "Thyroid review")
    past_visit(db, lakshmi, desai, greenleaf, 20, "Itchy scalp", hour=16)

    # ---- Imran Qureshi: asthma + allergic rhinitis; Aditya Rao, Iyer ----
    grant(db, imran, arao, 100, "Asthma care")
    grant(db, imran, iyer, 60, "General check-ups")
    it, v = prescribe(db, imran, arao, monte, dose=1, unit="tablet", times=["21:00"], freq="Once daily at night",
                      start=today - timedelta(days=100), indication="Asthma", org_id=sunrise.id, created_days_ago=100)
    history(db, imran, it, v, 10, taken_mostly)
    prescribe(db, imran, iyer, cetir, dose=1, unit="tablet", times=["21:30"], freq="Once daily at night",
              start=today - timedelta(days=60), end=today + timedelta(days=30), indication="Allergic rhinitis",
              org_id=lotus.id, created_days_ago=60)
    db.add(Diagnosis(patient_id=imran.id, name="Asthma", code="J45.9", recorded_by=arao.id))
    db.add(Allergy(patient_id=imran.id, substance="Penicillin", substance_ingredient="penicillin",
                   reaction="Hives", severity="moderate", recorded_by=iyer.id))
    records(db, imran, [
        ("procedure", "Lung function test", "Spirometry: mild reversible obstruction, consistent with asthma.", 100, arao, sunrise, []),
        ("consultation", "Asthma review", "Fewer night symptoms on montelukast. Inhaler technique checked.", 30, arao, sunrise, ["Montelukast"]),
        ("consultation", "Allergy consultation", "Seasonal allergic rhinitis. Cetirizine at night.", 60, iyer, lotus, ["Cetirizine"]),
    ])
    past_visit(db, imran, arao, sunrise, 30, "Asthma review", hour=17)

    # ---- Divya Menon: pregnancy care; Sundaram ----
    grant(db, divya, sundaram, 80, "Antenatal care")
    prescribe(db, divya, sundaram, folic, dose=1, unit="tablet", times=["09:00"], freq="Once daily",
              start=today - timedelta(days=80), indication="Antenatal supplement", org_id=sunrise.id, created_days_ago=80)
    it, v = prescribe(db, divya, sundaram, iron, dose=1, unit="tablet", times=["14:00"], freq="Once daily after lunch",
                      start=today - timedelta(days=50), indication="Mild anaemia", food="Take after lunch",
                      org_id=sunrise.id, created_days_ago=50)
    history(db, divya, it, v, 10, taken_mostly)
    db.add(Diagnosis(patient_id=divya.id, name="Pregnancy, second trimester", code="Z34.92", recorded_by=sundaram.id))
    records(db, divya, [
        ("consultation", "Antenatal visit", "12 weeks. Folic acid continued; routine tests ordered.", 80, sundaram, sunrise, ["Folic acid"]),
        ("lab_report", "Haemoglobin", "Hb 10.4 g/dL. Iron supplement started.", 50, sundaram, None, ["Ferrous ascorbate"]),
        ("procedure", "Anomaly scan", "Normal anatomy scan at 20 weeks.", 22, sundaram, sunrise, []),
    ])
    past_visit(db, divya, sundaram, sunrise, 22, "Antenatal visit and scan")

    # ---- Arvind Krishnan: epilepsy + knee osteoarthritis; Kulkarni, Nair ----
    grant(db, arvind, kulkarni, 365, "Epilepsy care")
    grant(db, arvind, nair, 45, "Knee pain")
    it, v = prescribe(db, arvind, kulkarni, levet, dose=1, unit="tablet", times=["08:00", "20:00"], freq="Twice daily",
                      start=today - timedelta(days=365), indication="Epilepsy", org_id=riverside.id, created_days_ago=365)
    history(db, arvind, it, v, 10, taken_mostly)
    prescribe(db, arvind, nair, glucos, dose=1, unit="tablet", times=["13:00"], freq="Once daily",
              start=today - timedelta(days=45), end=today + timedelta(days=45), indication="Knee osteoarthritis",
              org_id=riverside.id, created_days_ago=45)
    db.add(Diagnosis(patient_id=arvind.id, name="Epilepsy", code="G40.909", recorded_by=kulkarni.id))
    db.add(Diagnosis(patient_id=arvind.id, name="Primary osteoarthritis of knee", code="M17.0", recorded_by=nair.id))
    records(db, arvind, [
        ("consultation", "Neurology review", "Seizure-free for 14 months on levetiracetam. Continue.", 60, kulkarni, riverside, ["Levetiracetam"]),
        ("procedure", "Knee X-ray", "Moderate joint-space narrowing, both knees.", 45, nair, riverside, []),
        ("consultation", "Orthopaedic consultation", "Osteoarthritis knees. Physiotherapy and glucosamine.", 45, nair, riverside, ["Glucosamine"]),
    ])
    past_visit(db, arvind, kulkarni, riverside, 60, "Neurology review")
    past_visit(db, arvind, nair, riverside, 45, "Knee pain", hour=12)

    # ---- Aarav Shetty (child): asthma-allergy; Sheikh, Aditya Rao ----
    grant(db, aarav, sheikh, 300, "Child health")
    grant(db, aarav, arao, 40, "Wheezing review", authority="referral")
    prescribe(db, aarav, sheikh, cetir, dose=0.5, unit="tablet", times=["20:00"], freq="Once daily at night",
              start=today - timedelta(days=40), end=today + timedelta(days=20), indication="Allergic rhinitis",
              org_id=lotus.id, created_days_ago=40)
    db.add(Diagnosis(patient_id=aarav.id, name="Allergic rhinitis", code="J30.9", recorded_by=sheikh.id))
    db.add(Allergy(patient_id=aarav.id, substance="Peanuts", reaction="Lip swelling", severity="severe", recorded_by=sheikh.id))
    records(db, aarav, [
        ("consultation", "Paediatric check-up", "Growth normal for age. Vaccinations up to date.", 120, sheikh, lotus, []),
        ("consultation", "Allergy consultation", "Sneezing and blocked nose for 3 weeks. Cetirizine at night.", 40, sheikh, lotus, ["Cetirizine"]),
        ("consultation", "Chest review", "Occasional wheeze with colds; no asthma treatment needed now.", 35, arao, sunrise, []),
    ])
    past_visit(db, aarav, sheikh, lotus, 40, "Blocked nose and sneezing", hour=10)

    # ---- Neha Gupta: PCOS + eczema; Sundaram, Desai, Mehra ----
    grant(db, neha, sundaram, 150, "Gynaecology care")
    grant(db, neha, desai, 70, "Skin care")
    grant(db, neha, mehra, 30, "Metabolic review", authority="referral")
    prescribe(db, neha, mehra, met, dose=1, unit="tablet", times=["20:00"], freq="Once daily with dinner",
              start=today - timedelta(days=30), indication="Polycystic ovary syndrome", food="With dinner",
              org_id=greenleaf.id, created_days_ago=30)
    db.add(Diagnosis(patient_id=neha.id, name="Polycystic ovary syndrome", code="E28.2", recorded_by=sundaram.id))
    db.add(Diagnosis(patient_id=neha.id, name="Atopic dermatitis", code="L20.9", recorded_by=desai.id))
    records(db, neha, [
        ("consultation", "Gynaecology consultation", "Irregular cycles; ultrasound consistent with PCOS.", 150, sundaram, sunrise, []),
        ("consultation", "Dermatology consultation", "Eczema on both hands; moisturiser and short steroid cream course.", 70, desai, greenleaf, []),
        ("consultation", "Metabolic review", "Insulin resistance; metformin started with dinner.", 30, mehra, greenleaf, ["Metformin"]),
    ])
    past_visit(db, neha, sundaram, sunrise, 150, "Irregular periods", hour=18)
    past_visit(db, neha, mehra, greenleaf, 30, "Metabolic review")

    db.add(EscalationPolicy(patient_id=None))

    # ---------------- availability for every doctor + upcoming appointments ----------------
    hours = [("10:00", "13:00", 20), ("14:00", "17:00", 30), ("09:00", "12:00", 15), ("15:00", "18:00", 20)]
    for i, (d, o) in enumerate(doctors):
        start_t, end_t, mins = hours[i % len(hours)]
        for weekday in range(6):
            db.add(DoctorAvailability(doctor_user_id=d.id, organization_id=o.id, weekday=weekday, start_time=start_t,
                                      end_time=end_t, slot_minutes=mins))
    db.flush()
    for d, _ in doctors:
        booking.materialize_slots(db, d.id)
    db.flush()

    def book(pu, p, doc, reason, days_ahead):
        slot = db.execute(select(AvailabilitySlot).where(AvailabilitySlot.doctor_user_id == doc.id,
                                                         AvailabilitySlot.starts_at > now + timedelta(days=days_ahead))
                          .order_by(AvailabilitySlot.starts_at)).scalars().first()
        if slot:
            h = booking.hold(db, pu, p, slot.id)
            booking.confirm(db, pu, p, h.id, reason)

    book(ananya_u, ananya, mehra, "Diabetes follow-up", 2)
    book(rahul_u, rahul, khan, "Blood pressure review", 3)
    book(suresh_u, suresh, reddy, "Kidney function review", 5)
    book(divya_u, divya, sundaram, "Antenatal visit", 4)
    book(arvind_u, arvind, nair, "Knee review after physiotherapy", 6)
    book(neha_u, neha, desai, "Eczema follow-up", 3)

    db.add(Notification(user_id=ananya_u.id, patient_id=ananya.id, category="doctor_instruction", title="New instruction",
                        body="Check fasting blood sugar twice a week", channel="in_app", delivery_status="delivered",
                        created_at=now - timedelta(days=2)))
    db.add(Notification(user_id=kavya.id, patient_id=ananya.id, category="caregiver_update", title="Weekly summary",
                        body="Ananya reported most doses this week.", channel="in_app", delivery_status="delivered",
                        created_at=now - timedelta(days=1)))
    audit.record(db, action="seed", resource_type="system", reason="starter data created")
    db.commit()
    print("Starter data created: 10 patients, 10 doctors, caregiver, coordinator, admin. See docs/ACCOUNTS.md.")


# ---------------- keeping self-registered accounts across a reset ----------------
_SKIP = {"id", "user_id", "organization_id", "verified_by", "created_at", "updated_at"}


def _row(obj) -> dict:
    return {c.key: getattr(obj, c.key) for c in obj.__table__.columns if c.key not in _SKIP}


def _snapshot(db) -> list[dict]:
    out = []
    for u in db.execute(select(User).where(User.is_demo.is_(False))).scalars():
        out.append({"user": _row(u), "patient": _row(u.patient_profile) if u.patient_profile else None,
                    "doctor": _row(u.doctor_profile) if u.doctor_profile else None,
                    "caregiver": _row(u.caregiver_profile) if getattr(u, "caregiver_profile", None) else None})
    return out


def _restore(db, saved: list[dict]) -> None:
    for s in saved:
        u = User(**s["user"])
        db.add(u)
        db.flush()
        if s["patient"]:
            db.add(PatientProfile(user_id=u.id, **s["patient"]))
        if s["doctor"]:
            db.add(DoctorProfile(user_id=u.id, **{**s["doctor"], "verification_status": "verified"}))
        if s["caregiver"]:
            db.add(CaregiverProfile(user_id=u.id, **s["caregiver"]))
    db.commit()
    if saved:
        print(f"Restored {len(saved)} self-registered account(s): " + ", ".join(s["user"]["email"] for s in saved))


def main():
    s = get_settings()
    saved: list[dict] = []
    if "--reset" in sys.argv:
        if not s.is_dev:
            raise SystemExit("--reset is only allowed in development")
        db = SessionLocal()
        try:
            saved = _snapshot(db)
        finally:
            db.close()
        if s.database_url.startswith("sqlite:///"):
            path = s.database_url.removeprefix("sqlite:///")
            shutil.copyfile(path, path + ".before-reset")
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        seed(db)
        if saved:
            _restore(db, saved)
    finally:
        db.close()


if __name__ == "__main__":
    main()
