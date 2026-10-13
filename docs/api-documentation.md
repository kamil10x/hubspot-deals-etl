# HubSpot Deals ETL — Service API Documentation

**Project:** `hubspot-deals-etl`  
**Service:** `hubspot_deals`  
**Version:** 1.0.0 (documentation draft)  
**Last updated:** 2026-10-10

> **Implementation note:** This document adapts the supplied API documentation template for HubSpot deal extraction. Confirm every route, request field, response shape, status code, and download format against the routes/controllers in the generated service before treating it as an implemented contract. Remove any endpoint that is not present in the code. The HubSpot CRM API described below is the upstream API; it is separate from this service's own REST API.

## 1. Overview

The service is intended to extract deal records from HubSpot CRM API v3, track extraction jobs, and make extracted results available to callers.

- **Service name:** `hubspot_deals`
- **Local development port:** `5200`
- **Staging port:** `5201` (deployment URL must be supplied by the environment)
- **Production port:** `5202` (deployment URL must be supplied by the environment)
- **Content type:** `application/json` for JSON requests and responses
- **Local base URL:** `http://localhost:5200`

No public staging or production hostname is specified in the project configuration, so those URLs should be filled in from deployment settings.

## 2. Authentication

### 2.1 HubSpot authentication (upstream API)

HubSpot CRM API requests use a private-app access token:

```http
Authorization: Bearer <HUBSPOT_ACCESS_TOKEN>
Content-Type: application/json
```

The private app must have the required read permission, typically `crm.objects.deals.read`, to retrieve deals. Store the token in an environment variable or secret manager; do not commit it to source control or log it.

### 2.2 Authentication to this service

The client-facing authentication mechanism for the generated service must be confirmed from its middleware and route configuration. Do not assume that the HubSpot token is also the authentication token for callers of this service. If the service expects the HubSpot token in a scan configuration, document the exact field only after verifying the request model/controller.

## 3. Base URLs

| Environment | Base URL |
|---|---|
| Development | `http://localhost:5200` |
| Staging | `https://<configured-staging-host>` |
| Production | `https://<configured-production-host>` |

Replace the staging and production placeholders with the actual deployed URLs.

## 4. Service REST endpoints

The following route shapes come from the supplied API template and are **candidate routes to verify in the generated application**. The route registry/controller code is authoritative.

### 4.1 Start a deal extraction

**Candidate route:** `POST /scan/start`

Starts an extraction job for HubSpot deals.

**Candidate request body** (adapt field names to the actual request schema):

```json
{
  "config": {
    "scanId": "hubspot-deals-scan-001",
    "type": ["deals"],
    "deal_ids": ["512", "513"]
  }
}
```

If the implementation accepts credentials in the request configuration, use its exact documented field name. Prefer server-side environment/secret configuration where supported; never put a real access token in examples, logs, or committed files.

| Field | Type | Required | Description |
|---|---|---|---|
| `config` | object | Confirm in code | Extraction configuration |
| `config.scanId` | string | Confirm in code | Caller-supplied scan identifier |
| `config.type` | string array | Confirm in code | Extraction type; use `deals` if supported |
| `config.deal_ids` | string array | Optional, if supported | Optional list of specific HubSpot deal IDs |

**Illustrative accepted response:**

```json
{
  "message": "Deals extraction started",
  "scanId": "hubspot-deals-scan-001",
  "status": "started"
}
```

**Candidate status codes:** `202` accepted; `400` invalid request; `409` conflicting/in-progress scan; `500` internal error. Confirm the actual status codes in the handler.

### 4.2 Get extraction status

**Candidate route:** `GET /scan/status/{scan_id}`

Returns the current state of an extraction job.

**Path parameter**

| Parameter | Type | Description |
|---|---|---|
| `scan_id` | string | Identifier used when the scan was started |

**Illustrative response:**

```json
{
  "scanId": "hubspot-deals-scan-001",
  "status": "running",
  "started_at": "2026-10-10T10:30:00Z",
  "completed_at": null,
  "error_message": null,
  "total_items": 500,
  "processed_items": 200,
  "failed_items": 0
}
```

Possible job states, if implemented by the service: `pending`, `running`, `completed`, `failed`, `cancelled`. Confirm field names and not-found behavior in the actual response model.

**Candidate status codes:** `200` status returned; `400` invalid identifier; `404` job not found if the implementation uses HTTP 404; `500` internal error.

### 4.3 Get extraction results

**Candidate route:** `GET /scan/result/{scan_id}`

Returns the deals saved for a completed or partially completed scan.

**Candidate query parameters** (verify supported pagination style):

| Parameter | Type | Default | Description |
|---|---|---|---|
| `page` | integer | `1` | Page number, if page-based pagination is implemented |
| `page_size` | integer | `100` | Number of results per page, if supported |

**Illustrative response:**

```json
{
  "scanId": "hubspot-deals-scan-001",
  "status": "completed",
  "data": [
    {
      "deal_id": "512",
      "dealname": "Example deal",
      "amount": "12500.00",
      "dealstage": "closedwon",
      "pipeline": "default",
      "_tenant_id": "tenant_1",
      "_scan_id": "hubspot-deals-scan-001",
      "_extracted_at": "2026-10-10T10:45:00Z"
    }
  ],
  "count": 1,
  "total_count": 1
}
```

The example is illustrative. Return only fields that are actually stored and exposed by the implementation. Confirm whether results use `data`, `results`, a pagination object, or another response shape.

**Candidate status codes:** `200` results returned; `400` invalid pagination/input; `404` scan not found; `500` internal error.

### 4.4 Other routes in the template

The original template also includes these candidate routes. Document them as supported endpoints only if they exist in the route registry:

| Method | Candidate route | Purpose |
|---|---|---|
| `POST` | `/scan/cancel/{scan_id}` | Cancel a running scan |
| `DELETE` | `/scan/remove/{scan_id}` | Delete a scan and its stored results |
| `GET` | `/scan/download/{scan_id}/{format}` | Download results as JSON/CSV/Excel |
| `GET` | `/health` | Health check |
| `GET` | `/stats` | Service statistics |

Do not claim a particular download format or health-check dependency unless the implementation supports it.

## 5. Upstream HubSpot CRM API v3 — Deals

This section describes the API called by the extraction service, not the service's own endpoints.

### 5.1 List deals

**Method:** `GET`  
**Endpoint:** `https://api.hubapi.com/crm/v3/objects/deals`

**Query parameters**

| Parameter | Type | Description |
|---|---|---|
| `limit` | integer | Maximum number of records in a page; use a supported value up to the API's documented maximum |
| `after` | string | Pagination cursor returned by the previous response |
| `properties` | comma-separated string | Deal properties to include in each record |
| `archived` | boolean | Whether archived records are included |

**Example request:**

```bash
curl --get "https://api.hubapi.com/crm/v3/objects/deals" \
  --header "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN" \
  --data-urlencode "limit=100" \
  --data-urlencode "properties=dealname,amount,dealstage,pipeline,closedate,createdate,hs_lastmodifieddate" \
  --data-urlencode "archived=false"
```

For subsequent pages, pass the `paging.next.after` cursor from the previous response as the `after` query parameter. Continue until no next cursor is returned.

### 5.2 Example upstream response

```json
{
  "results": [
    {
      "id": "512",
      "properties": {
        "dealname": "Example deal",
        "amount": "12500",
        "dealstage": "closedwon",
        "pipeline": "default",
        "closedate": "2026-09-30T00:00:00Z",
        "createdate": "2026-01-10T12:00:00Z",
        "hs_lastmodifieddate": "2026-10-09T15:20:00Z"
      },
      "createdAt": "2026-01-10T12:00:00Z",
      "updatedAt": "2026-10-09T15:20:00Z",
      "archived": false
    }
  ],
  "paging": {
    "next": {
      "after": "NTI="
    }
  }
}
```

The values above are sample data. The response may omit `paging` when there is no next page. HubSpot returns property values as strings in many cases; convert them to the appropriate database types during normalization.

### 5.3 Deal properties

Common properties may include `dealname`, `amount`, `dealstage`, `pipeline`, `closedate`, `createdate`, `hs_lastmodifieddate`, `hubspot_owner_id`, `dealtype`, and `description`. The properties available depend on the HubSpot account and installed configuration.

To retrieve the account's available deal properties, use:

```http
GET https://api.hubapi.com/crm/v3/properties/deals
Authorization: Bearer <HUBSPOT_ACCESS_TOKEN>
```

Use the returned property `name` values when building the `properties` query parameter. Verify any forecast-probability property name against this endpoint before mapping it to the database.

## 6. Error handling and status codes

### 6.1 Client-facing service errors

The exact error payload depends on the generated service's exception handlers. A useful documented pattern, if it matches the implementation, is:

```json
{
  "status": "error",
  "error_code": "VALIDATION_ERROR",
  "message": "Input validation failed",
  "details": {}
}
```

| HTTP status | Meaning | Client action |
|---|---|---|
| `400` | Invalid input or validation failure | Correct the request |
| `401` | Missing or invalid client credentials, if service auth is enabled | Authenticate correctly |
| `403` | Caller lacks permission | Check access policy |
| `404` | Scan or result does not exist | Check the scan ID |
| `409` | Conflicting operation, if implemented | Check current scan status |
| `429` | Service rate limit reached, if implemented | Retry after the indicated delay |
| `500` | Unexpected service error | Inspect server logs; retry only when safe |
| `503` | Service temporarily unavailable, if implemented | Retry with backoff |

These are conventional meanings, not a guarantee that every status is currently returned. Update this table after checking the route handlers and global error middleware.

### 6.2 Upstream HubSpot errors

Handle HubSpot API errors separately from errors returned by the extraction service:

- `401 Unauthorized`: token is missing, invalid, or expired.
- `403 Forbidden`: the private app may lack the required CRM read scope.
- `429 Too Many Requests`: HubSpot rate limit reached; respect any retry guidance in the response headers/body and use exponential backoff with jitter.
- `5xx`: transient upstream service failure; retry with bounded backoff where safe.
- Other `4xx`: inspect the request, query parameters, object properties, and response body before retrying.

Do not retry permanent validation/authentication errors without first correcting the cause. Avoid logging access tokens or sensitive response data.

## 7. Example workflow

The following calls use the candidate service routes from the template. Run them only after verifying that these routes are registered by the application.

### Step 1 — Start extraction

```bash
curl -X POST "http://localhost:5200/scan/start" \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "scanId": "hubspot-deals-scan-001",
      "type": ["deals"],
      "deal_ids": ["512", "513"]
    }
  }'
```

### Step 2 — Check status

```bash
curl "http://localhost:5200/scan/status/hubspot-deals-scan-001"
```

### Step 3 — Retrieve results

```bash
curl "http://localhost:5200/scan/result/hubspot-deals-scan-001?page=1&page_size=100"
```

If the actual implementation uses a different payload or pagination scheme, update the examples to match it.

## 8. Rate limits and operational guidance

- Apply bounded retries with exponential backoff and jitter for transient upstream failures.
- Respect HubSpot rate-limit response headers and retry guidance.
- Use cursor-based pagination through the `after` parameter; do not assume one request returns every deal.
- Request only the properties needed for the extraction.
- Record scan status, counts, timestamps, and sanitized error details for troubleshooting.
- Keep access tokens in environment variables or a secret manager; never commit secrets to Git.
- Confirm whether the service itself implements request throttling, retry scheduling, cancellation, and scan locking before documenting those as available features.

## 9. Pre-submission verification checklist

- [ ] Confirm actual service routes from the registered router/application.
- [ ] Confirm request validation and exact required fields for starting a scan.
- [ ] Confirm whether client-facing authentication is enabled and how it works.
- [ ] Confirm actual response JSON for start, status, and results.
- [ ] Confirm HTTP status codes and error payloads from route handlers.
- [ ] Confirm whether cancel, remove, download, health, and stats routes exist.
- [ ] Confirm the HubSpot token is read securely and is never logged or committed.
- [ ] Test a start-scan request and retrieve results from a real local run.
- [ ] Ensure database result fields match `DATABASE-DESIGN-DOCS.md`.

## 10. Changelog

| Version | Date | Changes |
|---|---|---|
| 1.0.0 | 2026-10-10 | Adapted the API documentation template for HubSpot Deals ETL; documented candidate service routes, upstream HubSpot API, request/response examples, authentication, and error handling. |
