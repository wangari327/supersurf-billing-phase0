from __future__ import annotations

from pathlib import Path

import pytest
from django.urls import reverse
from playwright.sync_api import Error as PlaywrightError

from audit.models import AuditEvent
from users.models import User


@pytest.mark.django_db
def test_login_logout_and_audit(client, readonly_user):
    response = client.post(
        reverse("login"),
        {"username": "readonly", "password": "StrongReadOnlyPass123!"},
        follow=True,
    )
    assert response.status_code == 200
    assert AuditEvent.objects.filter(action="login.success", actor=readonly_user).exists()

    response = client.post(reverse("logout"), follow=True)
    assert response.status_code == 200
    assert AuditEvent.objects.filter(action="logout", actor=readonly_user).exists()


@pytest.mark.django_db
def test_login_throttling_records_failed_attempts(client, settings):
    settings.AXES_FAILURE_LIMIT = 2
    User.objects.create_user(username="locked", password="StrongPass123!")
    for _ in range(2):
        client.post(reverse("login"), {"username": "locked", "password": "wrong"})
    assert AuditEvent.objects.filter(action="login.failed", target_identifier="locked").count() >= 2


@pytest.mark.django_db
def test_playwright_login_dashboard_smoke(live_server, seeded_roles):
    from playwright.sync_api import sync_playwright

    User.objects.create_user(username="browser-owner", password="StrongOwnerPass123!")
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except PlaywrightError:
            candidates = [
                Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
                Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
            ]
            executable = next((candidate for candidate in candidates if candidate.exists()), None)
            if executable is None:
                raise
            browser = playwright.chromium.launch(executable_path=str(executable))
        page = browser.new_page()
        page.goto(f"{live_server.url}{reverse('login')}")
        page.fill("#id_username", "browser-owner")
        page.fill("#id_password", "StrongOwnerPass123!")
        page.click("button[type='submit']")
        page.wait_for_url(f"{live_server.url}{reverse('dashboard')}")
        assert "SuperSurf Billing" in page.text_content("body")
        browser.close()
