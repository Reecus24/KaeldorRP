"""P0 regression: admin auth must prefer Authorization Bearer header over stale access_token cookie.

Scenarios:
- Admin Bearer + stale player cookie => 200 on /api/admin/* (was 403 before fix)
- Player Bearer alone on admin route => 403 (admin gating not weakened)
- Cookie-only admin (no Authorization header) => 200 (cookie fallback still works)
"""
import os
import requests
import pytest

# load frontend .env so REACT_APP_BACKEND_URL is available when pytest is run standalone
try:
    from dotenv import load_dotenv
    load_dotenv("/app/frontend/.env")
except Exception:
    pass
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

ADMIN_EMAIL = "admin@kaeldor.com"
ADMIN_PASS = "admin123"
PLAYER_EMAIL = "shiftplayer@kaeldor.com"
PLAYER_PASS = "demo123"

ADMIN_ENDPOINTS = ["/api/admin/config", "/api/admin/stats", "/api/admin/players"]


def _login(email, password):
    # use a bare session so we get a clean cookie jar per login
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"no token in login response for {email}: {data}"
    # also grab the cookie the backend set
    cookie = s.cookies.get("access_token")
    assert cookie, f"backend did not set access_token cookie for {email}"
    return token, cookie, data.get("user") or {}


@pytest.fixture(scope="module")
def admin_creds():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def player_creds():
    return _login(PLAYER_EMAIL, PLAYER_PASS)


class TestAdminAuthStaleCookie:
    def test_admin_bearer_with_stale_player_cookie_returns_200(self, admin_creds, player_creds):
        """PRIMARY BUG FIX: admin bearer must win over a stale non-admin cookie."""
        admin_token, _, admin_user = admin_creds
        _, player_cookie, _ = player_creds
        assert admin_user.get("role") == "admin", f"seed admin has wrong role: {admin_user}"
        headers = {"Authorization": f"Bearer {admin_token}"}
        cookies = {"access_token": player_cookie}
        for ep in ADMIN_ENDPOINTS:
            r = requests.get(f"{BASE_URL}{ep}", headers=headers, cookies=cookies, timeout=20)
            assert r.status_code == 200, f"{ep} expected 200 with admin Bearer + stale player cookie, got {r.status_code}: {r.text[:300]}"
            # sanity: response must be JSON (not an error page)
            assert r.headers.get("content-type", "").startswith("application/json")

    def test_player_bearer_on_admin_route_is_403(self, player_creds):
        """Regression guard: non-admin bearer must NOT be allowed on admin routes."""
        player_token, _, _ = player_creds
        headers = {"Authorization": f"Bearer {player_token}"}
        r = requests.get(f"{BASE_URL}/api/admin/config", headers=headers, timeout=20)
        assert r.status_code == 403, f"player bearer must be 403 on /api/admin/config, got {r.status_code}: {r.text[:200]}"

    def test_cookie_only_admin_still_works(self, admin_creds):
        """Cookie fallback: no Authorization header, but admin cookie => 200."""
        _, admin_cookie, _ = admin_creds
        r = requests.get(f"{BASE_URL}/api/admin/config",
                         cookies={"access_token": admin_cookie}, timeout=20)
        assert r.status_code == 200, f"cookie-only admin expected 200, got {r.status_code}: {r.text[:200]}"

    def test_no_auth_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/admin/config", timeout=20)
        assert r.status_code == 401, f"unauthenticated should be 401, got {r.status_code}"

    def test_player_bearer_with_stale_admin_cookie_is_still_403(self, admin_creds, player_creds):
        """Mirror-check: bearer precedence works in both directions -- player bearer stays 403 even if an admin cookie is present."""
        _, admin_cookie, _ = admin_creds
        player_token, _, _ = player_creds
        headers = {"Authorization": f"Bearer {player_token}"}
        cookies = {"access_token": admin_cookie}
        r = requests.get(f"{BASE_URL}/api/admin/config", headers=headers, cookies=cookies, timeout=20)
        assert r.status_code == 403, f"player bearer with stale admin cookie must be 403, got {r.status_code}"
