import pytest

from integrations.phone import mask, normalize


@pytest.mark.parametrize("value", ["98765 43210", "+91 98765-43210", "919876543210", "09876543210"])
def test_normalize(value):
    assert normalize(value) == "+919876543210"


def test_mask_never_returns_full_number():
    masked = mask("+919876543210")
    assert masked == "+91 98xxx xx210"
    assert "9876543210" not in masked


def test_bad_number_rejected():
    with pytest.raises(ValueError):
        normalize("not a phone")
