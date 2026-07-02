"""Runtime dependency checks for configured network behavior."""

import pytest
from requests.exceptions import InvalidSchema


def test_requests_can_construct_socks_proxy_manager():
    """The app can run behind a SOCKS proxy when fetching paper feeds."""
    from requests.adapters import SOCKSProxyManager

    try:
        SOCKSProxyManager("socks5h://127.0.0.1:9")
    except InvalidSchema as exc:
        pytest.fail(f"requests SOCKS proxy support is not installed: {exc}")
