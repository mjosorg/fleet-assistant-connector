import requests
import logging
from typing import Optional
from helper_backup import _auth_headers, SUPERVISOR_BASE_URL

logger = logging.getLogger(__name__)


def get_available_updates() -> list:
    """Returns list of available updates from the Supervisor API."""
    response = requests.get(
        f"{SUPERVISOR_BASE_URL}/available_updates",
        headers=_auth_headers(),
        timeout=10
    )
    response.raise_for_status()
    return response.json().get("data", {}).get("available_updates", [])


# The Supervisor blocks on update calls until the operation completes, which can
# take several minutes on slow hardware. Use a generous timeout for all of them.
_UPDATE_TIMEOUT = 600  # 10 minutes


def update_core(version: Optional[str] = None) -> None:
    """Triggers a Home Assistant Core update."""
    payload = {"version": version} if version else {}
    response = requests.post(
        f"{SUPERVISOR_BASE_URL}/core/update",
        headers=_auth_headers(content_type=bool(payload)),
        json=payload or None,
        timeout=_UPDATE_TIMEOUT,
    )
    response.raise_for_status()


def update_os(version: Optional[str] = None) -> None:
    """Triggers a Home Assistant OS update."""
    payload = {"version": version} if version else {}
    response = requests.post(
        f"{SUPERVISOR_BASE_URL}/os/update",
        headers=_auth_headers(content_type=bool(payload)),
        json=payload or None,
        timeout=_UPDATE_TIMEOUT,
    )
    response.raise_for_status()


def update_supervisor(version: Optional[str] = None) -> None:
    """Triggers a Supervisor update.

    The Supervisor kills its own process during the update, so the HTTP
    connection will die before a response is received. Treat ReadTimeout
    and ConnectionError as expected success rather than failures.
    """
    payload = {"version": version} if version else {}
    try:
        response = requests.post(
            f"{SUPERVISOR_BASE_URL}/supervisor/update",
            headers=_auth_headers(content_type=bool(payload)),
            json=payload or None,
            timeout=_UPDATE_TIMEOUT,
        )
        response.raise_for_status()
    except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
        # Supervisor restarted itself — connection drop is expected, not an error.
        logger.info("Supervisor update triggered; connection closed (Supervisor restarted)")


def update_addon(slug: str) -> None:
    """Triggers an update for a specific add-on."""
    response = requests.post(
        f"{SUPERVISOR_BASE_URL}/addons/{slug}/update",
        headers=_auth_headers(),
        timeout=_UPDATE_TIMEOUT,
    )
    response.raise_for_status()
