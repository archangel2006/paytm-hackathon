"""
Mock KYC service.

Deterministic and clearly labelled as a mock.
"""

from __future__ import annotations

import logging

from agent.ports import KycResult

logger = logging.getLogger(__name__)


def submit_to_mock_kyc(document_id: str) -> KycResult:
    """Submit a document that passed the pre-check to the mock KYC service.

    Rules:
    - Any document whose owner name contains "REJECT" returns ``rejected``.
    - Everything else returns ``approved`` with a reference id.
    """
    # Check for the rejection trigger
    if "REJECT" in document_id.upper():
        logger.info("Mock KYC: REJECTED (trigger word found) doc_id=%s", document_id)
        return KycResult(
            status="rejected",
            reference_id=None,
            reason="Name contains rejection trigger (mock).",
        )

    reference_id = f"MOCKKYC-{document_id}"
    logger.info("Mock KYC: APPROVED ref=%s", reference_id)
    return KycResult(
        status="approved",
        reference_id=reference_id,
    )
