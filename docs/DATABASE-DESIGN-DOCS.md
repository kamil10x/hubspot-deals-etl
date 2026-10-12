# 🗄️ hubspot_deals - Database Schema

This document defines the PostgreSQL schema for the `hubspot_deals` service (project `hubspot-deals-etl`). It follows the standard scan-job template with two tables:

1. **`scan_jobs`** - scan job management and tracking
2. **`hubspot_deals`** - deal records extracted from HubSpot CRM (`GET /crm/v3/objects/deals`)

---

## 📋 Overview

- **Database:** PostgreSQL
- **Source:** HubSpot CRM Deals API v3 (see `api-integration.md` for the upstream API)
- **Multi-tenant:** every row carries a tenant identifier; all reads and writes are scoped by tenant
- **Scan model:** each scan produces a snapshot of deals linked to that scan job. Re-running a scan creates a new job with its own result rows, so history is preserved.
- **ETL metadata on every deal row:** `_extracted_at`, `_scan_id`, `_tenant_id`

```
scan_jobs (1) ────< hubspot_deals (many)
   id  ←──────────  scan_job_id
```

---

## 🏗️ Table Schemas

### 1. `scan_jobs`

**Purpose:** Tracks each extraction run (status, progress, configuration, errors).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | VARCHAR(36) | PRIMARY KEY | Internal UUID |
| `scan_id` | VARCHAR(100) | UNIQUE, NOT NULL | External scan identifier returned to API callers |
| `status` | VARCHAR(20) | NOT NULL, CHECK | `pending`, `running`, `completed`, `failed`, `cancelled` |
| `scan_type` | VARCHAR(50) | NOT NULL | `hubspot_deals` for this service |
| `config` | JSONB | NOT NULL | Scan parameters (properties, limit, archived flag, filters). **Never store the HubSpot access token here.** |
| `organization_id` | VARCHAR(64) | NOT NULL | Tenant identifier (same value written to `_tenant_id` on results) |
| `error_message` | TEXT | NULLABLE | Failure details |
| `started_at` | TIMESTAMPTZ | NULLABLE | Execution start |
| `completed_at` | TIMESTAMPTZ | NULLABLE | Execution end |
| `total_items` | INTEGER | DEFAULT 0 | Deals to process |
| `processed_items` | INTEGER | DEFAULT 0 | Deals stored successfully |
| `failed_items` | INTEGER | DEFAULT 0 | Deals that failed processing |
| `success_rate` | VARCHAR(10) | NULLABLE | e.g. `98.50%` |
| `batch_size` | INTEGER | DEFAULT 100 | Page size for HubSpot requests (HubSpot maximum is 100) |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Row creation |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Last update |

```sql
CREATE TABLE scan_jobs (
    id               VARCHAR(36)  PRIMARY KEY,
    scan_id          VARCHAR(100) NOT NULL UNIQUE,
    status           VARCHAR(20)  NOT NULL DEFAULT 'pending',
    scan_type        VARCHAR(50)  NOT NULL DEFAULT 'hubspot_deals',
    config           JSONB        NOT NULL DEFAULT '{}'::jsonb,
    organization_id  VARCHAR(64)  NOT NULL,
    error_message    TEXT,
    started_at       TIMESTAMPTZ,
    completed_at     TIMESTAMPTZ,
    total_items      INTEGER      NOT NULL DEFAULT 0,
    processed_items  INTEGER      NOT NULL DEFAULT 0,
    failed_items     INTEGER      NOT NULL DEFAULT 0,
    success_rate     VARCHAR(10),
    batch_size       INTEGER      NOT NULL DEFAULT 100,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT check_valid_status
        CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    CONSTRAINT check_positive_counts
        CHECK (total_items >= 0 AND processed_items >= 0 AND failed_items >= 0),
    CONSTRAINT check_batch_size
        CHECK (batch_size BETWEEN 1 AND 100)
);
```

**Indexes**

```sql
CREATE INDEX idx_scan_status_created ON scan_jobs (status, created_at);
CREATE INDEX idx_scan_org_status     ON scan_jobs (organization_id, status);
CREATE INDEX idx_scan_org_created    ON scan_jobs (organization_id, created_at DESC);
```

`scan_id` is already indexed by its UNIQUE constraint.

---

### 2. `hubspot_deals`

**Purpose:** Stores deal records extracted from HubSpot, one row per deal per scan.

#### HubSpot → PostgreSQL type mapping

HubSpot returns every value in `properties` as a string, so values must be converted when loaded.

| HubSpot property | HubSpot type | PostgreSQL column | PostgreSQL type | Notes |
|---|---|---|---|---|
| `id` / `hs_object_id` | string | `deal_id` | VARCHAR(50) | HubSpot deal ID |
| `dealname` | string | `dealname` | TEXT | |
| `amount` | number | `amount` | NUMERIC(18,2) | Empty string → NULL |
| `dealstage` | enumeration | `dealstage` | VARCHAR(100) | Internal stage ID, e.g. `contractsent` |
| `pipeline` | enumeration | `pipeline` | VARCHAR(100) | Pipeline ID, e.g. `default` |
| `closedate` | datetime | `closedate` | TIMESTAMPTZ | ISO 8601 UTC |
| `createdate` | datetime | `createdate` | TIMESTAMPTZ | |
| `hs_lastmodifieddate` | datetime | `hs_lastmodifieddate` | TIMESTAMPTZ | Used for incremental extraction |
| `hubspot_owner_id` | string | `hubspot_owner_id` | VARCHAR(50) | |
| `dealtype` | enumeration | `dealtype` | VARCHAR(50) | |
| `description` | string | `description` | TEXT | |
| `hs_priority` | enumeration | `hs_priority` | VARCHAR(50) | |
| `hs_is_closed` | boolean | `hs_is_closed` | BOOLEAN | `"true"`/`"false"` strings → boolean |
| `hs_is_closed_won` | boolean | `hs_is_closed_won` | BOOLEAN | |
| `hs_forecast_probability` | number | `hs_forecast_probability` | NUMERIC(6,4) | Fraction between 0 and 1 |
| `hs_forecast_amount` | number | `hs_forecast_amount` | NUMERIC(18,2) | |
| `archived` (top-level) | boolean | `archived` | BOOLEAN | Not inside `properties` |
| entire `properties` object | n/a | `raw_properties` | JSONB | Keeps unmapped or custom properties |

Any property that is not available in a given HubSpot account is stored as NULL. Custom properties are preserved in `raw_properties`.

#### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | VARCHAR(36) | PRIMARY KEY | Unique result row ID (UUID) |
| `scan_job_id` | VARCHAR(36) | FOREIGN KEY, NOT NULL | References `scan_jobs.id` (ON DELETE CASCADE) |
| `deal_id` | VARCHAR(50) | NOT NULL | HubSpot deal ID |
| *(deal fields)* | see mapping above | | |
| `_extracted_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | When this row was extracted |
| `_scan_id` | VARCHAR(100) | NOT NULL | External scan ID (= `scan_jobs.scan_id`) |
| `_tenant_id` | VARCHAR(64) | NOT NULL | Tenant (= `scan_jobs.organization_id`) |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Row creation |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Last update |

```sql
CREATE TABLE hubspot_deals (
    id                       VARCHAR(36)   PRIMARY KEY,
    scan_job_id              VARCHAR(36)   NOT NULL
                                 REFERENCES scan_jobs(id) ON DELETE CASCADE,

    -- HubSpot deal fields
    deal_id                  VARCHAR(50)   NOT NULL,
    dealname                 TEXT,
    amount                   NUMERIC(18,2),
    dealstage                VARCHAR(100),
    pipeline                 VARCHAR(100),
    closedate                TIMESTAMPTZ,
    createdate               TIMESTAMPTZ,
    hs_lastmodifieddate      TIMESTAMPTZ,
    hubspot_owner_id         VARCHAR(50),
    dealtype                 VARCHAR(50),
    description              TEXT,
    hs_priority              VARCHAR(50),
    hs_is_closed             BOOLEAN,
    hs_is_closed_won         BOOLEAN,
    hs_forecast_probability  NUMERIC(6,4),
    hs_forecast_amount       NUMERIC(18,2),
    archived                 BOOLEAN       NOT NULL DEFAULT FALSE,
    raw_properties           JSONB,

    -- ETL metadata
    _extracted_at            TIMESTAMPTZ   NOT NULL DEFAULT now(),
    _scan_id                 VARCHAR(100)  NOT NULL,
    _tenant_id               VARCHAR(64)   NOT NULL,

    created_at               TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ   NOT NULL DEFAULT now(),

    -- A deal appears at most once per scan
    CONSTRAINT uq_deal_per_scan UNIQUE (scan_job_id, deal_id)
);
```

**Indexes**

```sql
-- Results of a scan (also covers the foreign key)
CREATE INDEX idx_deals_scan_job        ON hubspot_deals (scan_job_id);

-- Tenant-scoped lookups
CREATE INDEX idx_deals_tenant_deal     ON hubspot_deals (_tenant_id, deal_id);
CREATE INDEX idx_deals_tenant_scan     ON hubspot_deals (_tenant_id, _scan_id);

-- Filtering by stage / pipeline
CREATE INDEX idx_deals_tenant_stage    ON hubspot_deals (_tenant_id, dealstage);
CREATE INDEX idx_deals_tenant_pipeline ON hubspot_deals (_tenant_id, pipeline, dealstage);

-- Date-range queries
CREATE INDEX idx_deals_tenant_closedate ON hubspot_deals (_tenant_id, closedate);
CREATE INDEX idx_deals_tenant_created   ON hubspot_deals (_tenant_id, createdate);
CREATE INDEX idx_deals_tenant_modified  ON hubspot_deals (_tenant_id, hs_lastmodifieddate);

-- Extraction history
CREATE INDEX idx_deals_tenant_extracted ON hubspot_deals (_tenant_id, _extracted_at DESC);

-- Optional: searching inside raw/custom properties
CREATE INDEX idx_deals_raw_properties   ON hubspot_deals USING GIN (raw_properties);
```

| Index | Reason |
|---|---|
| `_tenant_id` leading composites | Every query is tenant-scoped, so tenant is always the first column |
| `dealstage`, `pipeline` | Pipeline and stage reporting |
| `closedate`, `createdate` | Date-range filters and forecasting |
| `hs_lastmodifieddate` | Incremental extraction (deals changed since the last scan) |
| `scan_job_id` | Fetching paginated results for one scan |
| GIN on `raw_properties` | Optional, for custom-property searches |

---

## 🔗 Relationships

```sql
-- ScanJob to deals (One-to-Many)
scan_jobs.id  ←  hubspot_deals.scan_job_id
```

**Cascade behavior:** deleting a `scan_jobs` row deletes all of its `hubspot_deals` rows (`ON DELETE CASCADE`).

---

## 🏢 Multi-Tenant Data Isolation

Tenant isolation uses a **shared database, shared schema** model with a tenant column on every row.

1. **Tenant column everywhere.** `scan_jobs.organization_id` and `hubspot_deals._tenant_id` are `NOT NULL`. The service copies the scan's tenant onto every deal row it writes.
2. **Tenant-scoped queries.** Every query includes `WHERE _tenant_id = :tenant_id` (or `organization_id` on `scan_jobs`). The tenant comes from the authenticated request, never from an unvalidated client-supplied filter.
3. **Tenant-first indexes.** All composite indexes lead with `_tenant_id`, so tenant filtering is index-backed.
4. **Credential separation.** Each tenant's HubSpot token is kept in a secrets manager or environment configuration, not in the database and not in `scan_jobs.config`.
5. **Row-Level Security (defense in depth).** PostgreSQL can enforce isolation even if application code forgets a filter:

```sql
ALTER TABLE hubspot_deals ENABLE ROW LEVEL SECURITY;
ALTER TABLE scan_jobs     ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_deals ON hubspot_deals
    USING (_tenant_id = current_setting('app.tenant_id', true));

CREATE POLICY tenant_isolation_jobs ON scan_jobs
    USING (organization_id = current_setting('app.tenant_id', true));

-- Per request/transaction, the service sets the tenant:
-- SET LOCAL app.tenant_id = 'tenant_1';
```

Row-level security applies to non-owner database roles, so the application should connect with a role that is not the table owner.

6. **Consistency check.** A deal row's `_tenant_id` and `_scan_id` must match its parent job:

```sql
SELECT d.id
FROM hubspot_deals d
JOIN scan_jobs j ON j.id = d.scan_job_id
WHERE d._tenant_id <> j.organization_id OR d._scan_id <> j.scan_id;
-- Expected result: 0 rows
```

---

## 📊 Common Queries

### Scan management

```sql
-- Scan status
SELECT scan_id, status, scan_type, total_items, processed_items, error_message
FROM scan_jobs
WHERE scan_id = 'your-scan-id' AND organization_id = 'tenant_1';

-- Active scans for a tenant
SELECT scan_id, status, started_at
FROM scan_jobs
WHERE organization_id = 'tenant_1' AND status IN ('pending', 'running')
ORDER BY created_at DESC;

-- Scan progress
SELECT scan_id, total_items, processed_items,
       CASE WHEN total_items > 0
            THEN ROUND(processed_items * 100.0 / total_items, 2)
            ELSE 0 END AS progress_percentage
FROM scan_jobs
WHERE scan_id = 'your-scan-id' AND organization_id = 'tenant_1';
```

### Deal results

```sql
-- Paginated results for a scan
SELECT deal_id, dealname, amount, dealstage, pipeline, closedate
FROM hubspot_deals
WHERE _tenant_id = 'tenant_1' AND _scan_id = 'your-scan-id'
ORDER BY created_at, id
LIMIT 100 OFFSET 0;

-- Deals and total value per stage
SELECT dealstage, COUNT(*) AS deal_count, SUM(amount) AS total_amount
FROM hubspot_deals
WHERE _tenant_id = 'tenant_1' AND _scan_id = 'your-scan-id'
GROUP BY dealstage;

-- Deals closing in a date range
SELECT deal_id, dealname, amount, closedate
FROM hubspot_deals
WHERE _tenant_id = 'tenant_1'
  AND _scan_id = 'your-scan-id'
  AND closedate >= '2026-11-01' AND closedate < '2026-12-01';

-- Search by name
SELECT deal_id, dealname
FROM hubspot_deals
WHERE _tenant_id = 'tenant_1' AND _scan_id = 'your-scan-id'
  AND dealname ILIKE '%enterprise%';
```

### Control operations

```sql
-- Cancel a scan
UPDATE scan_jobs
SET status = 'cancelled',
    completed_at = now(),
    error_message = 'Cancelled by user'
WHERE scan_id = 'your-scan-id'
  AND organization_id = 'tenant_1'
  AND status IN ('pending', 'running');
```

---

## 🛠️ Implementation Examples

### Creating a scan job

```sql
INSERT INTO scan_jobs (id, scan_id, status, scan_type, config, organization_id, batch_size)
VALUES (
    'uuid-1', 'hubspot-deals-scan-001', 'pending', 'hubspot_deals',
    '{"properties": ["dealname","amount","dealstage","pipeline","closedate"], "archived": false}',
    'tenant_1', 100
);
```

### Inserting deals

```sql
INSERT INTO hubspot_deals (
    id, scan_job_id, deal_id, dealname, amount, dealstage, pipeline,
    closedate, createdate, hs_lastmodifieddate, archived, raw_properties,
    _scan_id, _tenant_id
) VALUES (
    'uuid-3', 'uuid-1', '123456', 'Enterprise Software Deal', 15000.00, 'contractsent', 'default',
    '2026-11-15T00:00:00Z', '2026-10-01T10:30:00Z', '2026-10-05T12:00:00Z', FALSE,
    '{"dealname": "Enterprise Software Deal", "amount": "15000"}',
    'hubspot-deals-scan-001', 'tenant_1'
)
ON CONFLICT (scan_job_id, deal_id) DO UPDATE
SET dealname = EXCLUDED.dealname,
    amount = EXCLUDED.amount,
    dealstage = EXCLUDED.dealstage,
    hs_lastmodifieddate = EXCLUDED.hs_lastmodifieddate,
    raw_properties = EXCLUDED.raw_properties,
    updated_at = now();
```

The `ON CONFLICT` clause makes retries and re-processed pages idempotent within a scan.

### Status updates

```sql
-- Start scan
UPDATE scan_jobs SET status = 'running', started_at = now() WHERE scan_id = 'hubspot-deals-scan-001';

-- Update progress after each page
UPDATE scan_jobs
SET processed_items = processed_items + 100
WHERE scan_id = 'hubspot-deals-scan-001';

-- Complete scan
UPDATE scan_jobs
SET status = 'completed',
    completed_at = now(),
    success_rate = CASE WHEN total_items > 0
        THEN ROUND((total_items - failed_items) * 100.0 / total_items, 2)::TEXT || '%'
        ELSE '100%' END
WHERE scan_id = 'hubspot-deals-scan-001';
```

### Latest known state of each deal (optional view)

```sql
CREATE VIEW latest_hubspot_deals AS
SELECT DISTINCT ON (_tenant_id, deal_id) *
FROM hubspot_deals
ORDER BY _tenant_id, deal_id, _extracted_at DESC;
```

---

## 📈 Performance Considerations

- **Batch inserts:** insert one HubSpot page (up to 100 deals) per statement or use `COPY` for large volumes.
- **Incremental extraction:** filter on `hs_lastmodifieddate` to avoid re-fetching unchanged deals.
- **Pagination:** use keyset pagination (`WHERE (created_at, id) > (...)`) for very large result sets instead of large `OFFSET` values.
- **Partitioning (very large datasets):** `hubspot_deals` can be hash-partitioned by `_tenant_id`. Note that PostgreSQL then requires the partition key to be part of the primary key.
- **Retention:** archive or delete completed scans after 90 days; the cascade removes their deals.

```sql
DELETE FROM scan_jobs
WHERE status = 'completed'
  AND completed_at < now() - INTERVAL '90 days';
```

---

## 🛡️ Data Integrity

### Auto-updating timestamps

```sql
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_scan_jobs_updated_at
    BEFORE UPDATE ON scan_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_hubspot_deals_updated_at
    BEFORE UPDATE ON hubspot_deals
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

### Status transitions

`pending → running → completed | failed | cancelled` (a scan may also move from `pending` directly to `cancelled`).

---

## ✅ Best Practices

1. Convert HubSpot string values to proper types on load, treating empty strings as NULL.
2. Always write `_tenant_id`, `_scan_id`, and `_extracted_at` on every deal row.
3. Store errors in `scan_jobs.error_message` and never include tokens in them.
4. Keep `raw_properties` so schema changes in HubSpot don't lose data.
5. Never store HubSpot access tokens in the database.

---

**Database Schema Version**: 1.0.0
**Last Updated**: 2026-10-10
**Target Database**: PostgreSQL 13+