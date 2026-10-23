"""Reference lists for India, served to the frontend from /api/reference so the UI and the
server validate against the same values. Verify council names against the National Medical
Commission's list of State Medical Councils before production use."""

SPECIALITIES = [
    "General Medicine", "Family Medicine", "General Surgery", "Paediatrics", "Obstetrics & Gynaecology",
    "Orthopaedics", "Ophthalmology", "Otorhinolaryngology (ENT)", "Dermatology, Venereology & Leprosy",
    "Psychiatry", "Anaesthesiology", "Emergency Medicine", "Respiratory Medicine", "Radiodiagnosis",
    "Radiation Oncology", "Pathology", "Microbiology", "Pharmacology", "Community Medicine",
    "Physical Medicine & Rehabilitation", "Geriatric Medicine", "Sports Medicine", "Cardiology", "Neurology",
    "Nephrology", "Gastroenterology", "Endocrinology", "Medical Oncology", "Clinical Haematology",
    "Rheumatology", "Infectious Diseases", "Neonatology", "Critical Care Medicine",
    "Cardiothoracic & Vascular Surgery", "Neurosurgery", "Urology", "Plastic & Reconstructive Surgery",
    "Paediatric Surgery", "Surgical Gastroenterology", "Surgical Oncology", "Endocrine Surgery",
]

COUNCILS = [
    "National Medical Commission (Indian Medical Register, formerly Medical Council of India)",
    "Andhra Pradesh Medical Council", "Arunachal Pradesh Medical Council", "Assam Medical Council",
    "Bihar Council of Medical Registration", "Chhattisgarh Medical Council", "Delhi Medical Council",
    "Goa Medical Council", "Gujarat Medical Council", "Haryana Medical Council", "Himachal Pradesh Medical Council",
    "Jammu & Kashmir Medical Council", "Jharkhand Medical Council", "Karnataka Medical Council",
    "Travancore-Cochin Medical Council (Kerala)", "Madhya Pradesh Medical Council", "Maharashtra Medical Council",
    "Manipur Medical Council", "Meghalaya Medical Council", "Mizoram Medical Council", "Nagaland Medical Council",
    "Odisha Council of Medical Registration", "Punjab Medical Council", "Rajasthan Medical Council",
    "Sikkim Medical Council", "Tamil Nadu Medical Council", "Telangana State Medical Council",
    "Tripura State Medical Council", "Uttar Pradesh Medical Council", "Uttarakhand Medical Council",
    "West Bengal Medical Council",
]

STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana",
    "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana",
    "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    # Union Territories
    "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu", "Delhi",
    "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
]
