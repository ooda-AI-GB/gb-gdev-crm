from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, Boolean, Date, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

contact_tags = Table(
    "contact_tags",
    Base.metadata,
    Column("contact_id", Integer, ForeignKey("contacts.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
)

class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    color = Column(String(20), default="blue") # e.g. "blue", "red", "green", "purple", "gold"

    contacts = relationship("Contact", secondary=contact_tags, back_populates="tags")

class ContactNote(Base):
    __tablename__ = "contact_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    contact = relationship("Contact", back_populates="contact_notes")

class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False) # who owns this contact (from auth)
    name = Column(String(100), nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String(20), nullable=True)
    company = Column(String(100), nullable=True)
    title = Column(String(100), nullable=True)
    status = Column(String, default="lead") # "lead", "contacted", "proposal", "negotiation", "closed_won", "closed_lost"
    source = Column(String, nullable=True) # "website", "referral", "cold_call", "linkedin", "other"
    notes = Column(Text, nullable=True)
    assigned_to = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    tags = relationship("Tag", secondary=contact_tags, back_populates="contacts")
    contact_notes = relationship("ContactNote", back_populates="contact", cascade="all, delete-orphan")

    deals = relationship("Deal", back_populates="contact", cascade="all, delete-orphan")
    activities = relationship("Activity", back_populates="contact", cascade="all, delete-orphan")

class Deal(Base):
    __tablename__ = "deals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False)
    title = Column(String(200), nullable=False)
    value = Column(Float, nullable=False)
    currency = Column(String(3), default="USD")
    stage = Column(String, default="qualified") # "qualified", "proposal", "negotiation", "closed_won", "closed_lost"
    probability = Column(Integer, default=0)
    expected_close = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    contact = relationship("Contact", back_populates="deals")
    activities = relationship("Activity", back_populates="deal", cascade="all, delete-orphan")

class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=True)
    type = Column(String, nullable=False) # "call", "email", "meeting", "note", "task"
    subject = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    date = Column(DateTime(timezone=True), nullable=False)
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    contact = relationship("Contact", back_populates="activities")
    deal = relationship("Deal", back_populates="activities")

class CompanyIntel(Base):
    __tablename__ = "company_intel"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(String(200), nullable=False)
    analysis_type = Column(String, nullable=False) # "swot", "competitor", "market"
    content = Column(Text, nullable=False)
    model_used = Column(String, nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    requested_by = Column(String, nullable=True)

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String, nullable=False) # task_due, deal_milestone, system
    read = Column(Boolean, default=False)
    link = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
