import os
import pytest


@pytest.fixture(autouse=True)
def configure_test_osint_mock():
    """
    Säkerställer att automatiserade enhetstester körs med MOCK_OSINT=true
    för snabb, deterministisk och nätverksoberoende exekvering.
    """
    old_val = os.environ.get("MOCK_OSINT")
    os.environ["MOCK_OSINT"] = "true"
    yield
    if old_val is not None:
        os.environ["MOCK_OSINT"] = old_val
    else:
        os.environ.pop("MOCK_OSINT", None)
