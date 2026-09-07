"""Member-aware reads from immutable completion snapshots, never inferred teeth."""
from pydantic import ValidationError
from sqlalchemy import exists, select

from app.models.clinical import Procedure, TreatmentPlanItem
from app.models.treatment_planning import TreatmentPlanItemRevision
from app.schemas.treatment_planning import PlanningAppliance


def procedure_has_member(tooth):
    revision = TreatmentPlanItemRevision
    return exists(select(revision.id).join(TreatmentPlanItem, TreatmentPlanItem.id == revision.item_id).where(
        TreatmentPlanItem.patient_id == Procedure.patient_id,
        revision.snapshot["status"].as_string() == "completed",
        revision.snapshot["completed_procedure_id"].as_integer() == Procedure.id,
        revision.snapshot["appliance"]["members"].contains([{"tooth": tooth}])))


def procedure_appliances(db, patient_id, procedure_ids):
    if not procedure_ids:
        return {}
    revision = TreatmentPlanItemRevision
    result = {}
    for value in db.scalars(select(revision.snapshot).join(TreatmentPlanItem, TreatmentPlanItem.id == revision.item_id).where(
        TreatmentPlanItem.patient_id == patient_id,
        revision.snapshot["status"].as_string() == "completed",
        revision.snapshot["completed_procedure_id"].as_integer().in_(procedure_ids))):
        if not value.get("appliance"):
            continue
        try:
            result[value["completed_procedure_id"]] = PlanningAppliance.model_validate(value["appliance"]).model_dump(mode="json")
        except (ValidationError, TypeError, ValueError):
            # Keep original snapshots unchanged, never guess corrupt members.
            continue
    return result


def attach_procedure_appliances(db, patient_id, procedures):
    groups = procedure_appliances(db, patient_id, [row.id for row in procedures])
    for row in procedures:
        row.appliance = groups.get(row.id)  # Unmapped read-only response attribute.
    return procedures
