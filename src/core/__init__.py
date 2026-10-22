import sys
from app import core as app_core

sys.modules["src.core"] = app_core
sys.modules["src.core.plugins"] = sys.modules.get("app.core.plugins")
sys.modules["src.core.finops"] = sys.modules.get("app.core.finops")
sys.modules["src.core.net"] = sys.modules.get("app.core.net")
sys.modules["src.core.reporting"] = sys.modules.get("app.core.reporting")
