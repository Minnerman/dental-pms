import logging
from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.core.settings import settings, validate_settings
from app.db.session import SessionLocal, engine
from app.models import Base
from app.routers.auth import router as auth_router
from app.routers.appointments import router as appointments_router
from app.routers.audit import router as audit_router
from app.routers.me import router as me_router
from app.routers.notes import router as notes_router, patient_router as patient_notes_router
from app.routers.patients import router as patients_router
from app.routers.timeline import router as timeline_router
from app.routers.users import router as users_router
from app.services.users import seed_initial_admin

app = FastAPI(title="Dental PMS API", version="0.1.0")
logger = logging.getLogger("dental_pms.startup")


@app.on_event("startup")
def startup():
    validate_settings(settings)
    Base.metadata.create_all(bind=engine)

    admin_email = str(settings.admin_email)
    admin_password = settings.admin_password.strip()
    db: Session = SessionLocal()
    try:
        created = seed_initial_admin(db, email=admin_email, password=admin_password)
        if created:
            logger.info("Initial admin created for %s (must change password on first login).", admin_email)
        else:
            logger.info("Initial admin not created (users already exist).")
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(me_router)
app.include_router(users_router)
app.include_router(patients_router)
app.include_router(appointments_router)
app.include_router(notes_router)
app.include_router(patient_notes_router)
app.include_router(audit_router)
app.include_router(timeline_router)
