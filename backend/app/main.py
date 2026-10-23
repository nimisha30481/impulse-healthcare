import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import account, appointments, auth, care, doctor, misc, patients, support
from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.services import jobs, realtime

log = logging.getLogger("impulse")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


async def _job_loop():
    interval = get_settings().background_tick_seconds
    while True:
        await asyncio.sleep(interval)
        db = SessionLocal()
        try:
            await asyncio.to_thread(jobs.tick, db)
        except Exception:  # noqa: BLE001
            log.exception("background tick failed")
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    if s.database_url.startswith("sqlite"):
        Base.metadata.create_all(engine)  # local convenience; PostgreSQL uses Alembic migrations
    realtime.bind_loop(asyncio.get_running_loop())
    task = asyncio.create_task(_job_loop()) if s.run_background_jobs else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="IMPULSE API", version="0.1.0", lifespan=lifespan,
              docs_url="/api/docs", openapi_url="/api/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.url.path.startswith("/api/") and "Cache-Control" not in response.headers:
        response.headers["Cache-Control"] = "no-store"  # never cache health data in shared caches
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors = []
    for e in exc.errors():
        field = ".".join(str(p) for p in e["loc"] if p not in ("body",))
        errors.append({"field": field, "message": e["msg"].replace("Value error, ", "")})
    return JSONResponse(status_code=422, content={"detail": "Please check the highlighted fields", "errors": errors})


for r in (auth.router, account.router, patients.router, care.router, doctor.router, appointments.router,
          support.router, misc.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"status": "ok", "environment": get_settings().environment}
