import requests
import logging
from helper_backup import _auth_headers, SUPERVISOR_BASE_URL

logger = logging.getLogger(__name__)


def check_update_available():
    try:
        response = requests.get(
            f"{SUPERVISOR_BASE_URL}/available_updates",
            headers=_auth_headers(),
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        if data.get("result") == "ok":
            return data["data"]
        return {"error": "Unexpected result from Supervisor"}
    except requests.exceptions.HTTPError as err:
        return {"error": f"HTTP error: {err.response.status_code}"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Problem occurred: {str(e)}"}


def get_fleet_assistant_version():
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
