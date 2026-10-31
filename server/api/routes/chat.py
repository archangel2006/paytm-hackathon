from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import desc

from integrations import simulator
from integrations.phone import normalize
from server.api.deps import APIError, get_repo
from server.db.models import Message
from server.db.repo import PlatformRepo

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


@router.post("/{merchant_id}/message")
def receive_chat_message(
    merchant_id: str,
    req: ChatMessageRequest,
    repo: PlatformRepo = Depends(get_repo),
):
    merchant = repo.get_merchant(merchant_id)
    if merchant is None:
        try:
            phone = normalize(merchant_id)
        except ValueError as exc:
            raise APIError(
                "NOT_FOUND",
                f"Merchant {merchant_id} not found and is not a valid phone number.",
                status_code=404,
            ) from exc
        merchant = repo.create_lead(phone_e164=phone, channel="simulator")

    result = simulator.receive_text(merchant.id, req.text)
    if not result.success:
        raise APIError(
            "AGENT_PROCESSING_FAILED",
            result.error or "The agent could not process this message.",
            status_code=502,
        )

    action = result.actions[0] if result.actions else None
    latest_outbound = None
    if result.reply_sent:
        latest_outbound = repo.db.query(Message).filter(
            Message.merchant_id == merchant.id,
            Message.direction == "out",
        ).order_by(desc(Message.created_at), desc(Message.id)).first()

    return {
        "reply": latest_outbound.text if latest_outbound else "",
        "action": {
            "id": action.id,
            "action_type": action.action_type.value,
            "autonomy_level": action.autonomy_level.value,
            "status": action.status.value,
            "reasoning": action.reasoning,
        } if action else None,
        "merchant_state": result.state_after.value,
    }
