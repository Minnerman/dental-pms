from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import require_capabilities
from app.models.user import User
from app.schemas.treatment_planning import PlanningStart, PlanningOut, PlanningItemCreate, PlanningItemUpdate, PlanningItemUncomplete, PlanningItemOut
from app.services import treatment_planning as service

router = APIRouter(prefix="/patients/{patient_id}/planning", tags=["clinical"])
VIEW = require_capabilities("clinical.view")
WRITE = require_capabilities("clinical.view", "clinical.write")


@router.get("", response_model=PlanningOut)
def get_planning(patient_id: int, db: Session = Depends(get_db), user: User = Depends(VIEW)):
    return service.get_workspace(db, patient_id, user)


@router.get("/catalogue")
def get_catalogue(patient_id: int, q: str = Query(default="", max_length=200), limit: int = Query(default=50, ge=1, le=100),
                  offset: int = Query(default=0, ge=0), db: Session = Depends(get_db), _user: User = Depends(VIEW)):
    return service.catalogue(db, patient_id, q, limit, offset)


@router.post("/start", response_model=PlanningOut, status_code=201)
def start_planning(patient_id: int, payload: PlanningStart, db: Session = Depends(get_db), user: User = Depends(WRITE),
                   request_id: str = Header(min_length=1, max_length=120)):
    return service.start(db, patient_id, user, request_id)


@router.post("/items", response_model=PlanningItemOut, status_code=201)
def add_item(patient_id: int, payload: PlanningItemCreate, db: Session = Depends(get_db), user: User = Depends(WRITE),
             request_id: str = Header(min_length=1, max_length=120)):
    return service.create_item(db, patient_id, payload, user, request_id)


@router.patch("/items/{item_id}", response_model=PlanningItemOut)
def change_item(patient_id: int, item_id: int, payload: PlanningItemUpdate, db: Session = Depends(get_db), user: User = Depends(WRITE),
                request_id: str = Header(min_length=1, max_length=120)):
    return service.update_item(db, patient_id, item_id, payload, user, request_id)


@router.get("/items/{item_id}/history")
def history(patient_id: int, item_id: int, limit: int = Query(default=50, ge=1, le=100), before_revision: int | None = Query(default=None, ge=1),
            db: Session = Depends(get_db), _user: User = Depends(VIEW)):
    return service.item_history(db, patient_id, item_id, limit, before_revision)


@router.post("/items/{item_id}/uncomplete", response_model=PlanningItemOut)
def uncomplete(patient_id: int, item_id: int, payload: PlanningItemUncomplete, db: Session = Depends(get_db), user: User = Depends(WRITE),
               request_id: str = Header(min_length=1, max_length=120)):
    return service.uncomplete_item(db, patient_id, item_id, payload, user, request_id)
