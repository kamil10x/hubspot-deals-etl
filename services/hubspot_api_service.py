"""HubSpot CRM Deals API service."""

import logging
import os
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional

import requests

from config import Config


logger = logging.getLogger(__name__)



ERROR_HINTS = {
    400: "Bad request. Check property names and parameters.",
    401: "Invalid or expired access token.",
    403: "Token is missing the crm.objects.deals.read scope.",
    404: "Endpoint or object not found.",
    429: "Rate limit exceeded. Retry after the specified delay.",
}



class HubSpotAPIError(Exception):
    """Raised when a HubSpot API request fails."""


class HubSpotAPIService:
    """Authenticate with HubSpot and retrieve CRM deals."""

    def __init__(
        self,
        access_token: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        rate_limit: Optional[int] = None,
        rate_limit_window: Optional[int] = None,
        max_retries: int = 3,
    ):
        
        if access_token is not None:
            self.access_token = access_token.strip()
        else:
            self.access_token = (
                getattr(Config, "HUBSPOT_ACCESS_TOKEN", "")
                or os.environ.get("HUBSPOT_ACCESS_TOKEN", "")
            ).strip()


        self.base_url = (
            base_url
            or getattr(Config, "HUBSPOT_API_BASE_URL", "https://api.hubapi.com")
        ).rstrip("/")

        self.timeout = float(
            timeout or getattr(Config, "HUBSPOT_API_TIMEOUT", 30)
        )
        self.rate_limit = int(
            rate_limit or getattr(Config, "HUBSPOT_API_RATE_LIMIT", 150)
        )
        self.rate_limit_window = float(
            rate_limit_window
            or getattr(Config, "HUBSPOT_RATE_LIMIT_WINDOW_SECONDS", 10)
        )
        self.max_retries = max_retries

        if self.timeout <= 0:
            raise ValueError("Timeout must be positive.")
        if self.rate_limit <= 0 or self.rate_limit_window <= 0:
            raise ValueError("Rate-limit settings must be positive.")

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "hubspot-deals-etl/1.0",
        })

        # Sliding-window limiter shared by this service instance.
        self._request_times = deque()
        self._rate_lock = threading.Lock()

        logger.info("HubSpot API service initialized")

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------
    def _wait_for_rate_limit(self) -> None:
        """Block until a request slot is free (150 requests / 10 seconds)."""
        while True:
            with self._rate_lock:
                now = time.monotonic()

                while (
                    self._request_times
                    and now - self._request_times[0] >= self.rate_limit_window
                ):
                    self._request_times.popleft()

                if len(self._request_times) < self.rate_limit:
                    self._request_times.append(now)
                    return

                wait_time = self.rate_limit_window - (
                    now - self._request_times[0]
                )

            logger.debug("Local rate limit reached; sleeping %.2fs", wait_time)
            time.sleep(max(wait_time, 0.01))

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------
    def _raise_http_error(self, response: requests.Response, endpoint: str) -> None:
        """Log HubSpot's error details and raise a descriptive error."""
        status = response.status_code

        try:
            body = response.json()
        except ValueError:
            body = {}
        if not isinstance(body, dict):
            body = {}

        logger.error(
            "HubSpot API request failed: status=%s endpoint=%s "
            "correlation_id=%s detail=%s",
            status,
            endpoint,
            body.get("correlationId"),
            body.get("message"),
        )

        if status in ERROR_HINTS:
            hint = ERROR_HINTS[status]
        elif 500 <= status < 600:
            hint = "HubSpot server error."
        else:
            hint = "Unexpected HubSpot API error."

        raise HubSpotAPIError(f"HubSpot API returned HTTP {status}: {hint}")

    # ------------------------------------------------------------------
    # Core request
    # ------------------------------------------------------------------
    def _request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a HubSpot API GET request with retry and error handling."""
        if not self.access_token:
            raise HubSpotAPIError(
                "HubSpot access token is missing. Configure "
                "HUBSPOT_ACCESS_TOKEN in your environment."
            )

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        for attempt in range(self.max_retries + 1):
            self._wait_for_rate_limit()

            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout,
                )

                # --- 429: respect Retry-After, then retry ---
                if response.status_code == 429:
                    if attempt >= self.max_retries:
                        raise HubSpotAPIError(
                            "HubSpot rate limit exceeded after retries."
                        )

                    retry_after = response.headers.get("Retry-After")
                    try:
                        delay = (
                            float(retry_after)
                            if retry_after
                            else min(2 ** attempt, 30)
                        )
                    except ValueError:
                        delay = min(2 ** attempt, 30)

                    logger.warning(
                        "HubSpot rate limit reached; retrying in %.1fs "
                        "(attempt %d/%d)",
                        delay, attempt + 1, self.max_retries,
                    )
                    time.sleep(max(delay, 0))
                    continue

                # --- 5xx: exponential backoff, then retry ---
                if 500 <= response.status_code < 600 and attempt < self.max_retries:
                    delay = min(2 ** attempt, 30)
                    logger.warning(
                        "HubSpot server error %d; retrying in %ds "
                        "(attempt %d/%d)",
                        response.status_code, delay,
                        attempt + 1, self.max_retries,
                    )
                    time.sleep(delay)
                    continue

                # --- Any remaining 4xx/5xx: fail with a clear message ---
                if response.status_code >= 400:
                    self._raise_http_error(response, endpoint)

                # --- Success ---
                try:
                    return response.json()
                except ValueError as exc:
                    raise HubSpotAPIError(
                        "HubSpot returned an invalid JSON response."
                    ) from exc

            except requests.exceptions.Timeout as exc:
                if attempt < self.max_retries:
                    delay = min(2 ** attempt, 30)
                    logger.warning(
                        "HubSpot request timed out; retrying in %ds "
                        "(attempt %d/%d)",
                        delay, attempt + 1, self.max_retries,
                    )
                    time.sleep(delay)
                    continue
                raise HubSpotAPIError(
                    "HubSpot request timed out after retries."
                ) from exc

            except requests.exceptions.RequestException as exc:
                if attempt < self.max_retries:
                    delay = min(2 ** attempt, 30)
                    logger.warning(
                        "HubSpot connection error (%s); retrying in %ds "
                        "(attempt %d/%d)",
                        exc.__class__.__name__, delay,
                        attempt + 1, self.max_retries,
                    )
                    time.sleep(delay)
                    continue
                raise HubSpotAPIError(
                    "Could not connect to the HubSpot API."
                ) from exc

        raise HubSpotAPIError("HubSpot request failed after retries.")

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------
    def validate_credentials(self) -> bool:
        """Check whether the token can access CRM deals."""
        if not self.access_token:
            logger.warning("HubSpot access token is not configured")
            return False

        try:
            self._request(
                "/crm/v3/objects/deals",
                params={"limit": 1, "properties": "dealname"},
            )
            logger.info("HubSpot credentials validated successfully")
            return True

        except HubSpotAPIError as exc:
            logger.warning("HubSpot credential validation failed: %s", exc)
            return False

    def get_deals(
        self,
        limit: int = 100,
        properties: Optional[List[str]] = None,
        max_deals: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch deals across all pages using HubSpot's `after` cursor."""
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100.")
        if max_deals is not None and max_deals < 0:
            raise ValueError("max_deals cannot be negative.")
        if max_deals == 0:
            return []

        endpoint = "/crm/v3/objects/deals"
        params: Dict[str, Any] = {"limit": limit}

        if properties:
            params["properties"] = ",".join(properties)

        deals: List[Dict[str, Any]] = []
        after: Optional[str] = None
        page_number = 0

        while True:
            if after:
                params["after"] = after
            else:
                params.pop("after", None)

            page = self._request(endpoint, params=params)
            results = page.get("results", [])
            deals.extend(results)
            page_number += 1

            logger.info(
                "Retrieved deals page %d: %d deals (total %d)",
                page_number, len(results), len(deals),
            )

            if max_deals is not None and len(deals) >= max_deals:
                return deals[:max_deals]

            next_page = page.get("paging", {}).get("next", {})
            after = next_page.get("after")

            if not after or not results:
                break

        logger.info("HubSpot deal retrieval completed: %d deals", len(deals))
        return deals

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self.session.close()