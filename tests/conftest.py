"""Global test defaults.

Legacy SaaS tests exercise public registration flows, so they run with
PRIVATE_ADMIN_MODE off. tests/test_private_admin.py overrides these per-test
to verify the fail-closed private mode.
"""
import os

os.environ.setdefault("PRIVATE_ADMIN_MODE", "false")
os.environ.setdefault("ADMIN_ALLOWLIST_EMAILS", "")


def pytest_runtest_setup(item):
    # test_private_admin manages its own env; every other test file gets
    # public-mode defaults even if a prior test mutated the env.
    if "test_private_admin" not in str(item.fspath):
        os.environ["PRIVATE_ADMIN_MODE"] = "false"
        os.environ["ADMIN_ALLOWLIST_EMAILS"] = ""
