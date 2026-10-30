"""
Document pipeline – validates documents and submits to mock KYC.
"""

from integrations.documents.validate import validate_document
from integrations.documents.mock_kyc import submit_to_mock_kyc

__all__ = ["validate_document", "submit_to_mock_kyc"]
