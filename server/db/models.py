from datetime import datetime, timezone
import json
from typing import Any, Optional
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    JSON,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class FSE(Base):
    __tablename__ = "fses"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    zone = Column(String(64), nullable=False)
    start_lat = Column(Float, nullable=False)
    start_lng = Column(Float, nullable=False)

    merchants = relationship("Merchant", back_populates="fse")
    visits = relationship("Visit", back_populates="fse")

class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(String(64), primary_key=True)
    shop_name = Column(String(256), nullable=False)
    owner_name = Column(String(128), nullable=False)
    category = Column(String(64), nullable=False)
    city = Column(String(64), nullable=False)
    area = Column(String(128), nullable=False)
    pincode = Column(String(16), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    language = Column(String(32), default="hindi")  # hindi, hinglish, english
    phone_e164 = Column(String(32), unique=True, nullable=False, index=True)
    preferred_channel = Column(String(32), default="whatsapp")
    consent = Column(Boolean, default=True)
    footfall_score = Column(Float, default=0.5)
    lead_score = Column(Float, default=50.0)
    score_explanation = Column(Text, default="")
    state = Column(String(32), default="NEW", index=True)
    state_updated_at = Column(DateTime(timezone=True), default=utcnow)
    fse_id = Column(String(64), ForeignKey("fses.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    fse = relationship("FSE", back_populates="merchants")
    messages = relationship("Message", back_populates="merchant", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="merchant", cascade="all, delete-orphan")
    visits = relationship("Visit", back_populates="merchant", cascade="all, delete-orphan")
    device = relationship("Device", back_populates="merchant", uselist=False, cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="merchant", cascade="all, delete-orphan")
    settlements = relationship("Settlement", back_populates="merchant", cascade="all, delete-orphan")
    tickets = relationship("Ticket", back_populates="merchant", cascade="all, delete-orphan")
    actions = relationship("AgentAction", back_populates="merchant", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"

    id = Column(String(64), primary_key=True)
    merchant_id = Column(String(64), ForeignKey("merchants.id"), nullable=False, index=True)
    direction = Column(String(8), nullable=False)  # in, out
    channel = Column(String(32), default="whatsapp")
    kind = Column(String(32), default="text")  # text, media, voice, template
    text = Column(Text, nullable=True)
    event_id = Column(String(128), unique=True, nullable=True, index=True)
    provider_message_id = Column(String(128), nullable=True)
    intent = Column(String(64), nullable=True)
    sentiment = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    merchant = relationship("Merchant", back_populates="messages")

class Document(Base):
    __tablename__ = "documents"

    id = Column(String(64), primary_key=True)
    merchant_id = Column(String(64), ForeignKey("merchants.id"), nullable=False, index=True)
    doc_type = Column(String(32), default="pan")  # pan, address_proof
    file_path = Column(String(512), nullable=False)
    quality = Column(String(32), default="ok")  # ok, blurry, unreadable
    sharpness_score = Column(Float, default=100.0)
    extracted_pan = Column(String(32), nullable=True)
    name_match = Column(Boolean, nullable=True)
    issues = Column(JSON, default=list)
    precheck_passed = Column(Boolean, default=False)
    kyc_status = Column(String(32), default="pending")  # pending, submitted, approved, rejected
    kyc_reference = Column(String(64), nullable=True)
    attempts = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    merchant = relationship("Merchant", back_populates="documents")

class Visit(Base):
    __tablename__ = "visits"

    id = Column(String(64), primary_key=True)
    merchant_id = Column(String(64), ForeignKey("merchants.id"), nullable=False, index=True)
    fse_id = Column(String(64), ForeignKey("fses.id"), nullable=False)
    slot_start = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(32), default="scheduled")  # scheduled, done, cancelled
    cluster_size = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    merchant = relationship("Merchant", back_populates="visits")
    fse = relationship("FSE", back_populates="visits")

class Device(Base):
    __tablename__ = "devices"

    id = Column(String(64), primary_key=True)
    merchant_id = Column(String(64), ForeignKey("merchants.id"), unique=True, nullable=False)
    status = Column(String(32), default="none")  # none, installed, active
    installed_at = Column(DateTime(timezone=True), nullable=True)
    first_txn_at = Column(DateTime(timezone=True), nullable=True)

    merchant = relationship("Merchant", back_populates="device")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String(64), primary_key=True)
    merchant_id = Column(String(64), ForeignKey("merchants.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    status = Column(String(32), default="success")  # success, failed
    created_at = Column(DateTime(timezone=True), default=utcnow)

    merchant = relationship("Merchant", back_populates="transactions")

class Settlement(Base):
    __tablename__ = "settlements"

    id = Column(String(64), primary_key=True)
    merchant_id = Column(String(64), ForeignKey("merchants.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    expected_date = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(32), default="paid")  # paid, delayed, processing
    delay_reason = Column(String(256), nullable=True)

    merchant = relationship("Merchant", back_populates="settlements")

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(String(64), primary_key=True)
    merchant_id = Column(String(64), ForeignKey("merchants.id"), nullable=False, index=True)
    type = Column(String(64), default="general")
    status = Column(String(32), default="open")  # open, resolved, closed
    assigned_to = Column(String(64), default="fse")  # fse, support
    resolved_by = Column(String(64), nullable=True)  # agent, human_name
    created_at = Column(DateTime(timezone=True), default=utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    merchant = relationship("Merchant", back_populates="tickets")

class AgentAction(Base):
    __tablename__ = "agent_actions"

    id = Column(String(64), primary_key=True)
    merchant_id = Column(String(64), ForeignKey("merchants.id"), nullable=False, index=True)
    action_type = Column(String(64), nullable=False)
    params = Column(JSON, default=dict)
    reasoning = Column(Text, nullable=False)
    confidence = Column(Float, default=1.0)
    source = Column(String(32), default="rule")  # rule, llm, fallback
    autonomy_level = Column(String(16), default="L3")  # L1, L2, L3
    status = Column(String(32), default="executed")  # proposed, pending_approval, approved, executed, rejected, overridden, blocked, failed
    guardrail_notes = Column(JSON, default=list)
    prompt_version = Column(String(32), default="v1.0")
    approved_by = Column(String(64), nullable=True)
    rejection_reason = Column(String(256), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    executed_at = Column(DateTime(timezone=True), nullable=True)

    merchant = relationship("Merchant", back_populates="actions")
    handoff = relationship("Handoff", back_populates="action", uselist=False)

class Handoff(Base):
    __tablename__ = "handoffs"

    id = Column(String(64), primary_key=True)
    merchant_id = Column(String(64), ForeignKey("merchants.id"), nullable=False, index=True)
    action_id = Column(String(64), ForeignKey("agent_actions.id"), nullable=True)
    target = Column(String(32), default="fse")  # fse, support
    reason = Column(String(128), nullable=False)
    summary = Column(JSON, default=dict)  # headline, what_happened, sentiment, objection, documents, recommended_next_step
    status = Column(String(32), default="open")  # open, resolved
    resolution_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    action = relationship("AgentAction", back_populates="handoff")

class AutonomyConfig(Base):
    __tablename__ = "autonomy_config"

    action_type = Column(String(64), primary_key=True)
    level = Column(String(16), nullable=False)  # L1, L2, L3
    updated_by = Column(String(64), default="system")
    updated_at = Column(DateTime(timezone=True), default=utcnow)

class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor = Column(String(64), nullable=False)
    event_type = Column(String(64), nullable=False)
    merchant_id = Column(String(64), nullable=True, index=True)
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=utcnow)

class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id = Column(String(64), primary_key=True)
    merchant_id = Column(String(64), ForeignKey("merchants.id"), nullable=False, index=True)
    reason = Column(String(64), nullable=False)
    run_at = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(String(32), default="pending")  # pending, running, done, failed

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(64), nullable=False, index=True)
    merchant_id = Column(String(64), nullable=True, index=True)
    data = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=utcnow)

class DemoState(Base):
    __tablename__ = "demo_state"

    key = Column(String(64), primary_key=True)
    value = Column(Text, nullable=False)

class SimRun(Base):
    __tablename__ = "sim_runs"

    id = Column(String(64), primary_key=True)
    params = Column(JSON, default=dict)
    seeds = Column(Integer, default=30)
    created_at = Column(DateTime(timezone=True), default=utcnow)

class SimResult(Base):
    __tablename__ = "sim_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("sim_runs.id"), nullable=False, index=True)
    metric = Column(String(64), nullable=False)
    arm = Column(String(32), nullable=False)  # manual, saathi
    mean = Column(Float, nullable=False)
    ci_low = Column(Float, nullable=False)
    ci_high = Column(Float, nullable=False)

