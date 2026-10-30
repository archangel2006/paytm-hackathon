import mimetypes
import os
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, UploadFile, File
from server.api.deps import get_repo, APIError
from server.db.repo import PlatformRepo
from server.settings import settings
from server.adapters.clock import clock

router = APIRouter(prefix="/documents", tags=["documents"])

@router.post("/{merchant_id}")
async def upload_document(
    merchant_id: str,
    file: UploadFile = File(...),
    repo: PlatformRepo = Depends(get_repo)
):
    m = repo.get_merchant(merchant_id)
    if not m:
        raise APIError("NOT_FOUND", f"Merchant {merchant_id} not found", status_code=404)

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    extension = mimetypes.guess_extension(file.content_type or "") or ".bin"
    upload_root = Path(settings.UPLOAD_DIR).resolve()
    upload_root.mkdir(parents=True, exist_ok=True)
    dest_path = upload_root / f"{merchant_id}_{uuid4().hex}{extension}"

    contents = await file.read()
    if len(contents) > int(settings.MAX_UPLOAD_MB * 1024 * 1024):
        raise APIError("PAYLOAD_TOO_LARGE", "Uploaded document exceeds the size limit.", status_code=413)
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise APIError("UNSUPPORTED_MEDIA_TYPE", "Only JPEG, PNG, and WebP documents are accepted.", status_code=415)

    resolved_dest = dest_path.resolve()
    if upload_root not in resolved_dest.parents:
        raise APIError("INVALID_UPLOAD_PATH", "Invalid upload destination.", status_code=400)

    with resolved_dest.open("wb") as f:
        f.write(contents)

    doc = repo.save_document(merchant_id=merchant_id, doc_type="pan", file_path=str(resolved_dest))

    # Deterministic simulation of blur / quality check
    filename = file.filename or ""
    is_blurry = "blurry" in filename.lower()
    if is_blurry:
        repo.update_document_validation(
            document_id=doc.id,
            quality="blurry",
            sharpness_score=35.0,
            extracted_pan=None,
            name_match=None,
            issues=["blurry", "pan_unreadable"],
            precheck_passed=False
        )
        action = repo.save_action(
            merchant_id=merchant_id,
            action_type="REREQUEST_DOC",
            params={"doc_type": "pan", "issues": ["blurry"]},
            reasoning="Uploaded PAN photo is blurry and unreadable. Requesting a clear photo.",
            autonomy_level="L3",
            status="executed"
        )
        reply = "Aapka PAN photo thoda dhundhla (blurry) hai. Kripya ek saaf photo dobara bhejein."
        repo.save_message(merchant_id, "out", "simulator", "text", reply)
        return {
            "document_id": doc.id,
            "quality": "blurry",
            "precheck_passed": False,
            "issues": ["blurry"],
            "reply": reply,
            "action_type": "REREQUEST_DOC"
        }
    else:
        repo.update_document_validation(
            document_id=doc.id,
            quality="ok",
            sharpness_score=142.5,
            extracted_pan="ABCDE1234F",
            name_match=True,
            issues=[],
            precheck_passed=True,
            kyc_status="submitted",
            kyc_reference="KYC_REF_98765"
        )
        # Advance state to DOCS_VERIFIED
        if m.state in ("DOCS_PENDING", "ENGAGED"):
            repo.update_state(merchant_id, "DOCS_VERIFIED", "Document passed pre-check")

        # Automatically schedule visit (AT-2 flow)
        nearby = repo.find_nearby_leads(merchant_id, radius_km=2.0)
        cluster_size = max(2, len(nearby) + 1)
        slot = clock.now() + repo.timedelta(days=1) if hasattr(repo, 'timedelta') else clock.now()
        visit = repo.create_visit(merchant_id, m.fse_id or "fse_3", slot, cluster_size=cluster_size)
        repo.update_state(merchant_id, "VISIT_SCHEDULED", "Visit slot assigned after document pre-check pass")

        action = repo.save_action(
            merchant_id=merchant_id,
            action_type="SCHEDULE_VISIT",
            params={"preferred_slot": slot.isoformat(), "cluster_size": cluster_size},
            reasoning=f"PAN card pre-check passed. Route clustered with {cluster_size} nearby shops.",
            autonomy_level="L3",
            status="executed"
        )
        reply = "PAN photo verified! Humne kal subah aapka Soundbox visit book kar diya hai."
        repo.save_message(merchant_id, "out", "simulator", "text", reply)

        return {
            "document_id": doc.id,
            "quality": "ok",
            "precheck_passed": True,
            "extracted_pan": "ABCDE1234F",
            "reply": reply,
            "action_type": "SCHEDULE_VISIT",
            "visit_id": visit.id,
            "cluster_size": cluster_size
        }
