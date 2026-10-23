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
