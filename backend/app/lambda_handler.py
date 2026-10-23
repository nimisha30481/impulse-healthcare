"""AWS Lambda entry points (deployed by infra/).

api_handler    - API Gateway HTTP API -> FastAPI via Mangum
worker_handler - EventBridge Scheduler (every minute) -> reminder/escalation tick
"""
from mangum import Mangum

from app.core.database import SessionLocal
from app.main import app
from app.services import jobs

api_handler = Mangum(app, lifespan="off")


def worker_handler(event, context):
    db = SessionLocal()
    try:
        jobs.tick(db)
    finally:
        db.close()
    return {"status": "ok"}


def interaction_workflow_handler(event, context):
    """Step Functions task. The assessment itself runs synchronously in the API so the doctor sees
    it immediately; this workflow handles the follow-up: confirm the record exists, notify the
    prescriber about unreviewed alerts, and audit completion. Retries/timeouts live in the state machine."""
    from app.core import audit
    from app.models import InteractionAssessment, User
    from app.services import notifications

    db = SessionLocal()
    try:
        a = db.get(InteractionAssessment, event["assessment_id"])
        if not a:
            raise ValueError("assessment not found")  # Step Functions retries, then fails visibly
        step = event.get("step", "notify")
        if step == "notify" and a.alerts and not a.reviewed_at and a.requested_by:
            notifications.notify(db, db.get(User, a.requested_by), category="important_alert",
                                 title="Medication safety alert needs review", body="Open the patient's prescriptions.",
                                 patient_id=a.patient_id, link=f"/doctor/patients/{a.patient_id}?tab=prescriptions",
                                 priority="high", dedupe_key=f"sfn-alert:{a.id}")
        audit.record(db, action=f"interaction_workflow_{step}", resource_type="interaction_assessment",
                     resource_id=a.id, patient_id=a.patient_id, source="step_functions")
        db.commit()
        return {"assessment_id": a.id, "status": a.status, "alerts": len(a.alerts)}
    finally:
        db.close()
