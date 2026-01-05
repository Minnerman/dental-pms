import os
from fastapi import FastAPI
from sqlalchemy.orm import Session

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
from app.services.users import ensure_admin_user

app = FastAPI(title="Dental PMS API", version="0.1.0")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

    admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com")
    admin_password = os.getenv("ADMIN_PASSWORD", "ChangeMe123!").strip()
    if len(admin_password.encode("utf-8")) > 72:
        raise RuntimeError("ADMIN_PASSWORD exceeds bcrypt 72-byte limit")
    db: Session = SessionLocal()
    try:
        ensure_admin_user(db, email=admin_email, password=admin_password)
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
