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


def update_core(version: Optional[str] = None) -> None:
    """Triggers a Home Assistant Core update."""
    payload = {"version": version} if version else {}
    response = requests.post(
        f"{SUPERVISOR_BASE_URL}/core/update",
        headers=_auth_headers(content_type=bool(payload)),
        json=payload or None,
        timeout=60
    )
    response.raise_for_status()


def update_os(version: Optional[str] = None) -> None:
    """Triggers a Home Assistant OS update."""
    payload = {"version": version} if version else {}
    response = requests.post(
        f"{SUPERVISOR_BASE_URL}/os/update",
        headers=_auth_headers(content_type=bool(payload)),
        json=payload or None,
        timeout=60
    )
    response.raise_for_status()


def update_supervisor(version: Optional[str] = None) -> None:
    """Triggers a Supervisor update."""
    payload = {"version": version} if version else {}
    response = requests.post(
        f"{SUPERVISOR_BASE_URL}/supervisor/update",
        headers=_auth_headers(content_type=bool(payload)),
        json=payload or None,
        timeout=60
    )
    response.raise_for_status()


def update_addon(slug: str) -> None:
    """Triggers an update for a specific add-on."""
    response = requests.post(
        f"{SUPERVISOR_BASE_URL}/addons/{slug}/update",
        headers=_auth_headers(),
        timeout=60
    )
    response.raise_for_status()


def get_fleet_assistant_version() -> Optional[str]:
    """Returns the current version of the add-on via Supervisor API."""
    try:
        response = requests.get(
            f"{SUPERVISOR_BASE_URL}/addons/self/info",
            headers=_auth_headers(),
            timeout=10
        )
        response.raise_for_status()
        return response.json().get("data", {}).get("version")
    except requests.exceptions.RequestException as e:
        logger.error("Unable to fetch version: %s", e)
        return None
