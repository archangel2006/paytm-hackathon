from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import desc
from agent.domain.enums import DocType

from integrations import simulator
from server.api.deps import APIError, get_repo
from server.db.models import Document, Message, Visit
from server.db.repo import PlatformRepo
from server.settings import settings

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/{merchant_id}")
async def upload_document(
    merchant_id: str,
    file: UploadFile = File(...),
    doc_type: DocType = Query(DocType.PAN),
    repo: PlatformRepo = Depends(get_repo),
):
    merchant = repo.get_merchant(merchant_id)
    if not merchant:
        raise APIError("NOT_FOUND", f"Merchant {merchant_id} not found", status_code=404)

    max_bytes = int(settings.MAX_UPLOAD_MB * 1024 * 1024)
    contents = await file.read(max_bytes + 1)
    if len(contents) > max_bytes:
        raise APIError(
            "PAYLOAD_TOO_LARGE",
            "Uploaded document exceeds the size limit.",
            status_code=413,
        )

    mime_type = file.content_type or "application/octet-stream"
    result = simulator.receive_media(
        merchant_id=merchant.id,
        file_bytes=contents,
        filename=file.filename or "upload",
        mime=mime_type,
        document_type=doc_type,
    )
    if not result.success:
        status_code = 413 if result.error and "too large" in result.error.lower() else 415
        raise APIError(
            "DOCUMENT_PROCESSING_FAILED",
            result.error or "The document could not be processed.",
            status_code=status_code,
        )

    repo.db.expire_all()
    document = repo.db.query(Document).filter(
        Document.merchant_id == merchant.id
    ).order_by(desc(Document.created_at), desc(Document.id)).first()
    action = result.actions[0] if result.actions else None
    outbound = repo.db.query(Message).filter(
        Message.merchant_id == merchant.id,
        Message.direction == "out",
    ).order_by(desc(Message.created_at), desc(Message.id)).first()
    visit = repo.db.query(Visit).filter(
        Visit.merchant_id == merchant.id
    ).order_by(desc(Visit.created_at), desc(Visit.id)).first()

    if document is None:
        raise APIError(
            "DOCUMENT_NOT_SAVED",
            "Document processing completed without a saved document record.",
            status_code=500,
        )

    return {
        "document_id": document.id,
        "doc_type": document.doc_type,
        "quality": document.quality,
        "precheck_passed": document.precheck_passed,
        "issues": document.issues or [],
        "reply": outbound.text if outbound else "",
        "action_type": action.action_type.value if action else None,
        "visit_id": visit.id if visit else None,
        "cluster_size": visit.cluster_size if visit else None,
        "merchant_state": repo.get_merchant(merchant.id).state,
    }
