from typing import Optional
from fastapi import APIRouter, Depends, Query
import agent
from server.api.deps import get_repo, APIError, require_staff_access
from server.db.models import Merchant
from server.db.repo import PlatformRepo

router = APIRouter(
    prefix="/merchants",
    tags=["merchants"],
    dependencies=[Depends(require_staff_access)],
)


def _successful_transaction_count(merchant: Merchant) -> int:
    return sum(transaction.status == "success" for transaction in merchant.transactions)


def _documents_status(merchant: Merchant) -> str:
    if not merchant.documents:
        return "none"
    latest_by_type = {}
    for document in sorted(
        merchant.documents,
        key=lambda item: (item.created_at.isoformat() if item.created_at else "", item.id),
    ):
        latest_by_type[document.doc_type] = document
    required_documents = [latest_by_type.get(doc_type) for doc_type in ("pan", "address_proof")]
    if all(
        document is not None
        and document.precheck_passed
        and document.kyc_status == "approved"
        for document in required_documents
    ):
        return "verified"
    return "pending"


def _activation_prerequisites_met(merchant: Merchant) -> bool:
    return (
        _documents_status(merchant) == "verified"
        and any(visit.status == "done" for visit in merchant.visits)
        and merchant.device is not None
        and merchant.device.status in {"installed", "active"}
    )


@router.get("")
def list_merchants(
    state: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    fse_id: Optional[str] = Query(None),
    sort: str = Query("score"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=300),
    repo: PlatformRepo = Depends(get_repo)
):
    items, total = repo.list_merchants(
        state=state,
        category=category,
        fse_id=fse_id,
        sort_by=sort,
        page=page,
        limit=limit
    )
    return {
        "items": [
            {
                "id": m.id,
                "shop_name": m.shop_name,
                "owner_name": m.owner_name,
                "category": m.category,
                "city": m.city,
                "area": m.area,
                "language": m.language,
                "state": m.state,
                "lead_score": m.lead_score,
                "fse_id": m.fse_id,
                "txn_count": len(m.transactions),
                "successful_txn_count": _successful_transaction_count(m),
                "docs_status": _documents_status(m),
                "activation_eligible": _activation_prerequisites_met(m),
            }
            for m in items
        ],
        "total": total,
        "page": page,
        "limit": limit
    }

@router.get("/{merchant_id}")
def get_merchant_detail(merchant_id: str, repo: PlatformRepo = Depends(get_repo)):
    m = repo.get_merchant(merchant_id)
    if not m:
        raise APIError("NOT_FOUND", f"Merchant {merchant_id} not found", status_code=404)

    device = repo.get_device(merchant_id)
    settlement = repo.get_settlement(merchant_id)

    return {
        "id": m.id,
        "shop_name": m.shop_name,
        "owner_name": m.owner_name,
        "category": m.category,
        "city": m.city,
        "area": m.area,
        "pincode": m.pincode,
        "lat": m.lat,
        "lng": m.lng,
        "language": m.language,
        "phone_e164": m.phone_e164,
        "preferred_channel": m.preferred_channel,
        "consent": m.consent,
        "footfall_score": m.footfall_score,
        "lead_score": m.lead_score,
        "score_explanation": m.score_explanation,
        "state": m.state,
        "state_updated_at": m.state_updated_at.isoformat() if m.state_updated_at else None,
        "successful_txn_count": _successful_transaction_count(m),
        "fse_id": m.fse_id,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "documents": [
            {
                "id": d.id,
                "doc_type": d.doc_type,
                "quality": d.quality,
                "sharpness_score": d.sharpness_score,
                "precheck_passed": d.precheck_passed,
                "attempts": d.attempts,
                "issues": d.issues or [],
                "kyc_status": d.kyc_status,
                "kyc_reference": d.kyc_reference
            }
            for d in sorted(
                m.documents,
                key=lambda item: (item.created_at.isoformat() if item.created_at else "", item.id),
            )
        ],
        "visits": [
            {
                "id": v.id,
                "fse_id": v.fse_id,
                "slot_start": v.slot_start.isoformat(),
                "status": v.status,
                "cluster_size": v.cluster_size
            }
            for v in m.visits
        ],
        "device": {
            "status": device.status if device else "none",
            "installed_at": device.installed_at.isoformat() if device and device.installed_at else None,
            "first_txn_at": device.first_txn_at.isoformat() if device and device.first_txn_at else None
        } if device else None,
        "settlement": {
            "amount": settlement.amount,
            "expected_date": settlement.expected_date.isoformat(),
            "status": settlement.status,
            "delay_reason": settlement.delay_reason
        } if settlement else None,
        "tickets": [
            {
                "id": t.id,
                "type": t.type,
                "status": t.status,
                "assigned_to": t.assigned_to,
                "created_at": t.created_at.isoformat()
            }
            for t in m.tickets
        ]
    }

@router.get("/{merchant_id}/messages")
def get_merchant_messages(merchant_id: str, limit: int = 50, repo: PlatformRepo = Depends(get_repo)):
    m = repo.get_merchant(merchant_id)
    if not m:
        raise APIError("NOT_FOUND", f"Merchant {merchant_id} not found", status_code=404)
    messages = repo.get_messages(merchant_id, limit=limit)
    return [
        {
            "id": msg.id,
            "merchant_id": msg.merchant_id,
            "direction": msg.direction,
            "channel": msg.channel,
            "kind": msg.kind,
            "text": msg.text,
            "intent": msg.intent,
            "sentiment": msg.sentiment,
            "created_at": msg.created_at.isoformat()
        }
        for msg in messages
    ]

@router.get("/{merchant_id}/actions")
def get_merchant_actions(merchant_id: str, limit: int = 50, repo: PlatformRepo = Depends(get_repo)):
    m = repo.get_merchant(merchant_id)
    if not m:
        raise APIError("NOT_FOUND", f"Merchant {merchant_id} not found", status_code=404)
    actions = repo.list_actions(merchant_id=merchant_id, limit=limit)
    return [
        {
            "id": a.id,
            "merchant_id": a.merchant_id,
            "shop_name": m.shop_name,
            "action_type": a.action_type,
            "autonomy_level": a.autonomy_level,
            "status": a.status,
            "reasoning": a.reasoning,
            "confidence": a.confidence,
            "source": a.source,
            "guardrail_notes": a.guardrail_notes or [],
            "created_at": a.created_at.isoformat(),
            "executed_at": a.executed_at.isoformat() if a.executed_at else None
        }
        for a in actions
    ]

@router.get("/{merchant_id}/next-action")
def preview_next_action(merchant_id: str, repo: PlatformRepo = Depends(get_repo)):
    m = repo.get_merchant(merchant_id)
    if not m:
        raise APIError("NOT_FOUND", f"Merchant {merchant_id} not found", status_code=404)

    proposal = agent.preview_next_action(merchant_id)

    return {
        "merchant_id": merchant_id,
        "action_type": proposal.action_type.value,
        "autonomy_level": proposal.autonomy_level.value,
        "reasoning": proposal.reasoning,
        "confidence": 0.90,
        "status": "proposed"
    }
