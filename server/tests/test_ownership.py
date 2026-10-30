import pytest
from scripts.check_ownership import check_file_ownership, check_import_boundaries

def test_pl16_ownership_rules():
    # Platform owner checking legal platform paths
    assert check_file_ownership("platform") == True
    # Boundary import scan
    assert check_import_boundaries() == True

