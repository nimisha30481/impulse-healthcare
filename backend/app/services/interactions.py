"""Medication safety checks.

Two very different kinds of check, kept separate on purpose:

1. Deterministic checks on DoseWISE's own data (always available):
   - duplicate therapy: two active medicines share an active ingredient
   - documented allergy: a medicine's ingredient matches a recorded allergy
2. Pairwise drug-drug interactions: ONLY from a configured, licensed clinical knowledge source.
   With no source configured the result is "unable to assess" - never "no interactions found".

AI (Bedrock) may explain verified findings in plain language; it never produces findings.
The workflow is orchestrated by Step Functions when configured, else run in-process with the
same steps, and every run is recorded as an InteractionAssessment.
"""
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.config import get_settings
from app.integrations import aws_services
from app.models import Allergy, InteractionAlert, InteractionAssessment, PrescriptionItem, PrescriptionVersion

PATIENT_UNAVAILABLE = (
    "Drug interaction checking is currently unavailable. Please ask your doctor or pharmacist before "
    "starting any new medicine."
)


def _ingredients(item: PrescriptionItem, v: PrescriptionVersion) -> set[str]:
    if item.catalogue and item.catalogue.ingredients:
        return {i.lower() for i in item.catalogue.ingredients}
    return {v.generic_name.lower()}


def _current(item: PrescriptionItem) -> PrescriptionVersion | None:
    return next((v for v in item.versions if v.version_no == item.current_version_no), None)


class KnowledgeSourceUnavailable(Exception):
    pass


def query_knowledge_source(meds: list[dict]) -> dict:
    """Contract for a licensed provider (HTTP adapter). Expected response:
    {"source": str, "version": str, "updated_at": str,
     "interactions": [{"medicines": [..], "severity": "major|moderate|minor",
                       "description": str, "consequences": str, "guidance": str}]}"""
    s = get_settings()
    if s.interaction_source != "http" or not s.interaction_source_url:
        raise KnowledgeSourceUnavailable("No interaction knowledge source configured")
    r = httpx.post(
        s.interaction_source_url,
        json={"medications": meds},
        headers={"Authorization": f"Bearer {s.interaction_source_api_key}"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def assess(db: Session, patient_id: str, *, new_item: PrescriptionItem | None, user=None) -> InteractionAssessment:
    items = db.execute(
        select(PrescriptionItem).where(
            PrescriptionItem.patient_id == patient_id,
            PrescriptionItem.status.in_(("active", "scheduled", "on_hold", "pending_verification", "draft")),
        )
    ).scalars().all()
    if new_item and new_item not in items:
        items.append(new_item)
    meds = []
    for it in items:
        v = _current(it)
        if v:
            meds.append({"item_id": it.id, "name": v.generic_name, "brand": v.brand_name, "strength": v.strength,
                         "dose": f"{v.dose_amount:g} {v.dose_unit}", "route": v.route,
                         "ingredients": sorted(_ingredients(it, v)), "status": it.status})

    a = InteractionAssessment(
        patient_id=patient_id,
        item_id=new_item.id if new_item else None,
        version_id=_current(new_item).id if new_item and _current(new_item) else None,
        requested_by=getattr(user, "id", None),
        status="partial",
        medications_considered=meds,
        checks_performed=[],
        checks_unavailable=[],
    )
    db.add(a)
    db.flush()

    sfn = aws_services.start_interaction_workflow(a.id, patient_id)
    if sfn.state == "ok":
        a.orchestrator, a.execution_ref = "step_functions", sfn.data

    # --- deterministic checks on DoseWISE data ---
    owner: dict[str, tuple[str, str]] = {}  # ingredient -> (item_id, medicine name)
    for m in meds:
        for ing in m["ingredients"]:
            if ing in owner and owner[ing][0] != m["item_id"]:
                db.add(InteractionAlert(
                    assessment_id=a.id, kind="duplicate_therapy", severity="moderate",
                    medicines=[owner[ing][1], m["name"]],
                    explanation=f"Both medicines contain {ing}.",
                    consequences="Taking both may mean taking more of the same ingredient than intended.",
                    source="DoseWISE ingredient comparison (patient's medication list)",
                    review_guidance="Confirm whether both are intended; check total daily amount.",
                ))
            owner.setdefault(ing, (m["item_id"], m["name"]))
    a.checks_performed = [*a.checks_performed, "duplicate_ingredients"]

    allergies = db.execute(select(Allergy).where(Allergy.patient_id == patient_id, Allergy.status == "active")).scalars()
    allergy_ings = {(al.substance_ingredient or al.substance).lower(): al for al in allergies}
    for m in meds:
        for ing in m["ingredients"]:
            al = allergy_ings.get(ing)
            if al:
                db.add(InteractionAlert(
                    assessment_id=a.id, kind="allergy", severity="major", medicines=[m["name"]],
                    explanation=f"Recorded allergy to {al.substance}" + (f" ({al.reaction})" if al.reaction else ""),
                    consequences="Possible allergic reaction.",
                    source=f"Patient allergy record ({al.provenance.replace('_', ' ')})",
                    review_guidance="Review the allergy record before prescribing.",
                ))
    a.checks_performed = [*a.checks_performed, "documented_allergies"]

    # --- pairwise interactions: licensed knowledge source only ---
    try:
        result = query_knowledge_source(meds)
        a.knowledge_source = result.get("source")
        a.knowledge_source_version = result.get("version")
        for hit in result.get("interactions", []):
            db.add(InteractionAlert(
                assessment_id=a.id, kind="drug_drug", severity=hit.get("severity", "moderate"),
                medicines=hit.get("medicines", []), explanation=hit.get("description", ""),
                consequences=hit.get("consequences"), source=result.get("source", "configured source"),
                source_updated_at=result.get("updated_at"), review_guidance=hit.get("guidance"),
            ))
        a.checks_performed = [*a.checks_performed, "drug_drug_pairs"]
        a.status = "completed"
    except KnowledgeSourceUnavailable as e:
        a.checks_unavailable = [*a.checks_unavailable, "drug_drug_pairs"]
        a.error = str(e)
        a.status = "unavailable"
    except Exception as e:  # noqa: BLE001 - provider failure must surface, not look like "safe"
        a.checks_unavailable = [*a.checks_unavailable, "drug_drug_pairs"]
        a.error = f"Knowledge source error: {str(e)[:200]}"
        a.status = "failed"

    audit.record(db, action="interaction_assessment", resource_type="interaction_assessment", resource_id=a.id,
                 patient_id=patient_id, user=user, reason=a.status)
    db.flush()
    db.refresh(a)
    return a


def serialize(a: InteractionAssessment, audience: str = "doctor") -> dict:
    alerts = [
        {"id": al.id, "kind": al.kind, "severity": al.severity, "medicines": al.medicines,
         "explanation": al.explanation, "consequences": al.consequences, "source": al.source,
         "source_updated_at": al.source_updated_at, "review_guidance": al.review_guidance}
        for al in a.alerts
    ]
    pair_state = (
        "assessed" if "drug_drug_pairs" in (a.checks_performed or [])
        else "unavailable" if a.status == "unavailable" else "failed"
    )
    out = {
        "id": a.id,
        "status": a.status,
        "created_at": a.created_at,
        "orchestrator": a.orchestrator,
        "knowledge_source": a.knowledge_source,
        "checks_performed": a.checks_performed,
        "checks_unavailable": a.checks_unavailable,
        "drug_drug_state": pair_state,
        "alerts": alerts,
        "medications_considered": [m["name"] for m in a.medications_considered or []],
        "reviewed_at": a.reviewed_at,
        "review_decision": a.review_decision,
        "review_note": a.review_note,
        "disclaimer": "No detected interaction does not guarantee safety. Results depend on the completeness "
                      "of the medication list and the configured knowledge source.",
    }
    if audience == "patient":
        out["patient_message"] = (
            PATIENT_UNAVAILABLE if pair_state != "assessed" else
            "Your new medicine may interact with another medicine you take. Please consult your doctor or "
            "pharmacist before starting it." if any(x["kind"] == "drug_drug" for x in alerts) else
            "No known interaction was identified by the configured source. This does not guarantee safety."
        )
    return out
