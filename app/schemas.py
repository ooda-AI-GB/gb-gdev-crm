from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any
from datetime import date, datetime
from enum import Enum

# --- Enums ---
class ContactStatus(str, Enum):
    lead = "lead"
    contacted = "contacted"
    proposal = "proposal"
    negotiation = "negotiation"
    closed_won = "closed_won"
    closed_lost = "closed_lost"

class DealStage(str, Enum):
    qualified = "qualified"
    proposal = "proposal"
    negotiation = "negotiation"
    closed_won = "closed_won"
    closed_lost = "closed_lost"

class ActivityType(str, Enum):
    call = "call"
    email = "email"
    meeting = "meeting"
    note = "note"
    task = "task"

class IntelType(str, Enum):
    swot = "swot"
    competitor = "competitor"
    market = "market"

# --- Contact Schemas ---
class ContactBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    status: Optional[ContactStatus] = ContactStatus.lead
    source: Optional[str] = None
    notes: Optional[str] = None
    assigned_to: Optional[str] = None

class ContactCreate(ContactBase):
    pass

class ContactUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    status: Optional[ContactStatus] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    assigned_to: Optional[str] = None

class ContactOut(ContactBase):
    id: int
    user_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Deal Schemas ---
class DealBase(BaseModel):
    title: str
    value: float
    currency: Optional[str] = "USD"
    stage: Optional[DealStage] = DealStage.qualified
    probability: Optional[int] = 0
    expected_close: Optional[date] = None
    notes: Optional[str] = None
    contact_id: int

class DealCreate(DealBase):
    pass

class DealUpdate(BaseModel):
    title: Optional[str] = None
    value: Optional[float] = None
    currency: Optional[str] = None
    stage: Optional[DealStage] = None
    probability: Optional[int] = None
    expected_close: Optional[date] = None
    notes: Optional[str] = None
    contact_id: Optional[int] = None

class DealOut(DealBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Activity Schemas ---
class ActivityBase(BaseModel):
    type: ActivityType
    subject: str
    description: Optional[str] = None
    date: datetime
    completed: Optional[bool] = False
    contact_id: int
    deal_id: Optional[int] = None

class ActivityCreate(ActivityBase):
    pass

class ActivityOut(ActivityBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# --- Intel Schemas ---
class IntelBase(BaseModel):
    company_name: str
    analysis_type: IntelType
    model_used: Optional[str] = None

class IntelCreate(IntelBase):
    pass

class IntelAnalyzeRequest(BaseModel):
    company_name: str
    analysis_type: IntelType
    context: Optional[str] = None

class IntelOut(IntelBase):
    id: int
    content: str
    generated_at: datetime
    requested_by: Optional[str] = None

    class Config:
        from_attributes = True
