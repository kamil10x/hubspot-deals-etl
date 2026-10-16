# Day 7 Test Results: HubSpot Deals ETL

**Task 3.4: Test and Validate** | Service: `hubspot-deals-etl` | Dev port: `5200`

> Secrets are never included in this repository. The HubSpot token appears only as `<YOUR_TOKEN>`, and the encrypted `config.auth` value returned by the status endpoint is shown as `<REDACTED>`.

## 1. Objective

Validate the HubSpot Deals extraction service by starting the Docker services, checking API health, monitoring a scan, verifying all 5 test deals, checking the PostgreSQL records, verifying checkpoint creation, and confirming the API documentation at `/docs`.

## 2. Summary of results

| Test | Result |
|------|--------|
| Docker services start | ✅ PASS |
| PostgreSQL health | ✅ PASS |
| Redis health | ✅ PASS |
| API health endpoint | ✅ PASS |
| Pipeline information | ✅ PASS |
| Scan completion | ✅ PASS |
| 5 / 5 deals extracted | ✅ PASS |
| PostgreSQL data verification | ✅ PASS |
| Extraction metadata verification | ✅ PASS |
| Checkpoint creation (`recordsProcessed = 5`) | ✅ PASS |
| Duplicate scan ID rejected | ✅ PASS |
| Swagger UI at `/docs` | ✅ PASS |
| Live interrupt-and-resume | ⚠️ NOT PERFORMED (see section 12) |
| Automated unit tests (13), incl. checkpoint save and resume-from-cursor | ✅ PASS (13 / 13, section 13) |

**Overall result: Day 7 testing and validation passed.** The service starts in Docker, passes API and database health checks, completes an extraction, stores all 5 test deals correctly in PostgreSQL, saves a checkpoint, and serves working Swagger documentation.

---

## 3. Docker services

```
docker compose up -d --build
docker compose ps
```

Fixes needed for the build to work:

- `cryptography` changed from `41.0.8` to `42.0.8`
- `python-dotenv==1.0.1` added to `requirements.txt`

```
NAME                         IMAGE                                                         COMMAND                  SERVICE                     STATUS                 PORTS
hubspot_deals_postgres_dev   postgres:15-alpine                                            "docker-entrypoint.s…"   postgres_dev                Up 5 hours (healthy)   0.0.0.0:5432->5432/tcp
hubspot_deals_redis          redis:7-alpine                                                "docker-entrypoint.s…"   redis                       Up 5 hours (healthy)   0.0.0.0:6379->6379/tcp
hubspot_deals_service_dev    hubspot_dealsdltextractionservice-hubspot_deals_service_dev   "python app.py"          hubspot_deals_service_dev   Up 5 hours (healthy)   0.0.0.0:5200->5200/tcp
```

All three containers are healthy. (Docker prints a warning that the `version` attribute in `docker-compose.yml` is obsolete; it is ignored and harmless.)

## 4. API health check

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

## 5. Pipeline information

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

## 6. API documentation (Swagger)

```
curl -I http://localhost:5200/docs
```

```
HTTP/1.1 200 OK
Server: Werkzeug/3.1.9 Python/3.11.17
Date: Fri, 16 Oct 2026 09:11:05 GMT
Content-Type: text/html; charset=utf-8
Content-Length: 3819
```

Swagger UI also loads in the browser at `http://localhost:5200/docs` (title `Hubspot_Deals 1.0.0`, base URL `/api`, groups: `scan`, `results`, `pipeline`, `maintenance`, plus `/health` and `/stats`).

## 7. Scan request and execution

A local `scan-request.json` was created in the project root (it is never committed):

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

Start the scan:

```
curl -X POST http://localhost:5200/api/scan/start -H "Content-Type: application/json" -d @scan-request.json
```

```json
{
  "success": true,
  "message": "Scan initialization accepted and is now processing in the background."
}
```

### Duplicate scan protection

Re-submitting the same `scanId` is rejected instead of re-running the extraction, so the completed scan was kept and used for validation:

```json
{
    "success": false,
    "message": "A scan with ID 'hubspot-deals-day7' already exists",
    "error": "A scan with ID 'hubspot-deals-day7' already exists"
}
```

### Scan status

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
            "auth": "<REDACTED>",
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
                "createdAt": "2026-10-16T05:09:06.840016+00:00",
                "phase": "main_data_completed",
                "recordsProcessed": 5,
                "totalEstimated": null,
                "cursor": null,
                "pageNumber": 1,
                "batchSize": 100,
                "lastProcessedId": null,
                "lastProcessedTimestamp": null,
                "checkpoint_data": {
                    "completion_status": "success",
                    "total_pages": 1,
                    "final_total": 5,
                    "service": "hubspot_deals"
                },
                "progress_percentage": null
            },
            "progress": null,
            "lastCheckpointAt": "2026-10-16T05:09:06.840016+00:00"
        }
    }
}
```

**Result: `status: completed`, `recordsExtracted: 5`, `errorMessage: null`, duration 1.88 s.**

## 8. Extracted test deals

```
docker exec -it hubspot_deals_postgres_dev psql -U postgres -d hubspot_deals_data_dev
```

All 5 expected HubSpot test deals were found in `hubspot_users_org_12345.hubspot_deals`:

| # | Deal | Amount | Stage | Close date | Deal ID |
|---|------|-------:|-------|------------|---------|
| 1 | Website Development | 5,000 | qualifiedtobuy | 2026-11-15 | 353410017998 |
| 2 | CRM Integration | 25,000 | presentationscheduled | 2026-11-30 | 353762832066 |
| 3 | Globex Annual Support Renewal | 50,000 | closedwon | 2026-10-05 | 353762832079 |
| 4 | Initech Enterprise Integration | 75,000 | closedlost | 2026-09-28 | 353525605104 |
| 5 | Umbrella Multi-Year Licensing | 100,000 | contractsent | 2027-01-20 | 353525605109 |

Every record carries the ETL metadata columns `_extracted_at`, `_scan_id` (`hubspot-deals-day7`), `_organization_id` (`org-12345`), `_page_number` (`1`) and `_source_service` (`hubspot_deals`), plus DLT's `_dlt_load_id` and `_dlt_id`.

<details>
<summary>Raw query output</summary>

```sql
SELECT * FROM hubspot_users_org_12345.hubspot_deals \gx
```

```
-[ RECORD 1 ]-------+-------------------------------
id                  | 353410017998
amount              | 5000
closedate           | 2026-11-15 07:29:52.446+00
createdate          | 2026-10-13 07:33:03.796+00
dealname            | Website Development
dealstage           | qualifiedtobuy
hs_lastmodifieddate | 2026-10-13 12:02:34.729+00
hs_object_id        | 353410017998
pipeline            | default
_extracted_at       | 2026-10-16 05:09:06.72374+00
_scan_id            | hubspot-deals-day7
_organization_id    | org-12345
_page_number        | 1
_source_service     | hubspot_deals
_dlt_load_id        | 1792127345.8473976
_dlt_id             | b39lEf8xGHNwrw
-[ RECORD 2 ]-------+-------------------------------
id                  | 353525605104
amount              | 75000
closedate           | 2026-09-28 07:41:43.11+00
createdate          | 2026-10-13 07:42:56.885+00
dealname            | Initech Enterprise Integration
dealstage           | closedlost
hs_lastmodifieddate | 2026-10-13 12:04:04.038+00
hs_object_id        | 353525605104
pipeline            | default
_extracted_at       | 2026-10-16 05:09:06.756246+00
_scan_id            | hubspot-deals-day7
_organization_id    | org-12345
_page_number        | 1
_source_service     | hubspot_deals
_dlt_load_id        | 1792127345.8473976
_dlt_id             | 9lpzad3588IiqQ
-[ RECORD 3 ]-------+-------------------------------
id                  | 353525605109
amount              | 100000
closedate           | 2027-01-20 07:43:51.542+00
createdate          | 2026-10-13 07:44:02.309+00
dealname            | Umbrella Multi-Year Licensing
dealstage           | contractsent
hs_lastmodifieddate | 2026-10-13 12:03:14.741+00
hs_object_id        | 353525605109
pipeline            | default
_extracted_at       | 2026-10-16 05:09:06.778482+00
_scan_id            | hubspot-deals-day7
_organization_id    | org-12345
_page_number        | 1
_source_service     | hubspot_deals
_dlt_load_id        | 1792127345.8473976
_dlt_id             | PQH2VXrCsiw3Vg
-[ RECORD 4 ]-------+-------------------------------
id                  | 353762832066
amount              | 25000
closedate           | 2026-11-30 07:38:00.088+00
createdate          | 2026-10-13 07:38:12.889+00
dealname            | CRM Integration
dealstage           | presentationscheduled
hs_lastmodifieddate | 2026-10-13 12:01:27.606+00
hs_object_id        | 353762832066
pipeline            | default
_extracted_at       | 2026-10-16 05:09:06.801966+00
_scan_id            | hubspot-deals-day7
_organization_id    | org-12345
_page_number        | 1
_source_service     | hubspot_deals
_dlt_load_id        | 1792127345.8473976
_dlt_id             | GmcTMSw8Dv2XXQ
-[ RECORD 5 ]-------+-------------------------------
id                  | 353762832079
amount              | 50000
closedate           | 2026-10-05 07:40:15.008+00
createdate          | 2026-10-13 07:40:47.768+00
dealname            | Globex Annual Support Renewal
dealstage           | closedwon
hs_lastmodifieddate | 2026-10-13 12:03:38.237+00
hs_object_id        | 353762832079
pipeline            | default
_extracted_at       | 2026-10-16 05:09:06.824843+00
_scan_id            | hubspot-deals-day7
_organization_id    | org-12345
_page_number        | 1
_source_service     | hubspot_deals
_dlt_load_id        | 1792127345.8473976
_dlt_id             | R/JDjk+FW+HvGg
```

</details>

## 9. Checkpoint verification

```sql
SELECT "job_id", "phase", "recordsProcessed", "pageNumber", "cursor"
FROM public.job_checkpoints
WHERE "job_id" = 'hubspot-deals-day7';
```

```
       job_id       |        phase        | recordsProcessed | pageNumber | cursor
--------------------+---------------------+------------------+------------+--------
 hubspot-deals-day7 | main_data_completed |                5 |          1 |
(1 row)
```

The scan status also confirmed `completion_status: success`, `total_pages: 1`, `final_total: 5`, `service: hubspot_deals`. The `job_checkpoints` columns are camelCase, so they must be quoted in SQL.

## 10. API route note

The configured API prefix is `/api`, not `/api/v1`. Endpoints used during validation:

```
/api/health
/api/pipeline/info
/api/scan/start
/api/scan/<scan_id>/status
```

Swagger documentation is served at `/docs`. The generated template documentation originally mentioned `/api/v1/...`; the project documentation in this repository uses `/api/...` to match the running service.

## 11. Final test summary

| Check | Evidence |
|-------|----------|
| Docker services healthy | Section 3 |
| `/api/health` | Section 4 |
| `/api/pipeline/info` | Section 5 |
| `/docs` returns 200 | Section 6 |
| Scan completed, 5 records, no errors | Section 7 |
| 5 deals in PostgreSQL | Section 8 |
| Checkpoint row saved | Section 9 |
| 13 / 13 unit tests pass | Section 13 |

## 12. Checkpoint / resume note

The live extraction finished on a single page (5 deals), so a real interrupt-and-resume was **not** performed in this run. Checkpoint saving and resuming from a saved cursor are verified by these automated tests, which pass (section 13):

```
test_checkpoint_saved_every_10_pages
test_resume_from_saved_cursor
```

This document records a successful live checkpoint (section 9) but does not claim that a live interruption test was carried out.

## 13. Automated unit tests

```
python -m pytest -v
```

```
collected 13 items

test_data_source.py::test_transform_hubspot_deal PASSED                         [  7%]
test_data_source.py::test_transform_invalid_amount PASSED                       [ 15%]
test_data_source.py::test_transform_missing_properties PASSED                   [ 23%]
test_data_source.py::test_hubspot_deals_pagination PASSED                       [ 30%]
test_data_source.py::test_checkpoint_saved_every_10_pages PASSED                [ 38%]
test_data_source.py::test_resume_from_saved_cursor PASSED                       [ 46%]
test_hubspot_api_service.py::TestHubSpotAPIService::test_401_invalid_token PASSED                [ 53%]
test_hubspot_api_service.py::TestHubSpotAPIService::test_403_insufficient_scope PASSED           [ 61%]
test_hubspot_api_service.py::TestHubSpotAPIService::test_429_rate_limit_after_retries PASSED     [ 69%]
test_hubspot_api_service.py::TestHubSpotAPIService::test_500_server_error_after_retries PASSED   [ 76%]
test_hubspot_api_service.py::TestHubSpotAPIService::test_missing_token_is_rejected PASSED        [ 84%]
test_hubspot_api_service.py::TestHubSpotAPIService::test_rate_limit_retry PASSED                 [ 92%]
test_hubspot_api_service.py::TestHubSpotAPIService::test_timeout_retries_then_fails PASSED       [100%]

13 passed in 17.44s
```

**Result: 13 / 13 tests pass.** They cover deal transformation (valid, invalid amount, missing properties), cursor pagination, checkpoint saving every 10 pages, resuming from a saved cursor, and the API service's handling of 401, 403, 429 (rate limit with retries), 500 and timeout errors, plus rejection of a missing token.

## 14. Earlier validation (Day 5, API service)

- All 5 deal IDs returned by `get_deals()`
- Pagination with `limit=1` returned all 5 deals across 5 pages
- Invalid token returned a handled 401 error

## 15. Security notes

- The real HubSpot access token is not stored anywhere in this repository.
- `scan-request.json` contains the token, stays local, and is listed in `.gitignore`.
- The temporary `swagger.json` used for API inspection is not committed.