from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from server.db.repo import PlatformRepo
from server.db.session import current_session
from server.db.models import AgentAction, Visit
from agent.domain.enums import (
    AutonomyLevel,
    Channel,
    DocQuality,
    DocType,
    Language,
    LifecycleState,
)
from agent.ports import (
    ContextBundle as AgentContextBundle,
    Counters as AgentCounters,
    DocumentView as AgentDocumentView,
    MessageView as AgentMessageView,
    MerchantView as AgentMerchantView,
    SettlementView as AgentSettlementView,
    TicketView as AgentTicketView,
    VisitView as AgentVisitView,
)

# Domain views mirroring agent/ports.py
class MerchantView(BaseModel):
    id: str
    shop_name: str
    owner_name: str
    category: str
    city: str
    area: str
    language: str
    state: str
    lead_score: float
    score_explanation: str
    footfall_score: float
    fse_id: str
    lat: float | None = None
    lng: float | None = None
    phone_e164: str
    preferred_channel: Channel = Channel.WHATSAPP
    consent: bool

class MessageView(BaseModel):
    id: str
    merchant_id: str
    direction: str
    channel: str
    kind: str
    text: Optional[str]
    intent: Optional[str] = None
    sentiment: Optional[float] = None
    created_at: str

class DocumentView(BaseModel):
    id: str
    merchant_id: str
    doc_type: str
    file_path: str
    quality: str
    attempts: int
    precheck_passed: bool

class SettlementView(BaseModel):
    amount: float
    status: str
    expected_date: str
    delay_reason: Optional[str] = None

class ActionSummary(BaseModel):
    id: str
    merchant_id: str
    action_type: str
    status: str
    autonomy_level: str
    reasoning: str
    confidence: float

class AgentStoreAdapter:
    """
    Implements agent.ports.Store.
    Adapts platform database repository to plain domain models required by Agent.
    """
    def __init__(self, db: Optional[Session] = None):
        self._db = db

    @property
    def db(self) -> Session:
        return self._db or current_session()

    @property
    def repo(self) -> PlatformRepo:
        return PlatformRepo(self.db)

    def get_merchant_by_phone(self, phone_e164: str) -> Optional[MerchantView]:
        m = self.repo.get_merchant_by_phone(phone_e164)
        if not m:
            return None
        return MerchantView(
            id=m.id,
            shop_name=m.shop_name,
            owner_name=m.owner_name,
            category=m.category,
            city=m.city,
            area=m.area,
            language=m.language,
            state=m.state,
            lead_score=m.lead_score,
            score_explanation=m.score_explanation,
            footfall_score=m.footfall_score,
            fse_id=m.fse_id,
            lat=m.lat,
            lng=m.lng,
            phone_e164=m.phone_e164,
            preferred_channel=m.preferred_channel,
            consent=m.consent
        )

    def get_merchant(self, merchant_id: str) -> Optional[MerchantView]:
        m = self.repo.get_merchant(merchant_id)
        if not m:
            return None
        return MerchantView(
            id=m.id,
            shop_name=m.shop_name,
            owner_name=m.owner_name,
            category=m.category,
            city=m.city,
            area=m.area,
            language=m.language,
            state=m.state,
            lead_score=m.lead_score,
            score_explanation=m.score_explanation,
            footfall_score=m.footfall_score,
            fse_id=m.fse_id,
            lat=m.lat,
            lng=m.lng,
            phone_e164=m.phone_e164,
            preferred_channel=m.preferred_channel,
            consent=m.consent
        )

    def list_merchants(
        self,
        state: LifecycleState | None = None,
        limit: int = 120,
    ) -> list[MerchantView]:
        state_value = state.value if state else None
        merchants, _ = self.repo.list_merchants(
            state=state_value,
            sort_by="score",
            limit=limit,
        )
        return [
            MerchantView(
                id=merchant.id,
                shop_name=merchant.shop_name,
                owner_name=merchant.owner_name,
                category=merchant.category,
                city=merchant.city,
                area=merchant.area,
                language=merchant.language,
                state=merchant.state,
                lead_score=merchant.lead_score,
                score_explanation=merchant.score_explanation,
                footfall_score=merchant.footfall_score,
                fse_id=merchant.fse_id,
                lat=merchant.lat,
                lng=merchant.lng,
                phone_e164=merchant.phone_e164,
                preferred_channel=merchant.preferred_channel,
                consent=merchant.consent,
            )
            for merchant in merchants
        ]

    def create_lead(self, phone_e164: str, channel: str = "whatsapp", language_guess: str = "hindi") -> MerchantView:
        m = self.repo.create_lead(phone_e164=phone_e164, channel=channel, language_guess=language_guess)
        return MerchantView(
            id=m.id,
            shop_name=m.shop_name,
            owner_name=m.owner_name,
            category=m.category,
            city=m.city,
            area=m.area,
            language=m.language,
            state=m.state,
            lead_score=m.lead_score,
            score_explanation=m.score_explanation,
            footfall_score=m.footfall_score,
            fse_id=m.fse_id,
            lat=m.lat,
            lng=m.lng,
            phone_e164=m.phone_e164,
            preferred_channel=m.preferred_channel,
            consent=m.consent
        )

    def update_lead_score(self, merchant_id: str, score: float, explanation: str) -> Optional[MerchantView]:
        m = self.repo.update_lead_score(merchant_id, score, explanation)
        if not m:
            return None
        return self.get_merchant(merchant_id)

    def already_processed(self, event_id: str) -> bool:
        return self.repo.already_processed(event_id)

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
    ) -> str:
        msg = self.repo.save_message(
            merchant_id=merchant_id,
            direction=direction,
            channel=channel,
            kind=kind,
            text=text,
            event_id=event_id,
            provider_message_id=provider_message_id,
            intent=intent,
            sentiment=sentiment
        )
        return msg.id

    def save_document(self, merchant_id: str, doc_type: str, file_path: str) -> str:
        doc = self.repo.save_document(merchant_id, doc_type, file_path)
        return doc.id

    def update_document_validation(
        self,
        document_id: str,
        result: Any,
        kyc_result: Any = None,
    ) -> Optional[DocumentView]:
        # Accepts either DocValidationResult or keyword args / dict
        if hasattr(result, "quality"):
            quality = getattr(result, "quality", "ok")
            sharpness_score = getattr(result, "sharpness_score", 100.0)
            extracted_pan = getattr(result, "extracted_pan", None)
            name_match = getattr(result, "name_match", None)
            issues = getattr(result, "issues", [])
            precheck_passed = getattr(result, "precheck_passed", False)
        elif isinstance(result, dict):
            quality = result.get("quality", "ok")
            sharpness_score = result.get("sharpness_score", 100.0)
            extracted_pan = result.get("extracted_pan")
            name_match = result.get("name_match")
            issues = result.get("issues", [])
            precheck_passed = result.get("precheck_passed", False)
        else:
            quality, sharpness_score, extracted_pan, name_match, issues, precheck_passed = (
                "ok", 100.0, None, None, [], False
            )

        quality = getattr(quality, "value", quality)
        doc = self.repo.update_document_validation(
            document_id=document_id,
            quality=str(quality),
            sharpness_score=float(sharpness_score),
            extracted_pan=extracted_pan,
            name_match=name_match,
            issues=issues,
            precheck_passed=bool(precheck_passed),
            kyc_status=kyc_result.status if kyc_result else "pending",
            kyc_reference=kyc_result.reference_id if kyc_result else None,
        )
        if not doc:
            return None
        return DocumentView(
            id=doc.id,
            merchant_id=doc.merchant_id,
            doc_type=doc.doc_type,
            file_path=doc.file_path,
            quality=doc.quality,
            attempts=doc.attempts,
            precheck_passed=doc.precheck_passed
        )

    def get_context_bundle(self, merchant_id: str) -> AgentContextBundle:
        raw = self.repo.get_context_bundle(merchant_id)
        merchant = raw["merchant"]
        merchant_record = self.repo.get_merchant(merchant_id)

        def parse_datetime(value: Any) -> datetime | None:
            if value is None or isinstance(value, datetime):
                return value
            return datetime.fromisoformat(value)

        agent_merchant = AgentMerchantView(
            id=merchant["id"],
            shop_name=merchant["shop_name"],
            owner_name=merchant["owner_name"],
            category=merchant["category"],
            city=merchant["city"],
            area=merchant["area"],
            language=Language(merchant.get("language", "hindi")),
            phone_e164=merchant["phone_e164"],
            preferred_channel=Channel(merchant.get("preferred_channel", "whatsapp")),
            state=LifecycleState(merchant["state"]),
            lead_score=merchant["lead_score"],
            score_explanation=getattr(merchant_record, "score_explanation", ""),
            footfall_score=getattr(merchant_record, "footfall_score", 0.0),
            fse_id=getattr(merchant_record, "fse_id", "") or "",
            lat=getattr(merchant_record, "lat", None),
            lng=getattr(merchant_record, "lng", None),
        )

        documents = self.repo.get_documents(merchant_id)
        document_views = [
            AgentDocumentView(
                id=document.id,
                doc_type=DocType(document.doc_type),
                quality=DocQuality(document.quality)
                if document.quality in {quality.value for quality in DocQuality}
                else None,
                precheck_passed=document.precheck_passed,
                kyc_status=document.kyc_status,
                attempts=document.attempts,
                issues=document.issues or [],
            )
            for document in documents
        ]

        recent_messages = [
            AgentMessageView(
                id=message.id,
                direction=message.direction,
                channel=Channel(message.channel),
                kind=message.kind,
                text=message.text,
                intent=message.intent,
                sentiment=message.sentiment,
                created_at=message.created_at,
            )
            for message in self.repo.get_messages(merchant_id, limit=10)
        ]

        open_tickets = [
            AgentTicketView(id=ticket["id"], type=ticket["type"], status="open")
            for ticket in raw["open_tickets"]
        ]
        latest_settlement = raw["settlement"]
        settlement_view = (
            AgentSettlementView(
                id=latest_settlement.get("id", ""),
                amount=latest_settlement["amount"],
                expected_date=latest_settlement["expected_date"],
                status=latest_settlement["status"],
                delay_reason=latest_settlement["delay_reason"],
            )
            if latest_settlement
            else None
        )
        visits = self.repo.db.query(Visit).filter(Visit.merchant_id == merchant_id).all()

        return AgentContextBundle(
            merchant=agent_merchant,
            documents=document_views,
            txn_count=raw["activity"]["txn_count"],
            last_txn_at=parse_datetime(raw["activity"]["last_txn_at"]),
            device_status=raw["activity"]["device_status"],
            installed_at=parse_datetime(raw["activity"]["installed_at"]),
            open_tickets=open_tickets,
            latest_settlement=settlement_view,
            recent_messages=recent_messages,
            visits=[
                AgentVisitView(
                    id=visit.id,
                    fse_id=visit.fse_id,
                    slot_start=visit.slot_start.isoformat(),
                    status=visit.status,
                    cluster_size=visit.cluster_size,
                )
                for visit in visits
            ],
            counters=AgentCounters(**raw["counters"]),
            consent=raw["consent"],
        )

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
    ) -> str:
        act = self.repo.save_action(
            merchant_id=merchant_id,
            action_type=action_type,
            params=params,
            reasoning=reasoning,
            confidence=confidence,
            source=source,
            autonomy_level=autonomy_level,
            status=status,
            guardrail_notes=guardrail_notes,
            prompt_version=prompt_version
        )
        return act.id

    def update_action_status(
        self,
        action_id: str,
        status: str,
        executed_at: Optional[datetime] = None,
        approved_by: Optional[str] = None,
        rejection_reason: Optional[str] = None
    ) -> None:
        act = self.repo.update_action_status(
            action_id=action_id,
            status=status,
            executed_at=executed_at,
            approved_by=approved_by,
            rejection_reason=rejection_reason
        )

    def get_action(self, action_id: str) -> Optional[Dict[str, Any]]:
        action = self.repo.db.query(AgentAction).filter(AgentAction.id == action_id).first()
        if not action:
            return None
        return {
            "id": action.id,
            "merchant_id": action.merchant_id,
            "action_type": action.action_type,
            "params": action.params or {},
            "status": action.status,
            "autonomy_level": action.autonomy_level,
            "reasoning": action.reasoning,
        }

    def update_state(self, merchant_id: str, new_state: str, reason: str = "") -> MerchantView:
        m = self.repo.update_state(merchant_id, new_state, reason)
        return self.get_merchant(merchant_id)

    def create_visit(
        self,
        merchant_id: str,
        fse_id: str,
        slot_start: datetime,
        cluster_size: int = 1
    ) -> str:
        if isinstance(slot_start, str):
            slot_start = datetime.fromisoformat(slot_start)
        if slot_start.tzinfo is None:
            slot_start = slot_start.replace(tzinfo=timezone.utc)
        visit = self.repo.create_visit(merchant_id, fse_id, slot_start, cluster_size)
        return visit.id

    def find_nearby_leads(
        self,
        merchant_id: str,
        radius_km: float = 2.0,
        states: Optional[List[str]] = None
    ) -> List[MerchantView]:
        state_values = [state.value if hasattr(state, "value") else state for state in states] if states else None
        merchants = self.repo.find_nearby_leads(merchant_id, radius_km, state_values)
        return [
            MerchantView(
                id=m.id,
                shop_name=m.shop_name,
                owner_name=m.owner_name,
                category=m.category,
                city=m.city,
                area=m.area,
                language=m.language,
                state=m.state,
                lead_score=m.lead_score,
                score_explanation=m.score_explanation,
                footfall_score=m.footfall_score,
                fse_id=m.fse_id,
                lat=m.lat,
                lng=m.lng,
                phone_e164=m.phone_e164,
                preferred_channel=m.preferred_channel,
                consent=m.consent
            )
            for m in merchants
        ]

    def get_settlement(self, merchant_id: str) -> Optional[SettlementView]:
        st = self.repo.get_settlement(merchant_id)
        if not st:
            return None
        return SettlementView(
            amount=st.amount,
            status=st.status,
            expected_date=st.expected_date.isoformat(),
            delay_reason=st.delay_reason
        )

    def create_handoff(
        self,
        merchant_id: str,
        action_id: Optional[str],
        target: str,
        reason: str,
        summary: Dict[str, Any]
    ) -> str:
        handoff = self.repo.create_handoff(merchant_id, action_id, target, reason, summary)
        return handoff.id

    def get_autonomy_level(self, action_type: str) -> AutonomyLevel:
        value = action_type.value if hasattr(action_type, "value") else action_type
        return AutonomyLevel(self.repo.get_autonomy_level(value))

    def set_consent(self, merchant_id: str, consent: bool) -> bool:
        return self.repo.set_consent(merchant_id, consent)

    def write_audit(self, actor: str, event_type: str, merchant_id: Optional[str], payload: Dict[str, Any]) -> None:
        self.repo.write_audit(actor, event_type, merchant_id, payload)

    def schedule_job(self, merchant_id: str, reason: str, run_at: datetime) -> str:
        job = self.repo.schedule_job(merchant_id, reason, run_at)
        return job.id
