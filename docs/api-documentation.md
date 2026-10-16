# HubSpot Deals ETL: Service API Documentation

**Project:** `hubspot-deals-etl` | **Service:** `hubspot_deals` | **Version:** 1.0.0 | **Last updated:** 2026-10-16

This document describes the REST API exposed by the service. Interactive documentation (Swagger UI) is served by the running service at `/docs`. The upstream HubSpot CRM API that the service calls is described in [`api-integration.md`](api-integration.md), and the stored data in [`database-schema.md`](database-schema.md).

## 1. Overview

| Item | Value |
|------|-------|
| Base path | `/api` |
| Development | `http://localhost:5200` |
| Staging | port `5201` |
| Production | port `5202` |
| Swagger UI | `http://localhost:5200/docs` (HTTP 200) |
| Content type | `application/json` |

All endpoints below are relative to `/api`, so the health check is `http://localhost:5200/api/health`. A request without the prefix (for example `/health`) returns 404.

## 2. Authentication

**Calls to this service.** In the development setup, no credentials are required on requests to the service itself (the examples below are made without an `Authorization` header).

**HubSpot access token.** The caller supplies the HubSpot private app access token (scope `crm.objects.deals.read`) in the scan request at `config.auth.accessToken`. The service uses it to call HubSpot with `Authorization: Bearer <token>`. The token is stored encrypted, and the status endpoint returns it only in encrypted form. It must never be committed to source control or logged. In all examples it is shown as `<YOUR_TOKEN>`.

## 3. Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Service and database health |
| GET | `/api/stats` | Service statistics |
| POST | `/api/scan/start` | Start a deals extraction scan |
| GET | `/api/scan/{scan_id}/status` | Scan status, record count and checkpoint info |
| GET | `/api/pipeline/info` | DLT pipeline information |
| GET | `/api/results/...` | Extracted results for a scan (`results` group in Swagger) |
| ... | `/api/scan/...`, `/api/maintenance/...` | Additional scan control and maintenance operations (see Swagger UI) |

The exact paths and parameters of every endpoint are listed in the Swagger UI at `/docs`.

### 3.1 `GET /api/health`

```
curl http://localhost:5200/api/health
```

```json
{
    "status": "healthy",
    "timestamp": "2026-10-16T09:10:08.114688",
    "service": "hubspot_deals_pipeline_dev",
    "pipeline": {
        "pipeline_name": "hubspot_deals_extraction",
        "destination_type": "postgres",
        "source_type": "hubspot_deals",
        "database_health": {
            "healthy": true,
            "timestamp": 1792141808.0933955,
            "database": "hubspot_deals_data_dev",
            "host": "postgres_dev"
        },
        "supports_checkpoints": true
    }
}
```

### 3.2 `GET /api/pipeline/info`

```
curl http://localhost:5200/api/pipeline/info
```

```json
{
    "success": true,
    "data": {
        "pipeline_name": "hubspot_deals_extraction",
        "destination_type": "postgres",
        "source_type": "hubspot_deals",
        "database_health": {
            "healthy": true,
            "timestamp": 1792141827.0995555,
            "database": "hubspot_deals_data_dev",
            "host": "postgres_dev"
        },
        "supports_checkpoints": true
    }
}
```

### 3.3 `POST /api/scan/start`

Starts an extraction in the background and returns immediately.

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `config.scanId` | string | yes | Unique scan identifier chosen by the caller. A scan ID that already exists is rejected. |
| `config.organizationId` | string | yes | Tenant / organization identifier. Results are loaded into the schema `hubspot_users_<organizationId with - replaced by _>`. |
| `config.type` | string array | yes | Scan type. Use `["user"]`. |
| `config.auth.accessToken` | string | yes | HubSpot private app access token. |
| `config.filters` | object | no | Optional filters, for example `{"includeArchived": false}`. |

**Example request**

```json
{
  "config": {
    "scanId": "hubspot-deals-day7",
    "organizationId": "org-12345",
    "type": ["user"],
    "auth": { "accessToken": "<YOUR_TOKEN>" },
    "filters": {}
  }
}
```

```
curl -X POST http://localhost:5200/api/scan/start -H "Content-Type: application/json" -d @scan-request.json
```

**Success response**

```json
{
  "success": true,
  "message": "Scan initialization accepted and is now processing in the background."
}
```

**Error response: duplicate scan ID**

```json
{
    "success": false,
    "message": "A scan with ID 'hubspot-deals-day7' already exists",
    "error": "A scan with ID 'hubspot-deals-day7' already exists"
}
```

### 3.4 `GET /api/scan/{scan_id}/status`

Returns the state of a scan. Poll it until `status` is `completed` or a failure state.

| Parameter | Location | Description |
|-----------|----------|-------------|
| `scan_id` | path | The `scanId` used when the scan was started |

```
curl http://localhost:5200/api/scan/hubspot-deals-day7/status
```

```json
{
    "success": true,
    "data": {
        "scanId": "hubspot-deals-day7",
        "organizationId": "org-12345",
        "type": "user",
        "status": "completed",
        "startTime": "2026-10-16T05:09:05.505335+00:00",
        "endTime": "2026-10-16T05:09:07.382148+00:00",
        "lastHeartbeat": "2026-10-16T05:09:06.871142+00:00",
        "recordsExtracted": 5,
        "errorMessage": null,
        "config": {
            "auth": "<encrypted>",
            "filters": { "includeArchived": false },
            "type": ["user"]
        },
        "metadata": {
            "pipeline_name": "hubspot_deals_extraction",
            "destination": "postgres",
            "dataset_name": "hubspot_users_org_12345",
            "source_type": "hubspot_deals",
            "extraction_summary": { "total_records": 5 },
            "completed_at": "2026-10-16T05:09:07.326694+00:00"
        },
        "duration": 1.876813,
        "checkpointInfo": {
            "latestCheckpoint": {
                "id": 1,
                "job_id": "hubspot-deals-day7",
                "phase": "main_data_completed",
                "recordsProcessed": 5,
                "cursor": null,
                "pageNumber": 1,
                "batchSize": 100,
                "checkpoint_data": {
                    "completion_status": "success",
                    "total_pages": 1,
                    "final_total": 5,
                    "service": "hubspot_deals"
                }
            },
            "lastCheckpointAt": "2026-10-16T05:09:06.840016+00:00"
        }
    }
}
```

| Field | Description |
|-------|-------------|
| `status` | Current state of the scan (for example `completed`) |
| `recordsExtracted` | Number of deals loaded |
| `errorMessage` | Failure details, or `null` |
| `duration` | Run time in seconds |
| `metadata.dataset_name` | PostgreSQL schema the data was loaded into |
| `checkpointInfo` | Latest saved checkpoint (phase, page number, cursor, records processed) |

### 3.5 Where the extracted data is stored

Deals are loaded into PostgreSQL table `<dataset_name>.hubspot_deals` (for example `hubspot_users_org_12345.hubspot_deals`). Each record contains the deal fields (`id`, `dealname`, `amount`, `dealstage`, `pipeline`, `closedate`, `createdate`, `hs_lastmodifieddate`, `hs_object_id`) plus ETL metadata (`_extracted_at`, `_scan_id`, `_organization_id`, `_page_number`, `_source_service`). See [`database-schema.md`](database-schema.md).

## 4. Errors and status codes

Service errors use a JSON body with `success: false`, a `message`, and an `error` description:

```json
{
    "success": false,
    "message": "A scan with ID 'hubspot-deals-day7' already exists",
    "error": "A scan with ID 'hubspot-deals-day7' already exists"
}
```

| HTTP status | Meaning |
|-------------|---------|
| `200` | Request succeeded (health, status, pipeline info, Swagger UI) |
| `404` | Unknown route (for example a path without the `/api` prefix) |

### Errors from HubSpot during a scan

The service handles these upstream errors and records the failure in the scan's `errorMessage`:

| HubSpot response | Cause | Behaviour |
|------------------|-------|-----------|
| `401 Unauthorized` | Missing, invalid or expired token | Not retried; the scan fails with an authentication error |
| `403 Forbidden` | Token lacks the `crm.objects.deals.read` scope | Not retried; the scan fails |
| `429 Too Many Requests` | Rate limit reached (HubSpot allows 150 requests per 10 seconds) | Retried with backoff; the scan fails if retries are exhausted |
| `5xx` | Temporary HubSpot failure | Retried; the scan fails if retries are exhausted |
| Timeout | No response in time | Retried, then the scan fails |

These behaviours are covered by the automated tests in `test_hubspot_api_service.py`.

## 5. Example workflow

```
# 1. Start the extraction
curl -X POST http://localhost:5200/api/scan/start -H "Content-Type: application/json" -d @scan-request.json

# 2. Check the status until it is completed
curl http://localhost:5200/api/scan/hubspot-deals-day7/status

# 3. Verify the stored deals
docker exec -it hubspot_deals_postgres_dev psql -U postgres -d hubspot_deals_data_dev
SELECT dealname, amount, dealstage FROM hubspot_users_org_12345.hubspot_deals;
```

## 6. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-10-16 | Documented the running service: `/api` base path, start/status/health/pipeline endpoints, real request and response examples, error handling |