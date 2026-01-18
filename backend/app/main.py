import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.settings import settings, validate_settings
from app.db.session import SessionLocal, engine
from app.models import Base
from app.routers.auth import router as auth_router
from app.routers.appointments import router as appointments_router
from app.routers.invoices import router as invoices_router
from app.routers.payments import router as payments_router
from app.routers.audit import router as audit_router
from app.routers.me import router as me_router
from app.routers.notes import router as notes_router, patient_router as patient_notes_router
from app.routers.notes import appointment_router as appointment_notes_router
from app.routers.notes import appointment_router as appointment_notes_router
from app.routers.notes import appointment_router as appointment_notes_router
from app.routers.clinical import router as clinical_router, patient_router as patient_clinical_router
from app.routers.patients import router as patients_router
from app.routers.reports import router as reports_router
from app.routers.recalls import router as recalls_router
from app.routers.treatments import router as treatments_router
from app.routers.estimates import router as estimates_router, patient_router as patient_estimates_router
from app.routers.settings import router as settings_router
from app.routers.timeline import router as timeline_router
from app.routers.users import router as users_router
from app.routers.document_templates import router as document_templates_router
from app.routers.attachments import (
    router as patient_attachments_router,
    attachments_router as attachments_router,
)
from app.routers.patient_documents import (
    router as patient_documents_router,
    documents_router as documents_router,
)
from app.routers.capabilities import router as capabilities_router
from app.services.users import seed_initial_admin
from app.services.capabilities import backfill_user_capabilities, ensure_capabilities
from app.services.document_templates import ensure_default_templates
from app.models.user import User
from sqlalchemy import select

app = FastAPI(title="Dental PMS API", version="0.1.0")
logger = logging.getLogger("dental_pms.startup")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = request.headers.get("x-request-id")
    logger.exception("Unhandled server error", extra={"request_id": request_id})
    payload = {"detail": "Internal server error"}
    if request_id:
        payload["request_id"] = request_id
    return JSONResponse(status_code=500, content=payload)


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
        ensured = ensure_capabilities(db)
        if ensured:
            logger.info("Capabilities ensured (%s total).", len(ensured))
        backfilled = backfill_user_capabilities(db)
        if backfilled:
            logger.info("Capabilities backfilled for existing users (%s grants).", backfilled)
        actor = db.scalar(select(User).order_by(User.id.asc()).limit(1))
        if actor:
            created_templates = ensure_default_templates(db, actor=actor)
            if created_templates:
                logger.info("Default document templates ensured (%s added).", created_templates)
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(me_router)
app.include_router(users_router)
app.include_router(patients_router)
app.include_router(recalls_router)
app.include_router(appointments_router)
app.include_router(invoices_router)
app.include_router(payments_router)
app.include_router(notes_router)
app.include_router(patient_notes_router)
app.include_router(appointment_notes_router)
app.include_router(appointment_notes_router)
app.include_router(appointment_notes_router)
app.include_router(patient_clinical_router)
app.include_router(clinical_router)
app.include_router(treatments_router)
app.include_router(estimates_router)
app.include_router(patient_estimates_router)
app.include_router(settings_router)
app.include_router(document_templates_router)
app.include_router(patient_attachments_router)
app.include_router(attachments_router)
app.include_router(patient_documents_router)
app.include_router(documents_router)
app.include_router(capabilities_router)
app.include_router(audit_router)
app.include_router(timeline_router)
app.include_router(reports_router)
