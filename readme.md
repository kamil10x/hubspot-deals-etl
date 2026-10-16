# HubSpot Deals ETL Service

A Flask-RESTX service that extracts **deals** from the HubSpot CRM API (v3) using [DLT](https://dlthub.com/) and loads them into PostgreSQL. It was generated with the DLT Generator and then customised for HubSpot as part of the DLT Integration Test.

- **Source:** HubSpot CRM API v3, `GET /crm/v3/objects/deals`
- **Auth:** HubSpot private app access token (`crm.objects.deals.read` scope)
- **Destination:** PostgreSQL (schema `hubspot_deals`)
- **Features:** cursor-based pagination, rate limiting (150 requests / 10 s), checkpointing, multi-tenant metadata, async scans with status tracking, Swagger UI

---

## Table of Contents

1. [Project Structure](#project-structure)
2. [Prerequisites](#prerequisites)
3. [Setup](#setup)
4. [Running the Service](#running-the-service)
5. [Using the API](#using-the-api)
6. [Configuration](#configuration)
7. [Test Data (5 HubSpot Deals)](#test-data-5-hubspot-deals)
8. [Validation Results](#validation-results)
9. [Documentation](#documentation)
10. [Troubleshooting](#troubleshooting)

---

## Project Structure

```
hubspot-deals-etl/
├── readme.md
├── docker-compose.yml          # dev / stage / prod services + PostgreSQL
├── Dockerfile.dev | .stage | .prod | .test
├── requirements.txt
├── .env.example                # environment template (no real secrets)
├── app.py                      # Flask application factory
├── wsgi.py                     # WSGI entry point
├── config.py                   # Configuration (loads .env)
├── utils.py, encrypter.py, loki_logger.py
│
├── api/
│   ├── routes.py               # Flask-RESTX endpoints + Swagger
│   └── schemas.py              # Request validation schemas
│
├── services/
│   ├── hubspot_api_service.py  # HubSpot client: auth, pagination, rate limiting, errors
│   ├── data_source.py          # DLT resource for deals, transforms, checkpoints
│   └── extraction_service.py   # Scan orchestration (runs the DLT pipeline)
│
├── models/
├── docs/                       # Project documentation (see below)
├── test-results/               # Proof of extraction and validation
└── test_*.py                   # Test scripts
```

## Prerequisites

- Docker and Docker Compose
- Python 3.11+ (only for running scripts locally)
- A HubSpot developer account with a test account and a private app (scope: `crm.objects.deals.read`)

## Setup

1. **Clone the repository**

   ```
   git clone https://github.com/kamil10x/hubspot-deals-etl.git
   cd hubspot-deals-etl
   ```

2. **Create your environment file**

   ```
   copy .env.example .env        (Windows)
   cp .env.example .env          (macOS / Linux)
   ```

3. **Add your HubSpot access token** to `.env`. Never commit `.env`; it is listed in `.gitignore`. Only `.env.example` (with placeholders) is tracked.

   To create a token: HubSpot → Settings → Integrations → Private Apps → create an app named "DLT Deals Extractor" with the `crm.objects.deals.read` scope → copy the access token.

## Running the Service

```
docker-compose up -d --build
```

Services (development profile):

| Environment | Port |
|-------------|------|
| Development | 5200 |
| Staging     | 5201 |
| Production  | 5202 |

Verify it is running:

```
curl http://localhost:5200/health
```

Swagger UI: <http://localhost:5200/docs/>

Stop the services:

```
docker-compose down
```

## Using the API

Full request/response documentation is in [`docs/api-documentation.md`](docs/api-documentation.md) and in the Swagger UI. The main endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/scan/start` | Start a deals extraction scan |
| GET | `/scan/{scan_id}/status` | Scan status and progress |
| POST | `/scan/{scan_id}/cancel` | Cancel a running scan |
| GET | `/scan/list` | List scans |
| GET | `/results/{scan_id}/tables` | Tables produced by a scan |
| GET | `/results/{scan_id}/result` | Extracted records |
| GET | `/pipeline/info` | DLT pipeline information |

> The exact route prefix (for example `/api/v1`) is shown in the Swagger UI at `/docs/`.

### Start a scan

Save the following as `scan-request.json` (replace the token with your own; do not commit this file):

```json
{
  "config": {
    "scanId": "hubspot-deals-scan-001",
    "organizationId": "org-12345",
    "type": ["data"],
    "auth": {
      "accessToken": "YOUR_HUBSPOT_PRIVATE_APP_TOKEN"
    },
    "filters": {
      "includeArchived": false
    }
  }
}
```

Then send it:

```
curl -X POST http://localhost:5200/api/v1/scan/start -H "Content-Type: application/json" -d @scan-request.json
```

### Check status and fetch results

```
curl http://localhost:5200/api/v1/scan/hubspot-deals-scan-001/status
curl http://localhost:5200/api/v1/results/hubspot-deals-scan-001/tables
curl "http://localhost:5200/api/v1/results/hubspot-deals-scan-001/result?limit=10"
```

## Configuration

All settings live in `.env` (template in `.env.example`).

| Variable | Description | Example |
|----------|-------------|---------|
| `FLASK_ENV` | Flask environment | `development` |
| `DB_HOST` / `DB_PORT` | PostgreSQL host and port | `postgres_dev` / `5432` |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | Development database credentials | see `.env.example` |
| `DB_SCHEMA` | Target schema | `hubspot_deals` |
| `HUBSPOT_*` base URL / timeout | HubSpot API base URL and request timeout | `https://api.hubapi.com`, `30` |
| `HUBSPOT_DEALS_API_TOKEN` | HubSpot access token (**keep secret**) | `your-token-here` |
| `DLT_PIPELINE_NAME` | DLT pipeline name | see `.env.example` |
| `MAX_CONCURRENT_SCANS` | Concurrent scan limit | `3` |
| `LOG_LEVEL` | Logging level | `INFO` |

## How It Works

1. **`hubspot_api_service.py`** authenticates with the private app access token, calls `/crm/v3/objects/deals`, follows HubSpot's cursor (`after`) for pagination, respects the 150 requests / 10 seconds limit, handles API errors (401, 403, 429, 5xx), validates credentials and logs each step.
2. **`data_source.py`** defines the DLT resource for deals with `id` as the primary key, converts types (dates, amounts), adds ETL metadata (`_extracted_at`, `_scan_id`, `_tenant_id`) and saves a checkpoint every N pages so an interrupted scan can resume.
3. **`extraction_service.py`** runs the pipeline asynchronously and records scan status. Data is written to PostgreSQL under the `hubspot_deals` schema.

## Test Data (5 HubSpot Deals)

Created in the HubSpot test account (portal `247668258`). Details are also in [`docs/test-deals.md`](docs/test-deals.md).

| Deal | Amount | Stage | Close date | Deal ID |
|------|--------|-------|------------|---------|
| Website Development | $5,000 | Qualified To Buy | 2026-11-15 | 353410017998 |
| CRM Integration | $25,000 | Presentation Scheduled | 2026-11-30 | 353762832066 |
| Globex Annual Support Renewal | $50,000 | Closed Won | 2026-10-05 | 353762832079 |
| Initech Enterprise Integration | $75,000 | Closed Lost | 2026-09-28 | 353525605104 |
| Umbrella Multi-Year Licensing | $100,000 | Contract Sent | 2027-01-20 | 353525605109 |

## Validation Results

Evidence is stored in [`test-results/`](test-results/).

| Check | Result | Evidence |
|-------|--------|----------|
| Docker services start without errors | ☐ Pass | `test-results/` |
| `GET /health` returns healthy | ☐ Pass | `test-results/` |
| Credential validation / bad token returns 401 | ☐ Pass | `test-results/` |
| Pagination (`limit=1` returns all 5 deals over 5 pages) | ☐ Pass | `test-results/` |
| Scan completes, 5 / 5 deals extracted | ☐ Pass | `test-results/` |
| Database records match the deal IDs above | ☐ Pass | `test-results/` |
| Checkpoint: interrupt and resume a scan | ☐ Pass | `test-results/` |
| Service stop / restart works | ☐ Pass | `test-results/` |
| Swagger UI available at `/docs/` | ☐ Pass | `test-results/` |

> Update the ☐ marks to ✅ and link the matching files once each check is done.

## Documentation

| Document | Contents |
|----------|----------|
| [`docs/api-integration.md`](docs/api-integration.md) | HubSpot CRM API v3 deals endpoint, auth, parameters, response format, rate limits, errors, deal properties |
| [`docs/database-schema.md`](docs/database-schema.md) | PostgreSQL tables, type mapping, ETL metadata, indexes, multi-tenant isolation |
| [`docs/api-documentation.md`](docs/api-documentation.md) | This service's REST endpoints, schemas, auth, error codes, examples |
| [`docs/test-deals.md`](docs/test-deals.md) | The 5 test deals and their IDs |

## Troubleshooting

**Service will not start**

```
docker-compose logs
docker-compose down -v
docker-compose up -d --build
```

**`401 Unauthorized` from HubSpot**: the token is missing, expired or revoked. Create a new one in the private app and update `.env`.

**`403 Forbidden`**: the private app is missing the `crm.objects.deals.read` scope.

**`429 Too Many Requests`**: the HubSpot rate limit was hit. The service backs off automatically; reduce concurrent scans if it persists.

**Port already in use**: stop whatever is using ports 5200–5202, or change the ports in `docker-compose.yml`.

**Database connection issues**

```
docker-compose exec postgres_dev pg_isready -U postgres
```

## Security

- The HubSpot access token is never committed. Keep it only in your local `.env` or in the scan request body.
- If a token is ever exposed, revoke it in HubSpot and generate a new one.

---

*Generated with the DLT Generator and customised for HubSpot Deals extraction.*
