# HubSpot Deals Extraction Service - Integration with HubSpot CRM API

This document describes the HubSpot CRM API v3 endpoints used by the `hubspot_deals` service to extract Deals data from a HubSpot account.

---

## Overview

### Required Endpoint
| API Endpoint | Purpose | Version | Required Scope | Usage |
|---|---|---|---|---|
| `GET /crm/v3/objects/deals` | List deals (paginated) | v3 | `crm.objects.deals.read` | **Required** |

### Optional Endpoint
| API Endpoint | Purpose | Version | Required Scope | Usage |
|---|---|---|---|---|
| `GET /crm/v3/properties/deals` | List deal property definitions (names, types, labels) | v3 | `crm.objects.deals.read` | Optional |

### Recommendation
Start with only `/crm/v3/objects/deals`. It returns everything needed for deals extraction when the `properties` parameter lists the fields you want.

Base URL: `https://api.hubapi.com`

---

## Authentication

HubSpot private app access tokens are sent as a bearer token:

```http
Authorization: Bearer pat-na1-xxxxxxxx
Content-Type: application/json
```

### Required scope
- `crm.objects.deals.read`: read access to deal records

### Creating the token
Settings -> Integrations -> Private Apps -> Create private app ("DLT Deals Extractor") -> Scopes -> add `crm.objects.deals.read` -> Create app -> copy the access token.

The token is passed to the service in each scan request. It must never be committed to the repository or written to logs.



---

## HubSpot API Endpoint

### 1. List Deals - `GET /crm/v3/objects/deals` (Required)

**Purpose:** Get a paginated list of all deals. This is all the service needs for basic deal extraction.

**URL:** `https://api.hubapi.com/crm/v3/objects/deals`

#### Query Parameters
| Parameter | Type | Required | Description |
|---|---|---|---|
| `limit` | integer | No | Number of deals per page. Maximum 100 (the service uses 100). |
| `after` | string | No | Pagination cursor. Take it from `paging.next.after` of the previous response. |
| `properties` | string | No | Comma-separated property names to return. HubSpot returns only a few properties unless you ask for more. |
| `archived` | boolean | No | `true` returns only archived deals. Default is `false`. |

#### Request Example
```bash
curl -X GET "https://api.hubapi.com/crm/v3/objects/deals?limit=100&properties=dealname,amount,dealstage,pipeline,closedate,createdate&archived=false" \
  -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN" \
  -H "Content-Type: application/json"
```

#### Response Structure
```json
{
  "results": [
    {
      "id": "512",
      "properties": {
        "dealname": "Acme Renewal",
        "amount": "25000",
        "dealstage": "presentationscheduled",
        "pipeline": "default",
        "closedate": "2026-12-01T00:00:00.000Z",
        "createdate": "2026-10-01T09:12:44.123Z",
        "hs_lastmodifieddate": "2026-10-05T11:02:10.001Z",
        "hs_object_id": "512"
      },
      "createdAt": "2026-10-01T09:12:44.123Z",
      "updatedAt": "2026-10-05T11:02:10.001Z",
      "archived": false
    }
  ],
  "paging": {
    "next": {
      "after": "513",
      "link": "https://api.hubapi.com/crm/v3/objects/deals?after=513"
    }
  }
}
```

#### Key Points
- Every property value comes back as a **string**, even numbers and booleans. The service converts the types before saving.
- `paging` is missing on the last page. That is how the service knows to stop.
- Pagination is cursor-based: send `after=<value>` to get the next page.


---

## Available Deal Properties

The service requests these properties by default:

| Property | HubSpot type | Description |
|---|---|---|
| `dealname` | string | Name of the deal |
| `amount` | number | Deal amount |
| `dealstage` | enumeration | Current pipeline stage (for example `qualifiedtobuy`, `closedwon`, `closedlost`) |
| `pipeline` | enumeration | Pipeline the deal belongs to |
| `dealtype` | enumeration | New business or existing business |
| `description` | string | Deal description |
| `closedate` | datetime | Expected or actual close date |
| `createdate` | datetime | When the deal was created |
| `hs_lastmodifieddate` | datetime | Last modification time |
| `hubspot_owner_id` | string | ID of the owner |
| `hs_is_closed` | bool | Whether the deal is closed |
| `hs_is_closed_won` | bool | Whether the deal was won |
| `hs_deal_stage_probability` | number | Win probability of the current stage |

Other properties exist, such as `hs_priority`, `hs_forecast_amount`, `hs_acv`, `hs_arr`, `hs_mrr` and `hs_tcv`, as well as custom properties. Call `GET /crm/v3/properties/deals` to list every property available in an account.

---

## Rate Limits

- The service is configured for **150 requests per 10 seconds**.
- HubSpot's actual limit depends on the account tier, so confirm yours in the HubSpot API usage guidelines. There is also a daily request limit.
- When the limit is exceeded, HubSpot returns `429 Too Many Requests` with a `Retry-After` header.

### How the service handles it
1. **Client-side throttle:** a sliding window never sends more than 150 requests in any 10-second period.
2. **Retry-After:** on a 429 the service waits the number of seconds HubSpot asks for and retries.
3. **Backoff:** on 5xx errors and timeouts it waits 2, 4, then 8 seconds, with a maximum of 3 attempts.

---

## Error Handling

| Status | Meaning | Service behaviour |
|---|---|---|
| 400 | Invalid parameter or request | Scan fails with the error message |
| 401 | Token invalid or expired | Scan fails: "Invalid or expired HubSpot access token" |
| 403 | Token lacks the required scope | Scan fails: "Missing scope: crm.objects.deals.read" |
| 404 | Endpoint not found | Scan fails |
| 429 | Rate limit exceeded | Wait for `Retry-After`, then retry |
| 500 / 502 / 503 / 504 | HubSpot server error | Retry with backoff, then fail after 3 attempts |
| Timeout / connection error | Network problem | Retry with backoff, then fail |

When a scan fails, the service saves an error checkpoint with the last cursor so the failure can be investigated.



---

## Pagination Flow in the Service

1. First request: `GET /crm/v3/objects/deals?limit=100&properties=...` with no `after`.
2. Process every item in `results`.
3. If `paging.next.after` exists, send the next request with `after=<that value>`.
4. If `paging` is missing, extraction is complete.
5. Every 10 pages the service saves a checkpoint holding the cursor, so a paused or interrupted scan resumes from the last saved page.

---

## Data Mapping (HubSpot to Database)

| HubSpot field | Database column | Conversion |
|---|---|---|
| `id` | `id` | string, primary key |
| `properties.dealname` | `dealname` | text |
| `properties.amount` | `amount` | string to number |
| `properties.dealstage` | `dealstage` | text |
| `properties.closedate`, `createdate` | `closedate`, `createdate` | ISO string to timestamp |
| `properties.hs_is_closed_won` | `hs_is_closed_won` | `"true"`/`"false"` to boolean |
| `archived` | `archived` | boolean |

Extraction metadata is added to each record: `_extracted_at`, `_scan_id` and `_tenant_id`. The full schema is in `database-schema.md`.

---

## Verifying the Integration Manually

Test the token and scope before running the service:

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN" \
  "https://api.hubapi.com/crm/v3/objects/deals?limit=1"
```

| Result | Meaning |
|---|---|
| `200` | Token and scope are valid |
| `401` | Token is wrong or expired |
| `403` | The private app is missing `crm.objects.deals.read` |

## References
- HubSpot CRM API, Deals (v3): https://developers.hubspot.com/docs/api/crm/deals
- HubSpot private apps: https://developers.hubspot.com/docs/api/private-apps
- HubSpot API usage guidelines and rate limits: https://developers.hubspot.com/docs/api/usage-details