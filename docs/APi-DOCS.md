# hubspot_deals - API Documentation

## Table of Contents
1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Base URLs](#base-urls)
4. [Deals API Endpoint](#deals-api-endpoint)
5. [Query Parameters and Pagination](#query-parameters-and-pagination)
6. [Response Format](#response-format)
7. [Deal Properties](#deal-properties)
8. [Rate Limiting](#rate-limiting)
9. [Error Handling](#error-handling)
10. [Examples](#examples)
11. [References](#references)
12. [Changelog](#changelog)

## Overview

The `hubspot_deals` service integrates with HubSpot CRM to retrieve deal records for the `hubspot-deals-etl` project. It uses the HubSpot CRM Deals API and supports property selection and cursor-based pagination.

- **Project name:** `hubspot-deals-etl`
- **Service name:** `hubspot_deals`
- **API version requested by this task:** CRM API v3
- **HubSpot API base URL:** `https://api.hubapi.com`
- **Content type:** `application/json`
- **Main endpoint:** `GET /crm/v3/objects/deals`

> **Version/authentication note:** This document describes the requested CRM API v3 endpoint and private-app access-token pattern. Before using it in a new HubSpot account, check HubSpot's current migration guidance and supported authentication options. Do not assume legacy private-app creation remains available for every account or use case.

## Authentication

HubSpot API requests must include an access token authorized to read CRM deal records.

### Private-app access token

For an existing HubSpot private app that supports this authentication method, include the token in the HTTP `Authorization` header:

```http
Authorization: Bearer YOUR_ACCESS_TOKEN
Content-Type: application/json
```

The token must have the appropriate deal-reading permission, commonly `crm.objects.deals.read`.

### Security requirements

- Store the token in an environment variable or secrets manager.
- Never commit a real token to source control.
- Do not include tokens in logs, screenshots, documentation, or error messages.
- Rotate/revoke exposed credentials promptly.
- Use only credentials authorized for the HubSpot account being accessed.

Example environment variable:

```env
HUBSPOT_ACCESS_TOKEN=replace_with_your_token
```

The value above is a placeholder, not a working credential.

## Base URLs

### HubSpot API

```text
https://api.hubapi.com
```

### Deals endpoint

```text
https://api.hubapi.com/crm/v3/objects/deals
```

The generated service's own development, staging, and production ports (5200, 5201, and 5202) are separate from HubSpot's API host.

## Deals API Endpoint

### Retrieve deals

**Method:** `GET`

**Path:** `/crm/v3/objects/deals`

**Full URL:** `https://api.hubapi.com/crm/v3/objects/deals`

Returns a page of deal records accessible to the authenticated HubSpot account.

### Request headers

```http
Authorization: Bearer YOUR_ACCESS_TOKEN
Accept: application/json
Content-Type: application/json
```

## Query Parameters and Pagination

| Parameter | Type | Required | Description |
|---|---|---|---|
| `limit` | integer | No | Maximum number of records to return in one page. The v3 endpoint supports up to 100 records per request. |
| `after` | string | No | Cursor used to retrieve the next page. Use the `paging.next.after` value from the previous response. |
| `properties` | comma-separated string | No | Deal property internal names to include, for example `dealname,amount,dealstage`. |
| `archived` | boolean | No | Whether to include archived deals. Defaults to `false` when omitted. |

### Example request

```http
GET https://api.hubapi.com/crm/v3/objects/deals?limit=10&properties=dealname,amount,dealstage,pipeline,closedate&archived=false
```

### Pagination workflow

1. Send the first request with `limit`, for example `limit=100`.
2. Process the `results` array.
3. If `paging.next.after` exists, send another request using that value as the `after` parameter.
4. Repeat until the response has no `paging.next` object.

Example next-page request:

```http
GET https://api.hubapi.com/crm/v3/objects/deals?limit=100&after=NEXT_CURSOR
```

Treat the cursor as an opaque value returned by HubSpot; do not calculate it yourself.

## Response Format

A successful response contains a `results` array. Each deal generally includes an `id`, a `properties` object, creation/update timestamps, and an `archived` flag. A `paging.next` object is present when another page is available.

### Sample JSON response

The following is an illustrative example; the IDs, values, properties, and cursor are sample data.

```json
{
  "results": [
    {
      "id": "123456",
      "properties": {
        "dealname": "Enterprise Software Deal",
        "amount": "15000",
        "dealstage": "contractsent",
        "pipeline": "default",
        "closedate": "2026-11-15T00:00:00Z",
        "createdate": "2026-10-01T10:30:00Z",
        "hs_lastmodifieddate": "2026-10-05T12:00:00Z"
      },
      "createdAt": "2026-10-01T10:30:00Z",
      "updatedAt": "2026-10-05T12:00:00Z",
      "archived": false
    }
  ],
  "paging": {
    "next": {
      "after": "123457",
      "link": "https://api.hubapi.com/crm/v3/objects/deals?after=123457"
    }
  }
}
```

If no further page is available, HubSpot may omit the `paging` field.

## Deal Properties

The `properties` query parameter accepts a comma-separated list of property **internal names**. Common standard deal properties include:

| Internal name | Description |
|---|---|
| `dealname` | Deal name |
| `amount` | Deal amount |
| `dealstage` | Current deal stage |
| `pipeline` | Pipeline containing the deal |
| `closedate` | Expected or actual close date |
| `createdate` | Date the deal was created |
| `hs_lastmodifieddate` | Date the deal was last modified |
| `hubspot_owner_id` | HubSpot owner ID |
| `dealtype` | Deal type, when available |
| `description` | Deal description |
| `hs_priority` | Deal priority, when available |
| `hs_object_id` | HubSpot object ID |
| `hs_is_closed` | Indicates whether the deal is closed, when available |
| `hs_is_closed_won` | Indicates whether the deal is closed-won, when available |
| `hs_forecast_probability` | Forecast probability, when available |
| `hs_forecast_amount` | Forecast amount, when available |
| `hs_manual_forecast_category` | Manually assigned forecast category, when available |
| `hs_deal_stage_probability` | Probability associated with the deal stage, when available |

This is a representative list, **not a guaranteed exhaustive list**. Available properties can vary by HubSpot account, API behavior, and custom configuration. Do not assume every property above exists in every account.

### Retrieve all available deal properties

Use the HubSpot CRM Properties API:

**Method:** `GET`

**Endpoint:** `/crm/v3/properties/deals`

**Full URL:** `https://api.hubapi.com/crm/v3/properties/deals`

Include the same `Authorization: Bearer YOUR_ACCESS_TOKEN` header. Inspect the returned `results` array for the account's available standard and custom properties. Property metadata can include fields such as `name`, `label`, `type`, `fieldType`, and `description`.

To document every property available in a particular HubSpot account, capture the actual authorized endpoint response rather than treating the representative list above as exhaustive.

## Rate Limiting

HubSpot enforces API usage limits. The applicable limit can depend on the app/authentication type, account subscription, and endpoint.

Recommended handling:

- Check HubSpot's current official rate-limit documentation for the limits applicable to the integration.
- Handle HTTP `429 Too Many Requests` responses.
- Honor a `Retry-After` header when provided.
- Use bounded exponential backoff with jitter for retryable rate-limit or transient server errors.
- Avoid retrying invalid requests or authentication failures without first fixing the cause.
- Request only the properties needed and use pagination to process records efficiently.
- Avoid logging access tokens or other secrets.

Do not hard-code a single numeric quota unless it has been verified for the relevant HubSpot account and authentication method.

## Error Handling

| HTTP status | Meaning | Recommended action |
|---|---|---|
| `400 Bad Request` | Invalid parameter, malformed request, or invalid property | Check query syntax and property internal names. |
| `401 Unauthorized` | Missing, invalid, or expired token | Verify the credential and `Authorization` header. |
| `403 Forbidden` | The credential lacks required access | Check the app's permissions/scopes and account access. |
| `404 Not Found` | Endpoint or requested resource not found | Verify the URL and resource identifier. |
| `429 Too Many Requests` | Rate limit exceeded | Honor `Retry-After` if present and retry with bounded backoff. |
| `5xx` | HubSpot server-side or temporary error | Retry transient failures with bounded exponential backoff and jitter. |

### Error-handling guidelines

1. Check the HTTP status code before processing the response as a successful result.
2. Parse HubSpot's error response when possible and record a safe, useful diagnostic.
3. Never log the access token.
4. Set connection/read timeouts in the HTTP client.
5. Limit retry attempts and avoid infinite retry loops.
6. Do not repeatedly retry `400`, `401`, or `403` errors without correcting the request or credentials.

HubSpot's error payload may differ from the generated service's own error-response format. If this service wraps upstream errors, document both formats separately.

## Examples

### cURL: Retrieve deals

```bash
curl --request GET \
  --url 'https://api.hubapi.com/crm/v3/objects/deals?limit=10&properties=dealname,amount,dealstage,pipeline,closedate&archived=false' \
  --header 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  --header 'Accept: application/json'
```

Replace `YOUR_ACCESS_TOKEN` with a valid token supplied securely. Do not paste a real token into documentation or commit it to Git.

### Python: Retrieve deals

```python
import os
import requests

url = "https://api.hubapi.com/crm/v3/objects/deals"
token = os.environ["HUBSPOT_ACCESS_TOKEN"]

headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/json",
}

params = {
    "limit": 100,
    "properties": "dealname,amount,dealstage,pipeline,closedate",
    "archived": "false",
}

response = requests.get(url, headers=headers, params=params, timeout=30)
response.raise_for_status()
data = response.json()

for deal in data.get("results", []):
    print(deal["id"], deal.get("properties", {}).get("dealname"))

# If data.get("paging", {}).get("next") exists, use its "after" value
# to request the next page.
```

The code expects `HUBSPOT_ACCESS_TOKEN` to be configured in the environment. It intentionally does not contain a real token.

## References

- [HubSpot CRM Deals API v3 guide](https://developers.hubspot.com/docs/api-reference/crm-deals-v3/guide)
- [HubSpot CRM Properties API v3 guide](https://developers.hubspot.com/docs/api-reference/crm-properties-v3/guide)
- [HubSpot API usage guidelines and rate limits](https://developers.hubspot.com/docs/developer-tooling/platform/usage-guidelines)
- [HubSpot authentication guidance](https://developers.hubspot.com/docs/apps/legacy-apps/private-apps/overview)

## Changelog

| Version | Change |
|---|---|
| 1.0.0 | Reworked the generic template for the `hubspot_deals` service; documented the deals endpoint, authentication, query parameters, pagination, response example, properties, rate limiting, and error handling. |
