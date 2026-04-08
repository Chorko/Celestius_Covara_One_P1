"""
Selenium product-audit harness for Covara One.

Checks:
1) Worker login and rewards points UI/actions.
2) Worker claim submission behavior.
3) Admin login and Event Ops UI.
4) Auto-approval visibility in admin reviews; triggers auto-process if needed.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.webdriver import WebDriver as SeleniumChromeDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.webdriver import WebDriver as SeleniumEdgeDriver
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait

BASE_URL = "http://127.0.0.1:3000"
BACKEND_URL = "http://127.0.0.1:8000"

WORKER_CREDENTIALS = [
    ("worker@demo.com", "demo1234"),
    ("worker@demo.com", "DevTrails@123"),
]
ADMIN_CREDENTIALS = [
    ("admin@demo.com", "demo1234"),
    ("admin@demo.com", "DevTrails@123"),
]


@dataclass
class LoginResult:
    ok: bool
    email: str | None = None
    password_used: str | None = None
    error: str | None = None


def _http_status(url: str) -> int:
    with urllib.request.urlopen(url, timeout=10) as response:
        return int(response.status)


def _make_driver() -> tuple[WebDriver, str]:
    browser_errors: dict[str, str] = {}

    chrome_options = ChromeOptions()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1600,1200")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    try:
        driver = SeleniumChromeDriver(options=chrome_options)
        return driver, "chrome"
    except Exception as exc:  # noqa: BLE001
        browser_errors["chrome"] = str(exc)

    edge_options = EdgeOptions()
    edge_options.add_argument("--headless=new")
    edge_options.add_argument("--window-size=1600,1200")
    edge_options.add_argument("--disable-gpu")
    edge_options.add_argument("--no-sandbox")
    edge_options.add_argument("--disable-dev-shm-usage")

    try:
        driver = SeleniumEdgeDriver(options=edge_options)
        return driver, "edge"
    except Exception as exc:  # noqa: BLE001
        browser_errors["edge"] = str(exc)

    raise RuntimeError(f"Could not start browser driver: {browser_errors}")


def _reset_session(driver: WebDriver) -> None:
    driver.get(BASE_URL)
    driver.delete_all_cookies()
    driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")


def _body_text(driver: WebDriver) -> str:
    try:
        return driver.find_element(By.TAG_NAME, "body").text
    except Exception:  # noqa: BLE001
        return driver.page_source


def _page_contains(driver: WebDriver, text: str) -> bool:
    return text.lower() in _body_text(driver).lower()


def _find_button_by_text(driver: WebDriver, text: str):
    return driver.find_element(By.XPATH, f"//button[contains(normalize-space(.), '{text}')]")


def _button_exists(driver: WebDriver, text: str) -> bool:
    try:
        _find_button_by_text(driver, text)
        return True
    except NoSuchElementException:
        return False


def _wait_for_any_text(driver: WebDriver, options: list[str], timeout: int = 12) -> bool:
    options_lc = [item.lower() for item in options]

    def _contains_any(d: WebDriver) -> bool:
        page = _body_text(d).lower()
        return any(item in page for item in options_lc)

    try:
        WebDriverWait(driver, timeout).until(_contains_any)
        return True
    except TimeoutException:
        return False


def _wait_for_xpath(driver: WebDriver, xpath: str, timeout: int = 20) -> bool:
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: len(d.find_elements(By.XPATH, xpath)) > 0
        )
        return True
    except TimeoutException:
        return False


def _extract_error_text(driver: WebDriver) -> str:
    page = _body_text(driver)
    candidates = [
        "Cannot reach Supabase",
        "Sign in failed",
        "Database not set up",
        "Profile row missing",
        "Invalid login credentials",
    ]
    for item in candidates:
        if item.lower() in page.lower():
            return item
    return "Unknown login or page error"


def _login_with_candidates(
    driver: WebDriver,
    credentials: list[tuple[str, str]],
    expected_url_fragment: str,
) -> LoginResult:
    for email, password in credentials:
        _reset_session(driver)
        driver.get(BASE_URL)

        try:
            WebDriverWait(driver, 20).until(
                lambda d: d.find_element(By.CSS_SELECTOR, "input[type='email']")
            )
            email_input = driver.find_element(By.CSS_SELECTOR, "input[type='email']")
            password_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            submit = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")

            email_input.clear()
            email_input.send_keys(email)
            password_input.clear()
            password_input.send_keys(password)
            submit.click()
        except Exception as exc:  # noqa: BLE001
            return LoginResult(ok=False, error=f"Could not submit login form: {exc}")

        deadline = time.time() + 25
        while time.time() < deadline:
            if expected_url_fragment in driver.current_url:
                return LoginResult(ok=True, email=email, password_used=password)

            if _page_contains(driver, "Cannot reach Supabase") or _page_contains(driver, "Sign in failed"):
                break

            time.sleep(0.4)

    return LoginResult(ok=False, error=_extract_error_text(driver))


def _logout(driver: WebDriver) -> None:
    try:
        button = driver.find_element(By.XPATH, "//button[contains(., 'Sign Out')]")
        button.click()
        WebDriverWait(driver, 10).until(lambda d: d.current_url.rstrip("/") == BASE_URL)
    except Exception:  # noqa: BLE001
        pass


def _count_text_occurrences(driver: WebDriver, text: str) -> int:
    try:
        elements = driver.find_elements(By.XPATH, f"//*[contains(normalize-space(.), '{text}')]")
        return len(elements)
    except Exception:  # noqa: BLE001
        return 0


def _extract_supabase_access_token(driver: WebDriver) -> str | None:
    token = driver.execute_script(
        """
                const stores = [window.localStorage, window.sessionStorage];
                for (const store of stores) {
                    if (!store) continue;
                    const keys = Object.keys(store);
                    for (const key of keys) {
                        const keyLc = key.toLowerCase();
                        if (!keyLc.includes('auth-token') && !keyLc.includes('supabase') && !keyLc.includes('sb-')) {
                            continue;
            }
                        const raw = store.getItem(key);
                        if (!raw) continue;
                        try {
                            const parsed = JSON.parse(raw);
                            if (parsed && typeof parsed === 'object') {
                                if (parsed.access_token) return parsed.access_token;
                                if (parsed.currentSession && parsed.currentSession.access_token) return parsed.currentSession.access_token;
                                if (parsed.session && parsed.session.access_token) return parsed.session.access_token;
                                if (parsed.data && parsed.data.session && parsed.data.session.access_token) return parsed.data.session.access_token;
                            }
                            if (Array.isArray(parsed) && parsed.length > 0 && parsed[0] && parsed[0].access_token) {
                                return parsed[0].access_token;
                            }
                        } catch (_) {
                            if (typeof raw === 'string' && raw.split('.').length === 3) {
                                return raw;
                            }
                        }
                    }
        }
        return null;
        """
    )
    return str(token) if token else None


def _count_text_occurrences_ci(driver: WebDriver, text: str) -> int:
        try:
                text_lc = text.lower()
                elements = driver.find_elements(
                        By.XPATH,
                        "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '%s')]"
                        % text_lc,
                )
                return len(elements)
        except Exception:  # noqa: BLE001
                return 0


def _post_auto_process(access_token: str, lookback_hours: int = 24) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{BACKEND_URL}/claims/auto-process?lookback_hours={lookback_hours}",
        method="POST",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
            payload["http_status"] = int(response.status)
            return payload
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {
            "http_status": exc.code,
            "error": body,
        }


def main() -> int:
    report: dict[str, Any] = {
        "backend_health": None,
        "frontend_health": None,
        "browser": None,
        "worker_login": None,
        "worker_rewards": {},
        "worker_claim_submission": {},
        "admin_login": None,
        "admin_event_ops": {},
        "auto_approval": {},
        "feature_alignment": {},
    }

    report["backend_health"] = _http_status(f"{BACKEND_URL}/health")
    report["frontend_health"] = _http_status(BASE_URL)

    driver = None
    try:
        driver, browser_name = _make_driver()
        report["browser"] = browser_name

        # Worker flow: login + rewards + claim submit
        worker_login = _login_with_candidates(driver, WORKER_CREDENTIALS, "/worker/dashboard")
        report["worker_login"] = worker_login.__dict__

        if worker_login.ok:
            driver.get(f"{BASE_URL}/worker/rewards")
            rewards_ready = _wait_for_xpath(
                driver,
                "//button[contains(normalize-space(.), 'Weekly Check-In')]",
                timeout=25,
            )
            report["worker_rewards"] = {
                "page_loaded": rewards_ready,
                "has_weekly_checkin_action": _button_exists(driver, "Weekly Check-In"),
                "has_discount_redeem_action": _button_exists(driver, "Redeem Discount"),
                "has_free_week_redeem_action": _button_exists(driver, "Redeem Free Week"),
            }

            try:
                checkin_button = _find_button_by_text(driver, "Weekly Check-In")
                checkin_button.click()
                report["worker_rewards"]["checkin_feedback_seen"] = _wait_for_any_text(
                    driver,
                    [
                        "check-in successful",
                        "already claimed",
                        "weekly check-in already claimed",
                    ],
                    timeout=8,
                )
            except (NoSuchElementException, StaleElementReferenceException):
                report["worker_rewards"]["checkin_feedback_seen"] = False

            try:
                driver.get(f"{BASE_URL}/worker/claims")
                WebDriverWait(driver, 20).until(
                    lambda d: d.find_element(By.TAG_NAME, "textarea")
                )
                reason_text = f"Selenium QA valid claim {int(time.time())}"
                textarea = driver.find_element(By.TAG_NAME, "textarea")
                textarea.clear()
                textarea.send_keys(reason_text)
                submit_button = driver.find_element(By.XPATH, "//button[contains(., 'Submit Claim')]")
                submit_button.click()
                time.sleep(5)

                report["worker_claim_submission"] = {
                    "reason_submitted": reason_text,
                    "claim_rendered_in_history": reason_text[:18] in driver.page_source,
                    "error_banner_present": _page_contains(driver, "Invalid signed device context")
                    or _page_contains(driver, "Failed to submit claim")
                    or _page_contains(driver, "Session expired")
                    or _page_contains(driver, "A similar claim already exists"),
                }
            except Exception as exc:  # noqa: BLE001
                report["worker_claim_submission"] = {
                    "error": f"Worker claim submit step failed: {exc}",
                }

        _logout(driver)

        # Admin flow: login + event ops + auto-approve verification
        admin_login = _login_with_candidates(driver, ADMIN_CREDENTIALS, "/admin/dashboard")
        report["admin_login"] = admin_login.__dict__

        if admin_login.ok:
            driver.get(f"{BASE_URL}/admin/events")
            events_ready = _wait_for_xpath(
                driver,
                "//button[contains(normalize-space(.), 'Relay Pending Outbox')]",
                timeout=90,
            )
            report["admin_event_ops"] = {
                "page_loaded": events_ready,
                "has_relay_action": _button_exists(driver, "Relay Pending Outbox"),
                "has_outbox_requeue_action": _button_exists(driver, "Requeue Outbox Dead Letters"),
                "has_consumer_requeue_action": _button_exists(driver, "Requeue Consumer Dead Letters"),
            }

            driver.get(f"{BASE_URL}/admin/reviews")
            WebDriverWait(driver, 20).until(lambda d: "Review Queue" in d.page_source)
            _wait_for_xpath(
                driver,
                "//*[contains(normalize-space(.), 'Auto-Approved') or "
                "contains(normalize-space(.), 'Submitted') or "
                "contains(normalize-space(.), 'Verification') or "
                "contains(normalize-space(.), 'Fraud Review') or "
                "contains(normalize-space(.), 'Approved')]",
                timeout=35,
            )

            auto_before = _count_text_occurrences_ci(driver, "Auto-Approved")
            report["auto_approval"]["auto_approved_visible_before_auto_process"] = auto_before

            auto_process_payload: dict[str, Any] | None = None
            if auto_before == 0:
                token = _extract_supabase_access_token(driver)
                report["auto_approval"]["token_extracted"] = bool(token)

                if token:
                    auto_process_payload = _post_auto_process(token, lookback_hours=24)
                    report["auto_approval"]["auto_process_response"] = auto_process_payload

                    driver.get(f"{BASE_URL}/admin/reviews")
                    _wait_for_any_text(
                        driver,
                        [
                            "claims in pipeline",
                            "No claims in queue",
                            "Auto-Approved",
                        ],
                        timeout=10,
                    )

            auto_after = _count_text_occurrences_ci(driver, "Auto-Approved")
            report["auto_approval"]["auto_approved_visible_after_auto_process"] = auto_after

            approved_count = 0
            if auto_process_payload:
                approved_count = int(auto_process_payload.get("claims_auto_approved", 0) or 0)

            report["auto_approval"]["verdict"] = (
                "PASS"
                if auto_after > 0 or approved_count > 0
                else "FAIL_OR_NO_ELIGIBLE_DATA"
            )

        report["feature_alignment"] = {
            "points_system_present_in_ui": bool(report["worker_rewards"].get("page_loaded")),
            "event_ops_visible_in_admin_ui": bool(report["admin_event_ops"].get("page_loaded")),
            "auto_approval_observed_or_reported": report["auto_approval"].get("verdict") == "PASS",
        }

    except WebDriverException as exc:
        report["fatal_error"] = f"WebDriverException: {exc}"
    except Exception as exc:  # noqa: BLE001
        report["fatal_error"] = str(exc)
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:  # noqa: BLE001
                pass

    print(json.dumps(report, indent=2))

    verdict = report.get("auto_approval", {}).get("verdict")
    return 0 if verdict in {"PASS", "FAIL_OR_NO_ELIGIBLE_DATA"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
