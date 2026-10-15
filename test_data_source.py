
from datetime import datetime

from services.data_source import transform_hubspot_deal


def test_transform_hubspot_deal():
    record = {
        "id": "12345",
        "properties": {
            "dealname": "Test Deal",
            "amount": "25000",
            "dealstage": "qualifiedtobuy",
            "createdate": "2026-10-14T10:00:00Z",
            "closedate": "1791936000000",
        },
    }

    result = transform_hubspot_deal(record)

    assert result["id"] == "12345"
    assert result["dealname"] == "Test Deal"
    assert result["amount"] == 25000.0
    assert result["dealstage"] == "qualifiedtobuy"
    assert result["createdate"].startswith("2026-10-14T10:00:00")
    assert result["closedate"].endswith("+00:00")


def test_transform_invalid_amount():
    record = {
        "id": "67890",
        "properties": {
            "dealname": "Invalid Amount Deal",
            "amount": "not-a-number",
        },
    }

    result = transform_hubspot_deal(record)

    assert result["id"] == "67890"
    assert result["amount"] is None


def test_transform_missing_properties():
    record = {"id": "11111"}

    result = transform_hubspot_deal(record)

    assert result["id"] == "11111"


def test_hubspot_deals_pagination(monkeypatch):
    from services import data_source

    calls = []

    class FakeHubSpotAPIService:
        def __init__(self, access_token):
            pass

        def get_deals_page(self, limit, after=None, properties=None):
            calls.append(after)

            if after is None:
                return {
                    "results": [
                        {
                            "id": "101",
                            "properties": {"dealname": "Deal One"},
                        }
                    ],
                    "paging": {"next": {"after": "cursor-2"}},
                }

            return {
                "results": [
                    {
                        "id": "102",
                        "properties": {"dealname": "Deal Two"},
                    }
                ]
            }

    monkeypatch.setattr(
        data_source, "HubSpotAPIService", FakeHubSpotAPIService
    )

    source_functions = data_source.create_data_source(
        job_config={"organizationId": "test-org"},
        auth_config={"accessToken": "test-token"},
        filters={},
    )

    records = list(source_functions[0])

    assert calls == [None, "cursor-2"]
    assert [record["id"] for record in records] == ["101", "102"]
    assert [record["dealname"] for record in records] == [
        "Deal One",
        "Deal Two",
    ]


def test_checkpoint_saved_every_10_pages(monkeypatch):
    from services import data_source

    class FakeHubSpotAPIService:
        def __init__(self, access_token):
            pass

        def get_deals_page(self, limit, after=None, properties=None):
            page = int(after) if after else 1

            response = {
                "results": [
                    {
                        "id": str(page),
                        "properties": {"dealname": f"Deal {page}"},
                    }
                ]
            }

            if page < 11:
                response["paging"] = {"next": {"after": str(page + 1)}}

            return response

    monkeypatch.setattr(
        data_source, "HubSpotAPIService", FakeHubSpotAPIService
    )

    checkpoints = []

    source_functions = data_source.create_data_source(
        job_config={"organizationId": "test-org"},
        auth_config={"accessToken": "test-token"},
        filters={"scan_id": "test-scan"},
        checkpoint_callback=lambda job_id, checkpoint: checkpoints.append(
            checkpoint
        ),
    )

    records = list(source_functions[0])

    periodic_checkpoints = [
        checkpoint
        for checkpoint in checkpoints
        if checkpoint.get("phase") == "main_data"
    ]

    assert len(records) == 11
    assert len(periodic_checkpoints) == 1
    assert periodic_checkpoints[0]["page_number"] == 10
    assert periodic_checkpoints[0]["records_processed"] == 10



def test_resume_from_saved_cursor(monkeypatch):
    from services import data_source

    calls = []

    class FakeHubSpotAPIService:
        def __init__(self, access_token):
            pass

        def get_deals_page(self, limit, after=None, properties=None):
            calls.append(after)
            return {
                "results": [
                    {
                        "id": "201",
                        "properties": {"dealname": "Resumed Deal"},
                    }
                ]
            }

    monkeypatch.setattr(
        data_source, "HubSpotAPIService", FakeHubSpotAPIService
    )

    source_functions = data_source.create_data_source(
        job_config={"organizationId": "test-org"},
        auth_config={"accessToken": "test-token"},
        filters={},
        resume_from={
            "cursor": "saved-cursor",
            "page_number": 5,
            "records_processed": 500,
        },
    )

    records = list(source_functions[0])

    assert calls == ["saved-cursor"]
    assert len(records) == 1
    assert records[0]["id"] == "201"
    assert records[0]["_page_number"] == 6
