"""Age and body measurements shown with a patient's record (BMI is calculated, never stored)."""
from datetime import date


def age(dob: date | None, today: date | None = None) -> int | None:
    if not dob:
        return None
    today = today or date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def bmi(height_cm: float | None, weight_kg: float | None) -> float | None:
    if not height_cm or not weight_kg:
        return None
    return round(weight_kg / (height_cm / 100) ** 2, 1)


def bmi_category(value: float | None) -> str | None:
    """WHO adult categories. Not used for children, whose BMI is read against age charts."""
    if value is None:
        return None
    if value < 18.5:
        return "Underweight"
    if value < 25:
        return "Normal"
    if value < 30:
        return "Overweight"
    return "Obese"


def body(p) -> dict:
    """age, sex, height, weight and BMI for a PatientProfile."""
    years = age(p.date_of_birth)
    value = bmi(p.height_cm, p.weight_kg)
    return {"age": years, "sex": p.sex, "height_cm": p.height_cm, "weight_kg": p.weight_kg, "bmi": value,
            "bmi_category": bmi_category(value) if years is None or years >= 18 else "See child growth chart"}
