from integrations.documents.mock_kyc import submit_to_mock_kyc


def test_mock_kyc_is_deterministic():
    assert submit_to_mock_kyc("doc-123").status == "approved"
    result = submit_to_mock_kyc("REJECT-doc")
    assert result.status == "rejected"
