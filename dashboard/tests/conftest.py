import os
import sys

# Make `server` importable when running pytest from dashboard/ (or from root).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Backend now validates bridge tokens strictly (fail-closed). Force a fixed
# test token so existing tests using `Bearer test-token` keep passing without
# depending on the developer's real env.
os.environ["QUANTAI_BRIDGE_TOKEN"] = "test-token"
os.environ["ATE_BRIDGE_TOKEN"] = "test-token"
os.environ["MT5_BRIDGE_TOKEN"] = "test-token"

# Admin credentials for login-related tests / endpoints.
os.environ["ADMIN_LOGIN"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin"
