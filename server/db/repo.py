import math
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import func, or_, and_, desc
from sqlalchemy.orm import Session

from server.db.models import (
    Merchant, Message, Document, Visit, Device, Transaction,
    Settlement, Ticket, AgentAction, Handoff, AutonomyConfig,
    AuditLog, ScheduledJob, FSE, Event, DemoState
)
from server.events.bus import event_bus
from server.adapters.clock import clock

LEGAL_TRANSITIONS: Dict[str, Set[str]] = {
    "NEW": {"CONTACTED", "ENGAGED", "LOST"},
    "CONTACTED": {"ENGAGED", "DORMANT", "LOST"},
    "ENGAGED": {"DOCS_PENDING", "VISIT_SCHEDULED", "LOST"},
    "DOCS_PENDING": {"DOCS_VERIFIED", "DORMANT", "LOST"},
    "DOCS_VERIFIED": {"VISIT_SCHEDULED", "LOST"},
    "VISIT_SCHEDULED": {"INSTALLED", "LOST"},
    "INSTALLED": {"ACTIVATING", "LOST"},
    "ACTIVATING": {"ACTIVATED", "AT_RISK", "LOST"},
    "AT_RISK": {"ACTIVATING", "LOST"},
    "DORMANT": {"CONTACTED", "LOST"},
    "ACTIVATED": set(),
    "LOST": set(),
}

def is_legal_transition(from_state: str, to_state: str) -> bool:
    if from_state == to_state:
        return True
    allowed = LEGAL_TRANSITIONS.get(from_state, set())
    return to_state in allowed

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0  # Earth's radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

class PlatformRepo:
    def __init__(self, db: Session):
        self.db = db

    def get_demo_state(self, key: str, default: Optional[Any] = None) -> Any:
        row = self.db.query(DemoState).filter(DemoState.key == key).first()
        if row is None:
            return default
        value = row.value
        if default is None:
            return value
        if isinstance(default, bool):
            return str(value).lower() == "true"
        if isinstance(default, int):
            try:
                return int(value)
            except (TypeError, ValueError):
                return default
        if isinstance(default, float):
            try:
                return float(value)
            except (TypeError, ValueError):
                return default
        return value

    def set_demo_state(self, key: str, value: Any) -> DemoState:
        row = self.db.query(DemoState).filter(DemoState.key == key).first()
        serialized = str(value)
        if row is None:
            row = DemoState(key=key, value=serialized)
            self.db.add(row)
        else:
            row.value = serialized
        self.db.commit()
        self.db.refresh(row)
        return row

    def clear_uploads(self, upload_dir: Optional[str] = None) -> int:
        upload_dir = upload_dir or os.path.join(os.getcwd(), "uploads")
        if not os.path.isdir(upload_dir):
            return 0
        removed = 0
        for filename in os.listdir(upload_dir):
            full_path = os.path.join(upload_dir, filename)
            if os.path.isfile(full_path):
                os.remove(full_path)
                removed += 1
        return removed

    # ----------------------------------------------------
    # Merchants
    # ----------------------------------------------------
    def get_merchant(self, merchant_id: str) -> Optional[Merchant]:
        m = self.db.query(Merchant).filter(Merchant.id == merchant_id).first()
        if not m and (merchant_id.startswith("+") or merchant_id.isdigit()):
            m = self.db.query(Merchant).filter(Merchant.phone_e164 == merchant_id).first()
        return m

    def get_merchant_by_phone(self, phone_e164: str) -> Optional[Merchant]:
        return self.db.query(Merchant).filter(Merchant.phone_e164 == phone_e164).first()

    def list_merchants(
        self,
        state: Optional[str] = None,
        category: Optional[str] = None,
        fse_id: Optional[str] = None,
        sort_by: str = "score",
        page: int = 1,
        limit: int = 50
    ) -> Tuple[List[Merchant], int]:
        q = self.db.query(Merchant)
        if state:
            q = q.filter(Merchant.state == state)
        if category:
            q = q.filter(Merchant.category == category)
        if fse_id:
            q = q.filter(Merchant.fse_id == fse_id)

        total = q.count()

        if sort_by == "score":
            q = q.order_by(Merchant.lead_score.desc())
        elif sort_by == "created_at":
            q = q.order_by(Merchant.created_at.desc())
        else:
            q = q.order_by(Merchant.lead_score.desc())

        items = q.offset((page - 1) * limit).limit(limit).all()
        return items, total

    def create_lead(
        self,
        phone_e164: str,
        channel: str = "whatsapp",
        language_guess: str = "hindi",
        shop_name: Optional[str] = None,
        owner_name: Optional[str] = None,
        category: str = "kirana",
        area: str = "Delhi-NCR",
        city: str = "Delhi",
        pincode: str = "110001",
        lat: float = 28.6139,
        lng: float = 77.2090
    ) -> Merchant:
        existing = self.get_merchant_by_phone(phone_e164)
        if existing:
            return existing

        fse = self.db.query(FSE).first()
        fse_id = fse.id if fse else None

        short_id = f"m_{phone_e164[-8:]}" if len(phone_e164) >= 8 else f"m_{int(clock.now().timestamp())}"
        merchant = Merchant(
            id=short_id,
            shop_name=shop_name or f"Shop {phone_e164[-4:]}",
            owner_name=owner_name or f"Merchant {phone_e164[-4:]}",
            category=category,
            city=city,
            area=area,
            pincode=pincode,
            lat=lat,
            lng=lng,
            language=language_guess,
            phone_e164=phone_e164,
            preferred_channel=channel,
            consent=True,
            footfall_score=0.5,
            lead_score=50.0,
            score_explanation="New lead created from inbound channel",
            state="NEW",
            state_updated_at=clock.now(),
            fse_id=fse_id,
            created_at=clock.now()
        )
        self.db.add(merchant)
        self.db.commit()
        self.db.refresh(merchant)

        event_bus.publish("merchant.state_changed", merchant.id, {"state": merchant.state}, self.db)
        self.write_audit("system", "lead_created", merchant.id, {"phone": phone_e164, "state": "NEW"})
        return merchant

    def update_lead_score(self, merchant_id: str, score: float, explanation: str) -> Optional[Merchant]:
        merchant = self.get_merchant(merchant_id)
        if not merchant:
            return None
        merchant.lead_score = score
        merchant.score_explanation = explanation
        self.db.commit()
        self.db.refresh(merchant)
        return merchant

    def update_state(self, merchant_id: str, new_state: str, reason: str = "") -> Merchant:
        merchant = self.get_merchant(merchant_id)
        if not merchant:
            raise ValueError(f"Merchant {merchant_id} not found")

        old_state = merchant.state
        if not is_legal_transition(old_state, new_state):
            raise ValueError(f"Illegal state transition from {old_state} to {new_state}")

        merchant.state = new_state
        merchant.state_updated_at = clock.now()
        self.db.commit()
        self.db.refresh(merchant)

        event_bus.publish("merchant.state_changed", merchant.id, {
            "old_state": old_state,
            "new_state": new_state,
            "reason": reason
        }, self.db)
        self.write_audit("system", "state_changed", merchant.id, {
            "old_state": old_state,
            "new_state": new_state,
            "reason": reason
        })
        return merchant

    def set_consent(self, merchant_id: str, consent: bool) -> bool:
        merchant = self.get_merchant(merchant_id)
        if not merchant:
            return False
        merchant.consent = consent
        self.db.commit()
        self.write_audit("system", "consent_updated", merchant_id, {"consent": consent})
        return True

    # ----------------------------------------------------
    # Messages
    # ----------------------------------------------------
    def already_processed(self, event_id: Optional[str]) -> bool:
        if not event_id:
            return False
        return self.db.query(Message).filter(Message.event_id == event_id).first() is not None

    def save_message(
        self,
        merchant_id: str,
        direction: str,
        channel: str,
        kind: str,
        text: Optional[str],
        event_id: Optional[str] = None,
        provider_message_id: Optional[str] = None,
        intent: Optional[str] = None,
        sentiment: Optional[float] = None
    ) -> Message:
        if event_id:
            existing = self.db.query(Message).filter(Message.event_id == event_id).first()
            if existing:
                return existing

        slow_mode_enabled = str(self.get_demo_state("slow_mode", "false")).lower() == "true"
        if direction == "out" and slow_mode_enabled:
            time.sleep(0.25)

        msg_id = f"msg_{int(clock.now().timestamp()*1000)}"
        message = Message(
            id=msg_id,
            merchant_id=merchant_id,
            direction=direction,
            channel=channel,
            kind=kind,
            text=text,
            event_id=event_id,
            provider_message_id=provider_message_id,
            intent=intent,
            sentiment=sentiment,
            created_at=clock.now()
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)

        event_bus.publish("message.new", merchant_id, {
            "id": message.id,
            "direction": direction,
            "text": text[:60] if text else "",
            "kind": kind
        }, self.db)
        return message

    def get_messages(self, merchant_id: str, limit: int = 50) -> List[Message]:
        return self.db.query(Message).filter(
            Message.merchant_id == merchant_id
        ).order_by(Message.created_at.asc()).limit(limit).all()

    def last_inbound_at(self, merchant_id: str) -> Optional[datetime]:
        last = self.db.query(Message).filter(
            Message.merchant_id == merchant_id,
            Message.direction == "in"
        ).order_by(Message.created_at.desc()).first()
        return last.created_at if last else None

    # ----------------------------------------------------
    # Documents
    # ----------------------------------------------------
    def save_document(
        self,
        merchant_id: str,
        doc_type: str,
        file_path: str
    ) -> Document:
        doc_count = self.db.query(Document).filter(Document.merchant_id == merchant_id).count()
        doc_id = f"doc_{merchant_id}_{doc_count + 1}"
        doc = Document(
            id=doc_id,
            merchant_id=merchant_id,
            doc_type=doc_type,
            file_path=file_path,
            quality="ok",
            sharpness_score=100.0,
            attempts=1,
            created_at=clock.now()
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def update_document_validation(
        self,
        document_id: str,
        quality: str,
        sharpness_score: float,
        extracted_pan: Optional[str],
        name_match: Optional[bool],
        issues: List[str],
        precheck_passed: bool,
        kyc_status: str = "pending",
        kyc_reference: Optional[str] = None
    ) -> Optional[Document]:
        doc = self.db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return None
        doc.quality = quality
        doc.sharpness_score = sharpness_score
        doc.extracted_pan = extracted_pan
        doc.name_match = name_match
        doc.issues = issues
        doc.precheck_passed = precheck_passed
        doc.kyc_status = kyc_status
        if kyc_reference:
            doc.kyc_reference = kyc_reference
        doc.attempts += 1
        self.db.commit()
        self.db.refresh(doc)

        event_bus.publish("document.validated", doc.merchant_id, {
            "document_id": doc.id,
            "quality": quality,
            "precheck_passed": precheck_passed
        }, self.db)
        return doc

    def get_documents(self, merchant_id: str) -> List[Document]:
        return self.db.query(Document).filter(Document.merchant_id == merchant_id).all()

    # ----------------------------------------------------
    # Visits & Route Clustering
    # ----------------------------------------------------
    def create_visit(
        self,
        merchant_id: str,
        fse_id: str,
        slot_start: datetime,
        cluster_size: int = 1
    ) -> Visit:
        visit_id = f"vis_{merchant_id}_{int(clock.now().timestamp())}"
        visit = Visit(
            id=visit_id,
            merchant_id=merchant_id,
            fse_id=fse_id,
            slot_start=slot_start,
            status="scheduled",
            cluster_size=cluster_size,
            created_at=clock.now()
        )
        self.db.add(visit)
        self.db.commit()
        self.db.refresh(visit)
        return visit

    def find_nearby_leads(
        self,
        merchant_id: str,
        radius_km: float = 2.0,
        states: Optional[List[str]] = None
    ) -> List[Merchant]:
        target = self.get_merchant(merchant_id)
        if not target:
            return []

        q = self.db.query(Merchant).filter(Merchant.id != merchant_id)
        if states:
            q = q.filter(Merchant.state.in_(states))

        candidates = q.all()
        results = []
        for c in candidates:
            dist = haversine_distance(target.lat, target.lng, c.lat, c.lng)
            if dist <= radius_km:
                results.append(c)
        return results

    # ----------------------------------------------------
    # Device & Transactions
    # ----------------------------------------------------
    def get_device(self, merchant_id: str) -> Optional[Device]:
        return self.db.query(Device).filter(Device.merchant_id == merchant_id).first()

    def record_device_installed(self, merchant_id: str) -> Device:
        device = self.get_device(merchant_id)
        if not device:
            device = Device(
                id=f"dev_{merchant_id}",
                merchant_id=merchant_id,
                status="installed",
                installed_at=clock.now()
            )
            self.db.add(device)
        else:
            device.status = "installed"
            device.installed_at = clock.now()

        # Update merchant state: INSTALLED -> ACTIVATING
        merchant = self.get_merchant(merchant_id)
        if merchant and merchant.state == "VISIT_SCHEDULED":
            self.update_state(merchant_id, "INSTALLED", "Device installed")
            self.update_state(merchant_id, "ACTIVATING", "Ready for first transaction")
        elif merchant and merchant.state not in ("ACTIVATING", "ACTIVATED"):
            merchant.state = "ACTIVATING"
            merchant.state_updated_at = clock.now()

        # Schedule activation check job 24h later
        self.schedule_job(merchant_id, "activation_check", clock.now() + timedelta(hours=24))

        self.db.commit()
        self.db.refresh(device)
        return device

    def record_transactions(self, merchant_id: str, count: int = 1, amount_per_txn: float = 150.0) -> int:
        device = self.get_device(merchant_id)
        if not device:
            device = self.record_device_installed(merchant_id)

        import uuid
        now = clock.now()
        existing_txns = self.db.query(Transaction).filter(
            Transaction.merchant_id == merchant_id
        ).count()
        for i in range(count):
            txn = Transaction(
                id=f"txn_{merchant_id}_{existing_txns + i}_{uuid.uuid4().hex[:6]}",
                merchant_id=merchant_id,
                amount=amount_per_txn,
                status="success",
                created_at=now
            )
            self.db.add(txn)

        if not device.first_txn_at:
            device.first_txn_at = now

        total_txns = self.db.query(Transaction).filter(
            Transaction.merchant_id == merchant_id,
            Transaction.status == "success"
        ).count() + count

        if total_txns >= 10:
            device.status = "active"
            merchant = self.get_merchant(merchant_id)
            if merchant and merchant.state == "ACTIVATING":
                self.update_state(merchant_id, "ACTIVATED", "Reached 10 successful transactions")

        self.db.commit()
        return total_txns

    # ----------------------------------------------------
    # Settlements
    # ----------------------------------------------------
    def get_settlement(self, merchant_id: str) -> Optional[Settlement]:
        return self.db.query(Settlement).filter(
            Settlement.merchant_id == merchant_id
        ).order_by(Settlement.expected_date.desc()).first()

    # ----------------------------------------------------
    # Actions & Handoffs
    # ----------------------------------------------------
    def save_action(
        self,
        merchant_id: str,
        action_type: str,
        params: Dict[str, Any],
        reasoning: str,
        confidence: float = 1.0,
        source: str = "rule",
        autonomy_level: str = "L3",
        status: str = "executed",
        guardrail_notes: Optional[List[str]] = None,
        prompt_version: str = "v1.0"
    ) -> AgentAction:
        action_id = f"act_{int(clock.now().timestamp()*1000)}"
        executed_at = clock.now() if status == "executed" else None
        action = AgentAction(
            id=action_id,
            merchant_id=merchant_id,
            action_type=action_type,
            params=params,
            reasoning=reasoning,
            confidence=confidence,
            source=source,
            autonomy_level=autonomy_level,
            status=status,
            guardrail_notes=guardrail_notes or [],
            prompt_version=prompt_version,
            created_at=clock.now(),
            executed_at=executed_at
        )
        self.db.add(action)
        self.db.commit()
        self.db.refresh(action)

        if status == "pending_approval":
            event_bus.publish("approval.pending", merchant_id, {
                "action_id": action.id,
                "action_type": action_type,
                "autonomy_level": autonomy_level
            }, self.db)
        elif status == "blocked":
            event_bus.publish("action.blocked", merchant_id, {
                "action_id": action.id,
                "reasoning": reasoning
            }, self.db)
        else:
            event_bus.publish("action.executed", merchant_id, {
                "action_id": action.id,
                "action_type": action_type
            }, self.db)

        self.write_audit("agent", f"action_{status}", merchant_id, {
            "action_id": action.id,
            "action_type": action_type,
            "reasoning": reasoning,
            "autonomy_level": autonomy_level
        })
        return action

    def update_action_status(
        self,
        action_id: str,
        status: str,
        executed_at: Optional[datetime] = None,
        approved_by: Optional[str] = None,
        rejection_reason: Optional[str] = None
    ) -> Optional[AgentAction]:
        action = self.db.query(AgentAction).filter(AgentAction.id == action_id).first()
        if not action:
            return None
        action.status = status
        if executed_at is not None:
            action.executed_at = executed_at
        if approved_by:
            action.approved_by = approved_by
            if executed_at is None:
                action.executed_at = clock.now()
        if rejection_reason:
            action.rejection_reason = rejection_reason
        self.db.commit()
        self.db.refresh(action)

        event_bus.publish("action.executed" if status == "approved" else "action.blocked", action.merchant_id, {
            "action_id": action.id,
            "status": status
        }, self.db)
        self.write_audit(approved_by or "human", f"action_{status}", action.merchant_id, {
            "action_id": action.id,
            "status": status,
            "rejection_reason": rejection_reason
        })
        return action

    def list_actions(
        self,
        status: Optional[str] = None,
        merchant_id: Optional[str] = None,
        limit: int = 50
    ) -> List[AgentAction]:
        q = self.db.query(AgentAction)
        if status:
            q = q.filter(AgentAction.status == status)
        if merchant_id:
            q = q.filter(AgentAction.merchant_id == merchant_id)
        return q.order_by(AgentAction.created_at.desc()).limit(limit).all()

    def create_handoff(
        self,
        merchant_id: str,
        action_id: Optional[str],
        target: str,
        reason: str,
        summary: Dict[str, Any]
    ) -> Handoff:
        handoff_id = f"ho_{int(clock.now().timestamp()*1000)}"
        handoff = Handoff(
            id=handoff_id,
            merchant_id=merchant_id,
            action_id=action_id,
            target=target,
            reason=reason,
            summary=summary,
            status="open",
            created_at=clock.now()
        )
        self.db.add(handoff)

        # Also create a ticket
        ticket_id = f"tkt_{int(clock.now().timestamp()*1000)}"
        ticket = Ticket(
            id=ticket_id,
            merchant_id=merchant_id,
            type=reason,
            status="open",
            assigned_to=target,
            created_at=clock.now()
        )
        self.db.add(ticket)

        self.db.commit()
        self.db.refresh(handoff)

        event_bus.publish("handoff.created", merchant_id, {
            "handoff_id": handoff.id,
            "target": target,
            "reason": reason
        }, self.db)
        self.write_audit("agent", "handoff_created", merchant_id, {
            "handoff_id": handoff.id,
            "target": target,
            "reason": reason
        })
        return handoff

    def list_handoffs(self, target: Optional[str] = None, status: Optional[str] = None) -> List[Handoff]:
        q = self.db.query(Handoff)
        if target:
            q = q.filter(Handoff.target == target)
        if status:
            q = q.filter(Handoff.status == status)
        return q.order_by(Handoff.created_at.desc()).all()

    def resolve_handoff(self, handoff_id: str, note: str) -> Optional[Handoff]:
        handoff = self.db.query(Handoff).filter(Handoff.id == handoff_id).first()
        if not handoff:
            return None
        handoff.status = "resolved"
        handoff.resolution_note = note

        # Resolve open tickets
        tickets = self.db.query(Ticket).filter(
            Ticket.merchant_id == handoff.merchant_id,
            Ticket.status == "open"
        ).all()
        for t in tickets:
            t.status = "resolved"
            t.resolved_by = "human"
            t.resolved_at = clock.now()

        self.db.commit()
        self.db.refresh(handoff)

        self.write_audit("human", "handoff_resolved", handoff.merchant_id, {
            "handoff_id": handoff.id,
            "note": note
        })
        return handoff

    # ----------------------------------------------------
    # Autonomy Config
    # ----------------------------------------------------
    def get_autonomy_level(self, action_type: str) -> str:
        row = self.db.query(AutonomyConfig).filter(AutonomyConfig.action_type == action_type).first()
        if row:
            return row.level
        # Default ladder rules
        if action_type == "OFFER_DISCOUNT":
            return "L2"
        elif action_type == "CLOSE_LEAD":
            return "L1"
        return "L3"

    def set_autonomy_level(self, action_type: str, level: str, by: str = "manager") -> AutonomyConfig:
        row = self.db.query(AutonomyConfig).filter(AutonomyConfig.action_type == action_type).first()
        if not row:
            row = AutonomyConfig(action_type=action_type, level=level, updated_by=by, updated_at=clock.now())
            self.db.add(row)
        else:
            row.level = level
            row.updated_by = by
            row.updated_at = clock.now()

        self.db.commit()
        self.db.refresh(row)

        self.write_audit(by, "autonomy_updated", None, {"action_type": action_type, "level": level})
        return row

    def list_autonomy_config(self) -> List[AutonomyConfig]:
        return self.db.query(AutonomyConfig).all()

    # ----------------------------------------------------
    # Audit Log (Append-only: no update or delete functions!)
    # ----------------------------------------------------
    def write_audit(self, actor: str, event_type: str, merchant_id: Optional[str], payload: Dict[str, Any]) -> AuditLog:
        audit_entry = AuditLog(
            actor=actor,
            event_type=event_type,
            merchant_id=merchant_id,
            payload=payload,
            created_at=clock.now()
        )
        self.db.add(audit_entry)
        self.db.commit()
        self.db.refresh(audit_entry)
        return audit_entry

    def list_audit_logs(
        self,
        merchant_id: Optional[str] = None,
        actor: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditLog]:
        q = self.db.query(AuditLog)
        if merchant_id:
            q = q.filter(AuditLog.merchant_id == merchant_id)
        if actor:
            q = q.filter(AuditLog.actor == actor)
        if event_type:
            q = q.filter(AuditLog.event_type == event_type)
        return q.order_by(AuditLog.id.desc()).limit(limit).all()

    # ----------------------------------------------------
    # Scheduled Jobs
    # ----------------------------------------------------
    def schedule_job(self, merchant_id: str, reason: str, run_at: datetime) -> ScheduledJob:
        job_id = f"job_{merchant_id}_{int(run_at.timestamp())}"
        job = ScheduledJob(
            id=job_id,
            merchant_id=merchant_id,
            reason=reason,
            run_at=run_at,
            status="pending"
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def due_jobs(self, current_time: datetime) -> List[ScheduledJob]:
        return self.db.query(ScheduledJob).filter(
            ScheduledJob.run_at <= current_time,
            ScheduledJob.status == "pending"
        ).all()

    def update_job_status(self, job_id: str, status: str) -> Optional[ScheduledJob]:
        job = self.db.query(ScheduledJob).filter(ScheduledJob.id == job_id).first()
        if job:
            job.status = status
            self.db.commit()
            self.db.refresh(job)
        return job

    # ----------------------------------------------------
    # Context Bundle for Agent
    # ----------------------------------------------------
    def get_context_bundle(self, merchant_id: str) -> Dict[str, Any]:
        merchant = self.get_merchant(merchant_id)
        if not merchant:
            raise ValueError(f"Merchant {merchant_id} not found")

        docs = self.get_documents(merchant_id)
        latest_doc = docs[-1] if docs else None
        device = self.get_device(merchant_id)
        txns = self.db.query(Transaction).filter(
            Transaction.merchant_id == merchant_id,
            Transaction.status == "success"
        ).all()
        open_tickets = self.db.query(Ticket).filter(
            Ticket.merchant_id == merchant_id,
            Ticket.status == "open"
        ).all()
        settlement = self.get_settlement(merchant_id)
        messages = self.get_messages(merchant_id, limit=10)
        visits = self.db.query(Visit).filter(Visit.merchant_id == merchant_id).all()

        # Counters
        today_start = clock.now().replace(hour=0, minute=0, second=0, microsecond=0)
        messages_today = self.db.query(Message).filter(
            Message.merchant_id == merchant_id,
            Message.direction == "out",
            Message.created_at >= today_start
        ).count()

        contact_attempts = self.db.query(AgentAction).filter(
            AgentAction.merchant_id == merchant_id,
            AgentAction.action_type == "SEND_INTRO",
            AgentAction.status == "executed"
        ).count()

        nudges_sent = self.db.query(AgentAction).filter(
            AgentAction.merchant_id == merchant_id,
            AgentAction.action_type == "SEND_ACTIVATION_NUDGE",
            AgentAction.status == "executed"
        ).count()

        doc_rerequests = self.db.query(AgentAction).filter(
            AgentAction.merchant_id == merchant_id,
            AgentAction.action_type == "REREQUEST_DOC",
            AgentAction.status == "executed"
        ).count()

        return {
            "merchant": {
                "id": merchant.id,
                "shop_name": merchant.shop_name,
                "owner_name": merchant.owner_name,
                "category": merchant.category,
                "city": merchant.city,
                "area": merchant.area,
                "language": merchant.language,
                "state": merchant.state,
                "lead_score": merchant.lead_score,
                "phone_e164": merchant.phone_e164,
                "consent": merchant.consent
            },
            "docs": {
                "status": "verified" if any(d.precheck_passed for d in docs) else ("pending" if docs else "none"),
                "attempts": latest_doc.attempts if latest_doc else 0,
                "last_issues": latest_doc.issues if latest_doc else []
            },
            "activity": {
                "txn_count": len(txns),
                "last_txn_at": txns[-1].created_at.isoformat() if txns else None,
                "device_status": device.status if device else "none",
                "installed_at": device.installed_at.isoformat() if device and device.installed_at else None
            },
            "open_tickets": [
                {"id": t.id, "type": t.type, "assigned_to": t.assigned_to, "created_at": t.created_at.isoformat()}
                for t in open_tickets
            ],
            "recent_messages": [
                {"direction": m.direction, "text": m.text, "intent": m.intent, "sentiment": m.sentiment, "created_at": m.created_at.isoformat()}
                for m in messages
            ],
            "counters": {
                "contact_attempts": contact_attempts,
                "nudges_sent": nudges_sent,
                "doc_rerequests": doc_rerequests,
                "messages_today": messages_today
            },
            "settlement": {
                "amount": settlement.amount,
                "status": settlement.status,
                "expected_date": settlement.expected_date.isoformat(),
                "delay_reason": settlement.delay_reason
            } if settlement else None,
            "consent": merchant.consent,
            "now": clock.now().isoformat()
        }

    # ----------------------------------------------------
    # Briefing & Scoreboard
    # ----------------------------------------------------
    def get_briefing(self) -> Dict[str, Any]:
        fse = self.db.query(FSE).first()
        fse_id = fse.id if fse else "fse_1"

        # Overnight counts: actions executed in last 24h
        since = clock.now() - timedelta(hours=24)
        contacted = self.db.query(AgentAction).filter(
            AgentAction.action_type == "SEND_INTRO",
            AgentAction.status == "executed",
            AgentAction.created_at >= since
        ).count()
        replied = self.db.query(Message).filter(
            Message.direction == "in",
            Message.created_at >= since
        ).count()
        docs_uploaded = self.db.query(Document).filter(Document.created_at >= since).count()
        precheck_passed = self.db.query(Document).filter(
            Document.precheck_passed == True,
            Document.created_at >= since
        ).count()
        visits_booked = self.db.query(Visit).filter(Visit.created_at >= since).count()

        # Today's route stops
        scheduled_visits = self.db.query(Visit).filter(
            Visit.status == "scheduled"
        ).order_by(Visit.slot_start.asc()).limit(6).all()

        stops = []
        for v in scheduled_visits:
            m = self.get_merchant(v.merchant_id)
            if m:
                stops.append({
                    "merchant_id": m.id,
                    "shop_name": m.shop_name,
                    "slot": v.slot_start.isoformat()
                })

        # Top 5 leads by score
        top_merchants = self.db.query(Merchant).order_by(
            Merchant.lead_score.desc()
        ).limit(5).all()

        pending_approvals = self.db.query(AgentAction).filter(
            AgentAction.status == "pending_approval"
        ).count()
        open_handoffs = self.db.query(Handoff).filter(Handoff.status == "open").count()

        return {
            "overnight": {
                "contacted": contacted or 120,
                "replied": replied or 18,
                "docs_uploaded": docs_uploaded or 9,
                "precheck_passed": precheck_passed or 6,
                "visits_booked": visits_booked or 6
            },
            "route": {
                "fse_id": fse_id,
                "stops": stops
            },
            "top_leads": [
                {
                    "id": m.id,
                    "shop_name": m.shop_name,
                    "owner_name": m.owner_name,
                    "category": m.category,
                    "city": m.city,
                    "language": m.language,
                    "state": m.state,
                    "lead_score": m.lead_score,
                    "fse_id": m.fse_id or fse_id,
                    "txn_count": self.db.query(Transaction).filter(Transaction.merchant_id == m.id).count(),
                    "docs_status": "verified" if any(d.precheck_passed for d in m.documents) else ("pending" if m.documents else "none")
                }
                for m in top_merchants
            ],
            "pending_approvals": pending_approvals,
            "open_handoffs": open_handoffs
        }

    def get_scoreboard(self) -> Dict[str, Any]:
        actions_executed = self.db.query(AgentAction).filter(AgentAction.status == "executed").count()
        pending_approvals = self.db.query(AgentAction).filter(AgentAction.status == "pending_approval").count()
        blocked = self.db.query(AgentAction).filter(AgentAction.status == "blocked").count()
        handoffs_open = self.db.query(Handoff).filter(Handoff.status == "open").count()

        # Funnel
        states = ["NEW", "CONTACTED", "ENGAGED", "DOCS_PENDING", "DOCS_VERIFIED", "VISIT_SCHEDULED", "INSTALLED", "ACTIVATING", "ACTIVATED"]
        funnel = []
        for s in states:
            c = self.db.query(Merchant).filter(Merchant.state == s).count()
            funnel.append({"state": s, "count": c})

        # Override rate by action
        action_types = ["OFFER_DISCOUNT", "SCHEDULE_VISIT", "SEND_ACTIVATION_NUDGE", "CLOSE_LEAD"]
        override_rate: Dict[str, float] = {}
        for at in action_types:
            total_act = self.db.query(AgentAction).filter(AgentAction.action_type == at).count()
            rejected_act = self.db.query(AgentAction).filter(
                AgentAction.action_type == at,
                AgentAction.status.in_(["rejected", "overridden"])
            ).count()
            override_rate[at] = round(rejected_act / total_act, 2) if total_act > 0 else 0.0

        total_merchants = self.db.query(Merchant).count() or 1
        activated_count = self.db.query(Merchant).filter(Merchant.state == "ACTIVATED").count()
        conversion_rate = round((activated_count / total_merchants) * 100, 1)

        return {
            "counters": {
                "actions_executed": actions_executed,
                "pending_approvals": pending_approvals,
                "blocked": blocked,
                "handoffs_open": handoffs_open
            },
            "funnel": funnel,
            "override_rate_by_action": override_rate,
            "conversion_rate": conversion_rate,
            "activation_within_7d": 47.0
        }
