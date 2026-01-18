from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import require_capability, require_roles
from app.schemas.capability import CapabilityOut
from app.services.capabilities import list_capabilities

router = APIRouter(prefix="/capabilities", tags=["capabilities"])


@router.get("", response_model=list[CapabilityOut])
def list_all_capabilities(
    db: Session = Depends(get_db),
    _=Depends(require_roles("superadmin")),
    __=Depends(require_capability("admin.permissions.manage")),
):
    return list_capabilities(db)
