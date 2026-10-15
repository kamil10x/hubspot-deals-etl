import unittest
from unittest.mock import Mock, patch

from services.hubspot_api_service import (
    HubSpotAPIService,
    HubSpotAPIError,
)


class TestHubSpotAPIService(unittest.TestCase):

    def setUp(self):
        self.service = HubSpotAPIService(
            access_token="test-token",
            rate_limit=150,
            rate_limit_window=10,
            max_retries=1,
        )

    def tearDown(self):
        self.service.close()

    @patch("services.hubspot_api_service.time.sleep")
    def test_rate_limit_retry(self, mock_sleep):
        first_response = Mock()
        first_response.status_code = 429
        first_response.headers = {"Retry-After": "0"}
        first_response.raise_for_status.return_value = None

        second_response = Mock()
        second_response.status_code = 200
        second_response.json.return_value = {"results": []}

        with patch.object(
            self.service.session,
            "get",
            side_effect=[first_response, second_response],
        ) as mock_get:
            result = self.service._request(
                "/crm/v3/objects/deals"
            )

        self.assertEqual(result, {"results": []})
        self.assertEqual(mock_get.call_count, 2)

    @patch("services.hubspot_api_service.time.sleep")
    def test_timeout_retries_then_fails(self, mock_sleep):
        import requests

        with patch.object(
            self.service.session,
            "get",
            side_effect=requests.exceptions.Timeout,
        ) as mock_get:
            with self.assertRaises(HubSpotAPIError):
                self.service._request(
                    "/crm/v3/objects/deals"
                )

        self.assertEqual(mock_get.call_count, 2)

    def test_missing_token_is_rejected(self):
        service = HubSpotAPIService(access_token="")

        try:
            with self.assertRaises(HubSpotAPIError):
                service._request("/crm/v3/objects/deals")
        finally:
            service.close()


    def test_401_invalid_token(self):
        response = Mock()
        response.status_code = 401
        response.json.return_value = {
            "message": "Unauthorized",
            "correlationId": "test-id",
        }

        with patch.object(
            self.service.session, "get", return_value=response
        ):
            with self.assertRaisesRegex(
                HubSpotAPIError, "HTTP 401"
            ):
                self.service._request("/crm/v3/objects/deals")

    def test_403_insufficient_scope(self):
        response = Mock()
        response.status_code = 403
        response.json.return_value = {
            "message": "Forbidden",
            "correlationId": "test-id",
        }

        with patch.object(
            self.service.session, "get", return_value=response
        ):
            with self.assertRaisesRegex(
                HubSpotAPIError, "HTTP 403"
            ):
                self.service._request("/crm/v3/objects/deals")

    @patch("services.hubspot_api_service.time.sleep")
    def test_500_server_error_after_retries(self, mock_sleep):
        response = Mock()
        response.status_code = 500
        response.json.return_value = {"message": "Server error"}

        with patch.object(
            self.service.session, "get", return_value=response
        ) as mock_get:
            with self.assertRaisesRegex(
                HubSpotAPIError, "HTTP 500"
            ):
                self.service._request("/crm/v3/objects/deals")

        self.assertEqual(mock_get.call_count, 2)

    @patch("services.hubspot_api_service.time.sleep")
    def test_429_rate_limit_after_retries(self, mock_sleep):
        response = Mock()
        response.status_code = 429
        response.headers = {"Retry-After": "0"}
        response.json.return_value = {"message": "Rate limited"}

        with patch.object(
            self.service.session, "get", return_value=response
        ) as mock_get:
            with self.assertRaises(HubSpotAPIError):
                self.service._request("/crm/v3/objects/deals")

        self.assertEqual(mock_get.call_count, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)