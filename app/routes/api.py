from datetime import datetime, date
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Tag, ContactNote, Contact, Deal, Activity,
    CompanyIntel, Notification, AutomationRule,
)
from app.database import get_db
from app.routes import get_current_user

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def to_dict(obj):
    """Convert a SQLAlchemy model instance to a plain dict, serialising datetimes."""
    d = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        if isinstance(val, datetime):
            d[col.name] = val.isoformat()
        elif isinstance(val, date):
            d[col.name] = val.isoformat()
        else:
            d[col.name] = val
    return d


def get_or_404(db: Session, model, id_val: int, label: str):
    obj = db.get(model, id_val)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return obj


# ---------------------------------------------------------------------------
# Pydantic schemas — create / update
# ---------------------------------------------------------------------------

class TagCreate(BaseModel):
    name: str
    color: Optional[str] = "blue"

class TagUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None


class ContactNoteCreate(BaseModel):
    contact_id: int
    content: str

class ContactNoteUpdate(BaseModel):
    content: Optional[str] = None


class ContactCreate(BaseModel):
    user_id: str
    name: str
    email: str
    phone: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    status: Optional[str] = "lead"
    source: Optional[str] = None
    notes: Optional[str] = None
    assigned_to: Optional[str] = None

class ContactUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    status: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    assigned_to: Optional[str] = None


class DealCreate(BaseModel):
    contact_id: int
    title: str
    value: float
    currency: Optional[str] = "USD"
    stage: Optional[str] = "qualified"
    probability: Optional[int] = 0
    expected_close: Optional[date] = None
    notes: Optional[str] = None

class DealUpdate(BaseModel):
    contact_id: Optional[int] = None
    title: Optional[str] = None
    value: Optional[float] = None
    currency: Optional[str] = None
    stage: Optional[str] = None
    probability: Optional[int] = None
    expected_close: Optional[date] = None
    notes: Optional[str] = None


class ActivityCreate(BaseModel):
    contact_id: int
    type: str
    subject: str
    date: datetime
    deal_id: Optional[int] = None
    description: Optional[str] = None
    completed: Optional[bool] = False

class ActivityUpdate(BaseModel):
    contact_id: Optional[int] = None
    deal_id: Optional[int] = None
    type: Optional[str] = None
    subject: Optional[str] = None
    description: Optional[str] = None
    date: Optional[datetime] = None
    completed: Optional[bool] = None


class CompanyIntelCreate(BaseModel):
    company_name: str
    analysis_type: str
    content: str
    model_used: Optional[str] = None
    requested_by: Optional[str] = None
    analysis_version: Optional[str] = None

class CompanyIntelUpdate(BaseModel):
    company_name: Optional[str] = None
    analysis_type: Optional[str] = None
    content: Optional[str] = None
    model_used: Optional[str] = None
    requested_by: Optional[str] = None
    analysis_version: Optional[str] = None


class NotificationCreate(BaseModel):
    user_id: str
    title: str
    message: str
    type: str
    read: Optional[bool] = False
    link: Optional[str] = None

class NotificationUpdate(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None
    type: Optional[str] = None
    read: Optional[bool] = None
    link: Optional[str] = None


class AutomationRuleCreate(BaseModel):
    name: str
    trigger_type: str
    condition: dict
    action_type: str
    action_config: dict
    enabled: Optional[bool] = True

class AutomationRuleUpdate(BaseModel):
    name: Optional[str] = None
    trigger_type: Optional[str] = None
    condition: Optional[dict] = None
    action_type: Optional[str] = None
    action_config: Optional[dict] = None
    enabled: Optional[bool] = None


# ---------------------------------------------------------------------------
# Dashboard — aggregate stats
# ---------------------------------------------------------------------------

@router.get("/dashboard")
def api_dashboard(
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    contacts_by_status = {
        row[0]: row[1]
        for row in db.query(Contact.status, func.count(Contact.id)).group_by(Contact.status).all()
    }
    deals_by_stage = {
        row[0]: row[1]
        for row in db.query(Deal.stage, func.count(Deal.id)).group_by(Deal.stage).all()
    }
    activities_by_type = {
        row[0]: row[1]
        for row in db.query(Activity.type, func.count(Activity.id)).group_by(Activity.type).all()
    }
    deal_total_value = db.query(func.sum(Deal.value)).scalar() or 0.0

    return {
        "counts": {
            "contacts": db.query(Contact).count(),
            "deals": db.query(Deal).count(),
            "activities": db.query(Activity).count(),
            "tags": db.query(Tag).count(),
            "contact_notes": db.query(ContactNote).count(),
            "company_intel": db.query(CompanyIntel).count(),
            "notifications": db.query(Notification).count(),
            "automation_rules": db.query(AutomationRule).count(),
        },
        "contacts_by_status": contacts_by_status,
        "deals_by_stage": deals_by_stage,
        "deal_total_value": deal_total_value,
        "activities_by_type": activities_by_type,
    }


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

@router.get("/tags")
def list_tags(
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    return [to_dict(t) for t in db.query(Tag).limit(limit).all()]


@router.get("/tags/{tag_id}")
def get_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    return to_dict(get_or_404(db, Tag, tag_id, "Tag"))


@router.post("/tags", status_code=201)
def create_tag(
    body: TagCreate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    tag = Tag(**body.model_dump())
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return to_dict(tag)


@router.put("/tags/{tag_id}")
def update_tag(
    tag_id: int,
    body: TagUpdate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    tag = get_or_404(db, Tag, tag_id, "Tag")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(tag, k, v)
    db.commit()
    db.refresh(tag)
    return to_dict(tag)


@router.delete("/tags/{tag_id}", status_code=204)
def delete_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    tag = get_or_404(db, Tag, tag_id, "Tag")
    db.delete(tag)
    db.commit()


# ---------------------------------------------------------------------------
# Contact Notes
# ---------------------------------------------------------------------------

@router.get("/contact-notes")
def list_contact_notes(
    contact_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    q = db.query(ContactNote)
    if contact_id is not None:
        q = q.filter(ContactNote.contact_id == contact_id)
    return [to_dict(n) for n in q.limit(limit).all()]


@router.get("/contact-notes/{note_id}")
def get_contact_note(
    note_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    return to_dict(get_or_404(db, ContactNote, note_id, "ContactNote"))


@router.post("/contact-notes", status_code=201)
def create_contact_note(
    body: ContactNoteCreate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    note = ContactNote(**body.model_dump())
    db.add(note)
    db.commit()
    db.refresh(note)
    return to_dict(note)


@router.put("/contact-notes/{note_id}")
def update_contact_note(
    note_id: int,
    body: ContactNoteUpdate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    note = get_or_404(db, ContactNote, note_id, "ContactNote")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(note, k, v)
    db.commit()
    db.refresh(note)
    return to_dict(note)


@router.delete("/contact-notes/{note_id}", status_code=204)
def delete_contact_note(
    note_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    note = get_or_404(db, ContactNote, note_id, "ContactNote")
    db.delete(note)
    db.commit()


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

@router.get("/contacts")
def list_contacts(
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    q = db.query(Contact)
    if status:
        q = q.filter(Contact.status == status)
    if source:
        q = q.filter(Contact.source == source)
    return [to_dict(c) for c in q.limit(limit).all()]


@router.get("/contacts/{contact_id}")
def get_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    return to_dict(get_or_404(db, Contact, contact_id, "Contact"))


@router.post("/contacts", status_code=201)
def create_contact(
    body: ContactCreate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    contact = Contact(**body.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return to_dict(contact)


@router.put("/contacts/{contact_id}")
def update_contact(
    contact_id: int,
    body: ContactUpdate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    contact = get_or_404(db, Contact, contact_id, "Contact")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(contact, k, v)
    db.commit()
    db.refresh(contact)
    return to_dict(contact)


@router.delete("/contacts/{contact_id}", status_code=204)
def delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    contact = get_or_404(db, Contact, contact_id, "Contact")
    db.delete(contact)
    db.commit()


# ---------------------------------------------------------------------------
# Deals
# ---------------------------------------------------------------------------

@router.get("/deals")
def list_deals(
    stage: Optional[str] = Query(None),
    contact_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    q = db.query(Deal)
    if stage:
        q = q.filter(Deal.stage == stage)
    if contact_id is not None:
        q = q.filter(Deal.contact_id == contact_id)
    return [to_dict(d) for d in q.limit(limit).all()]


@router.get("/deals/{deal_id}")
def get_deal(
    deal_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    return to_dict(get_or_404(db, Deal, deal_id, "Deal"))


@router.post("/deals", status_code=201)
def create_deal(
    body: DealCreate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    deal = Deal(**body.model_dump())
    db.add(deal)
    db.commit()
    db.refresh(deal)
    return to_dict(deal)


@router.put("/deals/{deal_id}")
def update_deal(
    deal_id: int,
    body: DealUpdate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    deal = get_or_404(db, Deal, deal_id, "Deal")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(deal, k, v)
    db.commit()
    db.refresh(deal)
    return to_dict(deal)


@router.delete("/deals/{deal_id}", status_code=204)
def delete_deal(
    deal_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    deal = get_or_404(db, Deal, deal_id, "Deal")
    db.delete(deal)
    db.commit()


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------

@router.get("/activities")
def list_activities(
    type: Optional[str] = Query(None),
    completed: Optional[bool] = Query(None),
    contact_id: Optional[int] = Query(None),
    deal_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    q = db.query(Activity)
    if type:
        q = q.filter(Activity.type == type)
    if completed is not None:
        q = q.filter(Activity.completed == completed)
    if contact_id is not None:
        q = q.filter(Activity.contact_id == contact_id)
    if deal_id is not None:
        q = q.filter(Activity.deal_id == deal_id)
    return [to_dict(a) for a in q.limit(limit).all()]


@router.get("/activities/{activity_id}")
def get_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    return to_dict(get_or_404(db, Activity, activity_id, "Activity"))


@router.post("/activities", status_code=201)
def create_activity(
    body: ActivityCreate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    activity = Activity(**body.model_dump())
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return to_dict(activity)


@router.put("/activities/{activity_id}")
def update_activity(
    activity_id: int,
    body: ActivityUpdate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    activity = get_or_404(db, Activity, activity_id, "Activity")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(activity, k, v)
    db.commit()
    db.refresh(activity)
    return to_dict(activity)


@router.delete("/activities/{activity_id}", status_code=204)
def delete_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    activity = get_or_404(db, Activity, activity_id, "Activity")
    db.delete(activity)
    db.commit()


# ---------------------------------------------------------------------------
# Company Intel
# ---------------------------------------------------------------------------

@router.get("/company-intel")
def list_company_intel(
    analysis_type: Optional[str] = Query(None),
    company_name: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    q = db.query(CompanyIntel)
    if analysis_type:
        q = q.filter(CompanyIntel.analysis_type == analysis_type)
    if company_name:
        q = q.filter(CompanyIntel.company_name.ilike(f"%{company_name}%"))
    return [to_dict(i) for i in q.limit(limit).all()]


@router.get("/company-intel/{intel_id}")
def get_company_intel(
    intel_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    return to_dict(get_or_404(db, CompanyIntel, intel_id, "CompanyIntel"))


@router.post("/company-intel", status_code=201)
def create_company_intel(
    body: CompanyIntelCreate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    intel = CompanyIntel(**body.model_dump())
    db.add(intel)
    db.commit()
    db.refresh(intel)
    return to_dict(intel)


@router.put("/company-intel/{intel_id}")
def update_company_intel(
    intel_id: int,
    body: CompanyIntelUpdate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    intel = get_or_404(db, CompanyIntel, intel_id, "CompanyIntel")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(intel, k, v)
    db.commit()
    db.refresh(intel)
    return to_dict(intel)


@router.delete("/company-intel/{intel_id}", status_code=204)
def delete_company_intel(
    intel_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    intel = get_or_404(db, CompanyIntel, intel_id, "CompanyIntel")
    db.delete(intel)
    db.commit()


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

@router.get("/notifications")
def list_notifications(
    type: Optional[str] = Query(None),
    read: Optional[bool] = Query(None),
    user_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    q = db.query(Notification)
    if type:
        q = q.filter(Notification.type == type)
    if read is not None:
        q = q.filter(Notification.read == read)
    if user_id:
        q = q.filter(Notification.user_id == user_id)
    return [to_dict(n) for n in q.limit(limit).all()]


@router.get("/notifications/{notification_id}")
def get_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    return to_dict(get_or_404(db, Notification, notification_id, "Notification"))


@router.post("/notifications", status_code=201)
def create_notification(
    body: NotificationCreate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    notification = Notification(**body.model_dump())
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return to_dict(notification)


@router.put("/notifications/{notification_id}")
def update_notification(
    notification_id: int,
    body: NotificationUpdate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    notification = get_or_404(db, Notification, notification_id, "Notification")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(notification, k, v)
    db.commit()
    db.refresh(notification)
    return to_dict(notification)


@router.delete("/notifications/{notification_id}", status_code=204)
def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    notification = get_or_404(db, Notification, notification_id, "Notification")
    db.delete(notification)
    db.commit()


# ---------------------------------------------------------------------------
# Automation Rules
# ---------------------------------------------------------------------------

@router.get("/automation-rules")
def list_automation_rules(
    enabled: Optional[bool] = Query(None),
    trigger_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    q = db.query(AutomationRule)
    if enabled is not None:
        q = q.filter(AutomationRule.enabled == enabled)
    if trigger_type:
        q = q.filter(AutomationRule.trigger_type == trigger_type)
    return [to_dict(r) for r in q.limit(limit).all()]


@router.get("/automation-rules/{rule_id}")
def get_automation_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    return to_dict(get_or_404(db, AutomationRule, rule_id, "AutomationRule"))


@router.post("/automation-rules", status_code=201)
def create_automation_rule(
    body: AutomationRuleCreate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    rule = AutomationRule(**body.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return to_dict(rule)


@router.put("/automation-rules/{rule_id}")
def update_automation_rule(
    rule_id: int,
    body: AutomationRuleUpdate,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    rule = get_or_404(db, AutomationRule, rule_id, "AutomationRule")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(rule, k, v)
    db.commit()
    db.refresh(rule)
    return to_dict(rule)


@router.delete("/automation-rules/{rule_id}", status_code=204)
def delete_automation_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    rule = get_or_404(db, AutomationRule, rule_id, "AutomationRule")
    db.delete(rule)
    db.commit()
