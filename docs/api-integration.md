# HubSpot Deals Extraction Service - Integration with HubSpot CRM API

This document describes the HubSpot CRM API v3 endpoints used by the `hubspot_deals` service to extract Deals data from a HubSpot account. It covers authentication, endpoint usage, pagination, data mapping, error handling, testing, and operational recommendations.

---

## Overview

The service uses the HubSpot CRM API to retrieve deal records. The primary endpoint is sufficient for basic extraction when the requested properties are included in the `properties` query parameter.

### Required Endpoint

| API Endpoint | Purpose | Version | Required Scope | Usage |
|---|---|---|---|---|
| `GET /crm/v3/objects/deals` | List deals using cursor-based pagination | v3 | `crm.objects.deals.read` | **Required** |

### Optional Endpoint

| API Endpoint | Purpose | Version | Required Scope | Usage |
|---|---|---|---|---|
| `GET /crm/v3/properties/deals` | Discover deal property definitions, including names, types, and labels | v3 | Verify the scope required by the HubSpot account and app configuration | Optional |

### Recommendation

Start with `GET /crm/v3/objects/deals`. Use the optional properties endpoint only when the service needs to discover available property definitions dynamically.

**Base URL:** `https://api.hubapi.com`

---

## Authentication Requirements

### Private App Access Token

HubSpot private app access tokens are sent as bearer tokens:

```http
Authorization: Bearer $HUBSPOT_ACCESS_TOKEN
Content-Type: application/json
```

Use an environment variable or the service's approved secret configuration to supply the token. Never commit a real token to the repository, include it in documentation, or write it to logs.

### Required Scope

- `crm.objects.deals.read`: read access to deal records.

### Creating a Private App Token

In HubSpot, open **Settings → Integrations → Private Apps**, create a private app, add the required scope, and copy its access token into the service's secure configuration. The exact interface labels may vary.

---

## HubSpot API Endpoints

### 1. List Deals — `GET /crm/v3/objects/deals` (Required)

**Purpose:** Retrieve a paginated list of deals.

**Method:** `GET`

**URL:** `https://api.hubapi.com/crm/v3/objects/deals`

#### Query Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `limit` | integer | No | Number of records to return per page. The endpoint supports a maximum of 100 records per request. |
| `after` | string | No | Cursor returned in `paging.next.after` by the previous response. Omit it on the first request. |
| `properties` | string | No | Comma-separated property names to include in each deal's `properties` object. |
| `archived` | boolean | No | Whether to return archived deals. The default is `false`. |

#### Request Example

This example requests the properties documented in the service's default property list:

```bash
curl -X GET "https://api.hubapi.com/crm/v3/objects/deals?limit=100&properties=dealname,amount,dealstage,pipeline,dealtype,description,closedate,createdate,hs_lastmodifieddate,hubspot_owner_id,hs_is_closed,hs_is_closed_won,hs_deal_stage_probability&archived=false" \
  -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN" \
  -H "Content-Type: application/json"
```

#### Example Response

The values below are illustrative. Actual records and available properties depend on the HubSpot account.

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
        "dealtype": "existingbusiness",
        "description": "Renewal opportunity",
        "closedate": "2026-12-01T00:00:00.000Z",
        "createdate": "2026-10-01T09:12:44.123Z",
        "hs_lastmodifieddate": "2026-10-05T11:02:10.001Z",
        "hubspot_owner_id": "12345",
        "hs_is_closed": "false",
        "hs_is_closed_won": "false",
        "hs_deal_stage_probability": "0.6"
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

- Deal property values are commonly represented as strings in the `properties` object; convert values to the destination types as required by the service schema.
- A response may include a `paging.next` object when more records are available. When it is absent, pagination is complete.
- Pagination is cursor-based. Pass the returned `paging.next.after` value as the `after` parameter in the next request.
- Request every property the service needs explicitly; do not assume every property will be returned by default.

### 2. List Deal Property Definitions — `GET /crm/v3/properties/deals` (Optional)

**Purpose:** Discover property definitions available for deals in the HubSpot account, including property names, labels, and types.

**When to use:** Use this endpoint if the integration needs to inspect available fields or support account-specific/custom properties. It is not required just to retrieve deals when the property names are already known.

**Method:** `GET`

**URL:** `https://api.hubapi.com/crm/v3/properties/deals`

#### Request Example

```bash
curl -X GET "https://api.hubapi.com/crm/v3/properties/deals" \
  -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN" \
  -H "Content-Type: application/json"
```

The response contains a `results` array of property definitions. Each definition can include fields such as `name`, `label`, `type`, and `fieldType`. Refer to the current HubSpot API documentation for the complete response schema and permission requirements.

---

## Available Deal Properties

The service documentation lists the following default properties:

| Property | Description |
|---|---|
| `dealname` | Name of the deal |
| `amount` | Deal amount |
| `dealstage` | Current pipeline stage |
| `pipeline` | Pipeline the deal belongs to |
| `dealtype` | Deal type, such as new or existing business |
| `description` | Deal description |
| `closedate` | Expected or actual close date |
| `createdate` | Deal creation time |
| `hs_lastmodifieddate` | Last modification time |
| `hubspot_owner_id` | ID of the deal owner |
| `hs_is_closed` | Whether the deal is closed |
| `hs_is_closed_won` | Whether the deal was won |
| `hs_deal_stage_probability` | Probability associated with the deal stage |

Other standard and custom properties may be available in an account. Use `GET /crm/v3/properties/deals` to discover the account's property definitions when needed.

---

## Data Extraction Flow

### Simple Flow — Required Endpoint Only

The service can retrieve deals by repeatedly requesting pages from the required endpoint. The following is an illustrative example of the cursor-based flow; adapt it to the actual HTTP client and checkpoint implementation in the service.

```python
import requests

def extract_deals(base_url, auth_headers, properties):
    """Retrieve deals using HubSpot cursor-based pagination."""
    url = f"{base_url}/crm/v3/objects/deals"
    params = {
        "limit": 100,
        "properties": ",".join(properties),
        "archived": "false",
    }
    all_deals = []

    while True:
        response = requests.get(
            url,
            headers=auth_headers,
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        all_deals.extend(data.get("results", []))

        next_page = data.get("paging", {}).get("next")
        if not next_page or not next_page.get("after"):
            break

        params["after"] = next_page["after"]

    return all_deals
```

### Advanced Flow — Optional Property Discovery

1. Call `GET /crm/v3/properties/deals` when property definitions need to be discovered.
2. Inspect the returned property names and types.
3. Select the properties required by the extraction configuration.
4. Request deal records through `GET /crm/v3/objects/deals`, using the `properties` parameter and normal pagination.

Property discovery is optional and should not be treated as a prerequisite for every scan.

---

## Performance Considerations

### Rate Limiting

- **Service configuration documented here:** a client-side throttle of 150 requests per 10 seconds.
- **HubSpot limits:** actual limits depend on the app and account tier. Confirm the current limits for the account before relying on a particular threshold.
- **Rate-limit response:** HubSpot may return `429 Too Many Requests`; respect the `Retry-After` header when provided.

### Retry Behavior

The current service documentation describes this behavior:

1. A sliding-window throttle limits the request rate.
2. On a `429` response, the service waits for the duration indicated by `Retry-After` and retries.
3. On server errors and timeouts, the service uses backoff delays of 2, 4, and 8 seconds, with a maximum of three attempts.

Confirm these details against the current implementation before treating them as verified runtime behavior.

### Batch Processing

- Use a page size of up to 100 records where appropriate for the endpoint.
- Prefer cursor pagination over repeatedly fetching the first page.
- Avoid unnecessary per-deal API calls; request the required properties in the list endpoint.
- Configure concurrency conservatively and ensure combined requests stay within the account's applicable limits.

---

## Error Handling

| HTTP Status / Error | Meaning | Recommended Handling |
|---|---|---|
| `400 Bad Request` | Invalid parameter or malformed request | Check query parameters and requested property names. |
| `401 Unauthorized` | Token is invalid or expired | Verify the configured private app token. |
| `403 Forbidden` | App lacks required access or scope | Check the app's scopes and account access. |
| `404 Not Found` | Endpoint or resource was not found | Verify the endpoint path and API version. |
| `429 Too Many Requests` | Rate limit exceeded | Respect `Retry-After` and retry safely. |
| `500`, `502`, `503`, `504` | Server-side failure | Retry with bounded backoff, then report the failure. |
| Timeout / connection error | Network or connectivity problem | Retry within a bounded policy and record the failure. |

The existing service documentation states that a failed scan saves an error checkpoint with the last cursor. Verify this behavior against the implementation and document any recovery limitations.

---

## Security Requirements

### Minimum Access

- Use the `crm.objects.deals.read` scope for reading deal records.
- Add only the additional scopes required by features that are actually implemented.
- Confirm the permission requirements for optional endpoints against the current HubSpot documentation.

### Secret Handling

- Store the private app token in a secret manager or environment-based configuration appropriate to the deployment.
- Never commit real tokens to source control.
- Redact authorization headers and tokens from logs and error messages.
- Use a separate test app/token when practical, and revoke credentials that are no longer needed.

---

## Monitoring & Debugging

### Safe Request Diagnostics

Record useful diagnostic details without exposing secrets:

- Endpoint path and HTTP status code.
- Request duration and retry count.
- Pagination progress, such as the number of records processed.
- Rate-limit responses and relevant retry timing.
- Scan or correlation identifier, if the service provides one.

Do not log the bearer token or full authorization header.

### Response Validation

Validate that the response is successful and that `results` is an array before processing it. For each deal, verify that the record identifier is present and handle missing optional properties explicitly. Convert values only according to the destination schema.

---

## Testing API Integration

### 1. Test Authentication and Deal Access

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN" \
  "https://api.hubapi.com/crm/v3/objects/deals?limit=1"
```

| Result | Meaning |
|---|---|
| `200` | The request succeeded; the token has access to this endpoint. |
| `401` | The token may be invalid or expired. |
| `403` | The app may lack the required scope or access. |

### 2. Test Deal Extraction

```bash
curl -X GET "https://api.hubapi.com/crm/v3/objects/deals?limit=5&properties=dealname,amount,dealstage" \
  -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN" \
  -H "Content-Type: application/json"
```

Check that the response contains a `results` array and the requested properties where values are available.

### 3. Test Property Discovery (Optional)

```bash
curl -X GET "https://api.hubapi.com/crm/v3/properties/deals" \
  -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN" \
  -H "Content-Type: application/json"
```

Use this test only if property discovery is part of the intended integration.

---

## Common Issues & Solutions

### `401 Unauthorized`

**Possible cause:** The token is missing, invalid, or expired.

**Solution:** Confirm that `HUBSPOT_ACCESS_TOKEN` is set correctly and that the request uses `Authorization: Bearer ...`. Never paste the token into shared logs or documentation.

### `403 Forbidden`

**Possible cause:** The private app does not have the required scope or access.

**Solution:** Verify `crm.objects.deals.read` and the app's access to the relevant HubSpot account.

### `429 Too Many Requests`

**Possible cause:** The app exceeded an applicable rate limit.

**Solution:** Respect `Retry-After`, reduce concurrency if necessary, and retry using a bounded policy.

### Empty Deal List

**Possible cause:** The account has no deals visible to the app, or the request targets a different account than expected.

**Solution:** Check the HubSpot account, token, endpoint, and whether the response's `results` array is empty. An empty array is not necessarily an API error.

### Missing Properties

**Possible cause:** The property was not requested, is unavailable in the account, or has no value for that deal.

**Solution:** Include the property name in `properties` and check the account's definitions through the optional properties endpoint.

---

## Implementation Recommendations

### Phase 1 — Basic Extraction

1. Configure the private app token securely.
2. Request deals from `GET /crm/v3/objects/deals`.
3. Explicitly request the fields required by the destination schema.
4. Follow `paging.next.after` until there are no more pages.
5. Validate and map records before saving them.

### Phase 2 — Optional Enhancements

1. Add property discovery if the integration needs account-specific field metadata.
2. Improve observability and error diagnostics.
3. Verify retry, checkpoint, and resume behavior through tests before describing these as guaranteed features.

### Performance Tip

Requesting the required properties in a paginated list call reduces the need for separate requests for each deal. Keep request volume, concurrency, and retries within the applicable HubSpot limits.

---

## Support Resources

- **HubSpot CRM Deals API:** https://developers.hubspot.com/docs/api/crm/deals
- **HubSpot Private Apps:** https://developers.hubspot.com/docs/api/private-apps
- **HubSpot API Usage Guidelines:** https://developers.hubspot.com/docs/api/usage-details
