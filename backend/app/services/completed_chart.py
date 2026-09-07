"""Read-only completed-care projection metadata and native authoring eligibility.

Raw diagnosis rows are never changed here. Native diagnosis and planning writes
share the patient lock, so audit IDs provide ordering without clock inference.
"""
from copy import deepcopy
from types import SimpleNamespace
from typing import get_args

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select, text

from app.models.audit_log import AuditLog
from app.models.clinical import Procedure, ProcedureStatus, TreatmentPlanItem, TreatmentPlanStatus
from app.schemas.clinical import NATIVE_SURFACE_ORDER, schematic_root_count
from app.schemas.treatment_planning import DrawingKind, LEVEL_KINDS, PlanningTarget, allowed_planning_materials

OBSERVATION_ACTIONS = (
    "clinical.tooth_conditions.recorded", "clinical.root_conditions.recorded", "clinical.crown_conditions.recorded",
    "clinical.bridge.created", "clinical.bridge.reset", "clinical.surface_conditions.recorded",
)
PROJECTION_ACTIONS = (*OBSERVATION_ACTIONS, "clinical.procedure.completed", "clinical.planning.item.uncompleted")


def projection_revision(db, patient_id):
    return db.scalar(select(func.max(AuditLog.id)).where(AuditLog.entity_type == "patient",
        AuditLog.entity_id == str(patient_id), AuditLog.action.in_(PROJECTION_ACTIONS))) or 0


def observation_events(db, patient_id, earliest_event):
    # One SQL aggregation returns at most 32 rows. No full patient audit text,
    # notes, author identities or historical clinical narratives are loaded.
    # Explicit no-op requests count: Reset after a completion is an intentional
    # new observation even if its raw stored value was already neutral.
    fields = []
    # Changing recorded dentition invalidates these anatomical layers even if
    # their raw maps were already empty; it does not change presence/anatomy.
    dentition_clear = "(action='clinical.tooth_conditions.recorded' AND coalesce(before->'dentition','null'::jsonb) IS DISTINCT FROM coalesce(after->'dentition','null'::jsonb))"
    for output, key in (("anatomy", "condition"), ("dentition", "dentition"), ("movement", "movement"), ("rotation", "rotation")):
        # Legacy deciduous shorthand may normalize condition while changing
        # dentition alone. That compatibility rewrite is not a presence finding.
        changed = "" if output == "anatomy" else f" OR coalesce(before->'{key}','null'::jsonb) IS DISTINCT FROM coalesce(after->'{key}','null'::jsonb)"
        fields.append(f"coalesce(max(id) FILTER (WHERE (action='clinical.tooth_conditions.recorded' AND request ? '{key}'){changed}),0) AS {output}")
    fields.append(f"""coalesce(max(id) FILTER (WHERE {dentition_clear} OR action IN ('clinical.crown_conditions.recorded','clinical.bridge.created','clinical.bridge.reset')
        OR coalesce(before->'crown_observation','null'::jsonb) IS DISTINCT FROM coalesce(after->'crown_observation','null'::jsonb)
        OR coalesce(before->'bridge_group_id','null'::jsonb) IS DISTINCT FROM coalesce(after->'bridge_group_id','null'::jsonb)
        OR coalesce(before->'bridge_role','null'::jsonb) IS DISTINCT FROM coalesce(after->'bridge_role','null'::jsonb)),0) AS crown""")
    for output, key in (("root_condition", "condition"), ("apicectomy", "apicectomy")):
        fields.append(f"""coalesce(max(id) FILTER (WHERE {dentition_clear} OR (action='clinical.root_conditions.recorded' AND request ? '{key}') OR
            (action<>'clinical.root_conditions.recorded' AND
            (SELECT jsonb_object_agg(k,v->'{key}') FROM jsonb_each(coalesce(before->'root_observations','{{}}'::jsonb)) r(k,v)) IS DISTINCT FROM
            (SELECT jsonb_object_agg(k,v->'{key}') FROM jsonb_each(coalesce(after->'root_observations','{{}}'::jsonb)) r(k,v)))),0) AS {output}""")
    for surface in NATIVE_SURFACE_ORDER:
        fields.append(f"""coalesce(max(id) FILTER (WHERE {dentition_clear} OR
            coalesce(before->'surface_observations'->'{surface}','null'::jsonb) IS DISTINCT FROM coalesce(after->'surface_observations'->'{surface}','null'::jsonb)
            OR (action='clinical.surface_conditions.recorded' AND EXISTS (
                SELECT 1 FROM jsonb_array_elements(coalesce(request->'targets','[]'::jsonb)) target
                WHERE target->>'tooth'=tooth AND (target->'surfaces') ? '{surface}'))),0) AS surface_{surface.lower()}""")
    sql = """WITH scoped AS (
        SELECT id,action,before_json::jsonb AS before_doc,after_json::jsonb AS after_doc
        FROM audit_logs WHERE entity_type='patient' AND entity_id=:patient_id AND id >= :earliest
        AND action IN ('clinical.tooth_conditions.recorded','clinical.root_conditions.recorded','clinical.crown_conditions.recorded',
            'clinical.bridge.created','clinical.bridge.reset','clinical.surface_conditions.recorded')
    ), expanded AS (
        SELECT id,action,t.key AS tooth,before_doc->'teeth'->t.key AS before,t.value AS after,
            coalesce(after_doc->'request','{}'::jsonb) AS request
        FROM scoped CROSS JOIN LATERAL jsonb_each(coalesce(after_doc->'teeth','{}'::jsonb)) t
    ) SELECT tooth,""" + ",".join(fields) + " FROM expanded GROUP BY tooth"
    result = {}
    for record in db.execute(text(sql), {"patient_id": str(patient_id), "earliest": earliest_event}).mappings():
        values = dict(record)
        tooth = values.pop("tooth")
        surfaces = {key: values.pop(f"surface_{key.lower()}") for key in NATIVE_SURFACE_ORDER}
        result[tooth] = {**values, "surfaces": surfaces}
    return result


def projection_context(db, patient_id):
    result = {"completed_effects": [], "observation_events": {}, "projection_revision": projection_revision(db, patient_id),
        "projection_coverage": {"status": "available", "reason": None}}
    rows = db.execute(select(TreatmentPlanItem, Procedure).outerjoin(Procedure,
        Procedure.id == TreatmentPlanItem.completed_procedure_id).where(TreatmentPlanItem.patient_id == patient_id,
        TreatmentPlanItem.plan_id.is_not(None), TreatmentPlanItem.status == TreatmentPlanStatus.completed)
        .order_by(TreatmentPlanItem.id).limit(1001)).all()
    if len(rows) > 1000:
        result["projection_coverage"] = {"status": "unavailable", "reason": "Completed chart exceeds the supported projection limit; review the treatment history"}
        return result
    if not rows:
        return result
    procedure_ids = [procedure.id for _, procedure in rows if procedure is not None]
    audits = {}
    if procedure_ids:
        for aid, pid, item_id in db.execute(select(AuditLog.id, AuditLog.after_json["procedure_id"].as_string(),
            AuditLog.after_json["treatment_plan_item_id"].as_string()).where(
            AuditLog.entity_type == "patient", AuditLog.entity_id == str(patient_id),
            AuditLog.action == "clinical.procedure.completed", AuditLog.after_json["procedure_id"].as_string().in_([str(value) for value in procedure_ids]))):
            audits.setdefault(int(pid), []).append((aid, item_id))
    for item, procedure in rows:
        details = item.planning_details or {}
        try:
            target = PlanningTarget.model_validate(details.get("target"))
            kind, material = details.get("drawing_kind"), details.get("material")
            if (kind not in get_args(DrawingKind) or kind not in LEVEL_KINDS[target.level]
                    or material is not None and material not in allowed_planning_materials(kind, target.level)):
                raise ValueError("Unknown effect metadata")
            legacy_surface = "".join("L" if key == "P" else key for key in target.surfaces) or None
            if (procedure is None or procedure.patient_id != patient_id or procedure.status != ProcedureStatus.completed
                    or len(audits.get(procedure.id, [])) != 1 or audits[procedure.id][0][1] != str(item.id)
                    or procedure.tooth != target.tooth or item.tooth != target.tooth
                    or procedure.surface != legacy_surface or item.surface != legacy_surface):
                raise ValueError("Ambiguous active completion")
        except (ValidationError, ValueError, TypeError):
            result["projection_coverage"] = {"status": "unavailable", "reason": "A completed treatment lacks unambiguous chart metadata; review its history"}
            continue
        result["completed_effects"].append({"item_id": item.id, "procedure_id": procedure.id,
            "completed_at": procedure.performed_at, "event_id": audits[procedure.id][0][0],
            "target": target.model_dump(), "drawing_kind": kind, "material": material})
    result["completed_effects"].sort(key=lambda effect: effect["event_id"])
    if result["completed_effects"]:
        result["observation_events"] = observation_events(db, patient_id, result["completed_effects"][0]["event_id"])
    return result


def check_projection(db, patient_id, expected_revision):
    context = projection_context(db, patient_id)
    if expected_revision is not None and expected_revision != context["projection_revision"]:
        raise HTTPException(409, "Completed chart or diagnosis changed; refresh before saving")
    if context["projection_coverage"]["status"] != "available":
        raise HTTPException(422, context["projection_coverage"]["reason"])
    return context


def effective_tooth(row, tooth, context):
    """Detached eligibility view only. Never attach/save this as a diagnosis row."""
    state = SimpleNamespace(condition=getattr(row, "condition", None), dentition=getattr(row, "dentition", None),
        movement=getattr(row, "movement", None), rotation=getattr(row, "rotation", None),
        root_observations=deepcopy(getattr(row, "root_observations", {})),
        crown_observation=deepcopy(getattr(row, "crown_observation", None)),
        surface_observations=deepcopy(getattr(row, "surface_observations", {})),
        bridge_group_id=getattr(row, "bridge_group_id", None), bridge_role=getattr(row, "bridge_role", None))
    events = context["observation_events"].get(tooth, {})
    for effect in context["completed_effects"]:
        if effect["target"]["tooth"] != tooth or events.get("anatomy", 0) > effect["event_id"]:
            continue
        eid, kind = effect["event_id"], effect["drawing_kind"]
        if kind in {"extraction", "implant"}:
            state.condition = "missing" if kind == "extraction" else "implant"
            for field in (("dentition", "movement", "rotation") if kind == "implant" else ("movement", "rotation")):
                if events.get(field, 0) <= eid:
                    setattr(state, field, None)
            if max(events.get("root_condition", 0), events.get("apicectomy", 0)) <= eid:
                state.root_observations = {}
            if events.get("crown", 0) <= eid:
                state.crown_observation = None
            state.surface_observations = {key: value for key, value in state.surface_observations.items()
                if events.get("surfaces", {}).get(key, 0) > eid}
        elif kind in {"root_canal", "post_core", "apicectomy"}:
            field = "apicectomy" if kind == "apicectomy" else "root_condition"
            if events.get(field, 0) <= eid:
                count = schematic_root_count(tooth, state.dentition or ("deciduous" if state.condition == "deciduous" else "permanent"))
                for index in range(1, count + 1):
                    root = state.root_observations.setdefault(str(index), {"condition": None, "apicectomy": False})
                    root["apicectomy" if kind == "apicectomy" else "condition"] = True if kind == "apicectomy" else "post_core_sound" if kind == "post_core" else "filled_sound"
        elif kind in {"crown", "bridge", "denture", "veneer"} or kind == "inlay_onlay" and effect["target"]["level"] == "crown":
            if events.get("crown", 0) <= eid:
                # Unknown prosthetic material still establishes an artificial
                # root-ineligible site, but is never persisted/inferred as metal.
                state.crown_observation = {"kind": effect["material"] or ("denture_unknown" if kind == "denture" else "crown_unknown"), "issues": []}
        elif kind in {"filling", "inlay_onlay", "sealant"} and effect["target"]["level"] == "surface":
            for key in effect["target"]["surfaces"]:
                if events.get("surfaces", {}).get(key, 0) <= eid:
                    state.surface_observations[key] = {"kind": "sealant" if kind == "sealant" else "restored",
                        "material": effect["material"], "condition": "sound", "defects": []}
    return state
