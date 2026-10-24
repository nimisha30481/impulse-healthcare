# DoseWISE starter accounts

Created by `python -m app.seed` (see `backend/app/seed.py`). Every person and organisation is fictional.
**Password for every account below: `Dosewise_2026`**

These accounts sign in with DoseWISE's own password check (they were created before Cognito, so no
email code is needed). Accounts you register yourself on the website use Amazon Cognito as before.

## Doctors (all Karnataka Medical Council, active immediately)

| Doctor | Speciality | Works at | Email |
|---|---|---|---|
| Dr. Arjun Mehra | Endocrinology | Greenleaf Family Clinic | dr.arjun.mehra@dosewise.in |
| Dr. Sara Khan | Cardiology | Lotus Multispeciality Hospital | dr.sara.khan@dosewise.in |
| Dr. Leela Iyer | General Medicine | Lotus Multispeciality Hospital | dr.leela.iyer@dosewise.in |
| Dr. Vikram Nair | Orthopaedics | Riverside Medical Centre | dr.vikram.nair@dosewise.in |
| Dr. Priyanka Desai | Dermatology | Greenleaf Family Clinic | dr.priyanka.desai@dosewise.in |
| Dr. Rohan Kulkarni | Neurology | Riverside Medical Centre | dr.rohan.kulkarni@dosewise.in |
| Dr. Fatima Sheikh | Paediatrics | Lotus Multispeciality Hospital | dr.fatima.sheikh@dosewise.in |
| Dr. Karthik Reddy | Nephrology | Riverside Medical Centre | dr.karthik.reddy@dosewise.in |
| Dr. Meenakshi Sundaram | Obstetrics & Gynaecology | Sunrise Women & Chest Clinic | dr.meenakshi.sundaram@dosewise.in |
| Dr. Aditya Rao | Respiratory Medicine | Sunrise Women & Chest Clinic | dr.aditya.rao@dosewise.in |

## Patients (each has exactly 3 medical-history records)

| Patient | Access ID | Main conditions | Their doctors | Email |
|---|---|---|---|---|
| Ananya Rao | DW-ANANYA | Type 2 diabetes, hypertension | Mehra, Khan, Iyer (caregiver: Kavya Rao) | ananya.rao@dosewise.in |
| Rahul Verma | DW-R7HKV2 | Hypertension, diabetes (missed doses → coordinator case) | Mehra, Khan | rahul.verma@dosewise.in |
| Meera Iyer | DW-M3ERQ8 | Sore throat (course completed) | Iyer | meera.iyer@dosewise.in |
| Suresh Patil | DW-S5PTL9 | Chronic kidney disease, hypertension | Reddy, Khan | suresh.patil@dosewise.in |
| Lakshmi Narayan | DW-L4KNR6 | Hypothyroidism | Mehra, Desai | lakshmi.narayan@dosewise.in |
| Imran Qureshi | DW-Q8RMN3 | Asthma, allergic rhinitis | Aditya Rao, Iyer | imran.qureshi@dosewise.in |
| Divya Menon | DW-D2MNV7 | Pregnancy care, mild anaemia | Sundaram | divya.menon@dosewise.in |
| Arvind Krishnan | DW-K9RVD4 | Epilepsy, knee osteoarthritis | Kulkarni, Nair | arvind.krishnan@dosewise.in |
| Aarav Shetty (child) | DW-A6SHT5 | Allergic rhinitis, peanut allergy | Sheikh, Aditya Rao | aarav.shetty@dosewise.in |
| Neha Gupta | DW-N5GPT8 | PCOS, eczema | Sundaram, Desai, Mehra | neha.gupta@dosewise.in |

Upcoming appointments are booked for Ananya, Rahul, Suresh, Divya, Arvind and Neha.

## Other roles

| Role | Name | Email |
|---|---|---|
| Caregiver | Kavya Rao (Ananya's daughter) | kavya.rao@dosewise.in |
| Care coordinator | Priya Nair | priya.nair@dosewise.in |
| Administrator | DoseWISE Administrator | admin@dosewise.in |

## Good demo paths

1. **Doctor:** sign in as Dr. Arjun Mehra → Patients (4 patients) → Ananya → Medical history (3 records), Prescriptions, Adherence.
2. **Patient:** sign in as Ananya → today's doses → Log dosage → Appointments → Reschedule (the old booking turns grey and points to the new one; a notification appears).
3. **Guest doctor:** home page → Guest Doctor Access → `DW-ANANYA` → read-only chart.
4. **Language:** switch to हिन्दी / ಕನ್ನಡ / தமிழ் / తెలుగు in the header; names and medicines stay as written.
