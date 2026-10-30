from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from server.db.repo import PlatformRepo

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
    phone_e164: str
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
    def __init__(self, db: Session):
        self.db = db
        self.repo = PlatformRepo(db)

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
            phone_e164=m.phone_e164,
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
            phone_e164=m.phone_e164,
            consent=m.consent
        )

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
            phone_e164=m.phone_e164,
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
    ) -> MessageView:
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
        return MessageView(
            id=msg.id,
            merchant_id=msg.merchant_id,
            direction=msg.direction,
            channel=msg.channel,
            kind=msg.kind,
            text=msg.text,
            intent=msg.intent,
            sentiment=msg.sentiment,
            created_at=msg.created_at.isoformat()
        )

    def save_document(self, merchant_id: str, doc_type: str, file_path: str) -> DocumentView:
        doc = self.repo.save_document(merchant_id, doc_type, file_path)
        return DocumentView(
            id=doc.id,
            merchant_id=doc.merchant_id,
            doc_type=doc.doc_type,
            file_path=doc.file_path,
            quality=doc.quality,
            attempts=doc.attempts,
            precheck_passed=doc.precheck_passed
        )

    def update_document_validation(self, document_id: str, result: Any) -> Optional[DocumentView]:
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

        doc = self.repo.update_document_validation(
            document_id=document_id,
            quality=str(quality),
            sharpness_score=float(sharpness_score),
            extracted_pan=extracted_pan,
            name_match=name_match,
            issues=issues,
            precheck_passed=bool(precheck_passed)
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

    def get_context_bundle(self, merchant_id: str) -> Dict[str, Any]:
        return self.repo.get_context_bundle(merchant_id)

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
    ) -> ActionSummary:
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
        return ActionSummary(
            id=act.id,
            merchant_id=act.merchant_id,
            action_type=act.action_type,
            status=act.status,
            autonomy_level=act.autonomy_level,
            reasoning=act.reasoning,
            confidence=act.confidence
        )

    def update_action_status(
        self,
        action_id: str,
        status: str,
        approved_by: Optional[str] = None,
        rejection_reason: Optional[str] = None
    ) -> Optional[ActionSummary]:
        act = self.repo.update_action_status(
            action_id=action_id,
            status=status,
            approved_by=approved_by,
            rejection_reason=rejection_reason
        )
        if not act:
            return None
        return ActionSummary(
            id=act.id,
            merchant_id=act.merchant_id,
            action_type=act.action_type,
            status=act.status,
            autonomy_level=act.autonomy_level,
            reasoning=act.reasoning,
            confidence=act.confidence
        )

    def update_state(self, merchant_id: str, new_state: str, reason: str = "") -> MerchantView:
        m = self.repo.update_state(merchant_id, new_state, reason)
        return self.get_merchant(merchant_id)

    def create_visit(
        self,
        merchant_id: str,
        fse_id: str,
        slot_start: datetime,
        cluster_size: int = 1
    ) -> Dict[str, Any]:
        visit = self.repo.create_visit(merchant_id, fse_id, slot_start, cluster_size)
        return {
            "visit_id": visit.id,
            "fse_id": visit.fse_id,
            "slot": visit.slot_start.isoformat(),
            "cluster_size": visit.cluster_size
        }

    def find_nearby_leads(
        self,
        merchant_id: str,
        radius_km: float = 2.0,
        states: Optional[List[str]] = None
    ) -> List[MerchantView]:
        merchants = self.repo.find_nearby_leads(merchant_id, radius_km, states)
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
                phone_e164=m.phone_e164,
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
    ) -> Dict[str, Any]:
        handoff = self.repo.create_handoff(merchant_id, action_id, target, reason, summary)
        return {
            "id": handoff.id,
            "merchant_id": handoff.merchant_id,
            "target": handoff.target,
            "reason": handoff.reason,
            "status": handoff.status
        }

    def get_autonomy_level(self, action_type: str) -> str:
        return self.repo.get_autonomy_level(action_type)

    def set_consent(self, merchant_id: str, consent: bool) -> bool:
        return self.repo.set_consent(merchant_id, consent)

    def write_audit(self, actor: str, event_type: str, merchant_id: Optional[str], payload: Dict[str, Any]) -> None:
        self.repo.write_audit(actor, event_type, merchant_id, payload)

    def schedule_job(self, merchant_id: str, reason: str, run_at: datetime) -> str:
        job = self.repo.schedule_job(merchant_id, reason, run_at)
        return job.id

