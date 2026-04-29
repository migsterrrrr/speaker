# Speaker API

HTTP API for Speaker: SQL-native professional intelligence for agents.

Agents use the API in a loop: write SQL, read JSON rows, carry `person_id`, `entity_id`, or `domain`, then query the next table.

**Base URL:** `https://api.speaker.sh`

---

## Authentication

Query endpoints require an API key in the `X-API-Key` header.

```bash
curl https://api.speaker.sh/query \
  -H "X-API-Key: sk-xxxxx" \
  -d "SELECT count() FROM people.nucleus"
```

Get an API key via `/signup` with an invite code.

---

## Endpoints

### `GET /health`

Public health check.

```bash
curl https://api.speaker.sh/health
```

Response:

```json
{"status":"ok","people":"825M","companies":"26M","tables":16,"version":"3.1.0"}
```

### `POST /query`

Execute SQL against the public Speaker graph.

**Request**

- Method: `POST`
- Header: `X-API-Key: sk-xxxxx`
- Body: raw SQL text, not JSON

**Response**

- Content-Type: `application/x-ndjson`
- Body: one JSON object per line (`JSONEachRow`)

```bash
curl https://api.speaker.sh/query \
  -H "X-API-Key: sk-xxxxx" \
  -d "SELECT entity_id, name, website FROM companies.nucleus LIMIT 3"
```

Supported:

- `SELECT`
- `DESCRIBE database.table`
- subqueries, aggregations, array functions, `ORDER BY`, `GROUP BY`

Restrictions:

- `SELECT`/`DESCRIBE` only
- database-qualified names required, e.g. `people.nucleus`
- allowed databases: `people`, `companies`, `web`
- max returned rows: 100,000
- server-side query timeout: about 50 seconds
- API/proxy timeout: about 60 seconds
- rate limit: 20 queries/second per API key
- no daily query limit

Errors:

- `400` — SQL syntax error, blocked statement, or query/resource failure
- `401` — missing or invalid API key
- `403` — database/table/function access denied
- `429` — rate limit exceeded
- `502` — database unavailable

### `GET /schema`

Returns the public graph table list. Requires API key.

```bash
curl https://api.speaker.sh/schema -H "X-API-Key: sk-xxxxx"
```

Response shape:

```json
{
  "mesh": {
    "people.nucleus": {"rows": "825M", "description": "Source of truth for professional people"},
    "companies.nucleus": {"rows": "26M", "description": "Source of truth for companies/entities"},
    "web.pages": {"rows": "1.3B", "description": "Crawled page evidence; filter by domain"}
  },
  "notes": "Use DESCRIBE database.table for full column list. Hops, not broad joins. Carry person_id, entity_id, or domain between queries."
}
```

For full column schemas with graph keys and ClickHouse access notes, use:

```bash
speaker schema
speaker schema people.nucleus
speaker schema companies.nucleus
speaker schema web.pages
```

or inspect the repo's [`tables/`](tables/) directory.

### `POST /signup`

Create an account with an invite code.

```bash
curl https://api.speaker.sh/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "invite_code": "INV-xxxxx"}'
```

Response:

```json
{"status":"active","email":"you@example.com","api_key":"sk-xxxxx"}
```

Store the API key; it is the credential used by the CLI and agents.

### `POST /login`

Legacy email/password login. Most users should use `speaker login <api-key>`.

```bash
curl https://api.speaker.sh/login \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "xxx"}'
```

---

## Public tables

### people.*

| Table | Rows | Key | Purpose |
|---|---:|---|---|
| `people.nucleus` | 825M | `person_id` | source of truth for professional people |
| `people.contacts` | 825M | `person_id` | contact and social handles |
| `people.roles_history` | 989M | `person_id`, `speaker_role_id` | one row per career role |
| `people.education` | 333M | `person_id`, `edu_id` | education records |
| `people.repos` | 40M | `owner`, `repo`; optional `person_id` | GitHub repositories |

### companies.*

| Table | Rows | Key | Purpose |
|---|---:|---|---|
| `companies.nucleus` | 26M | `entity_id` | source of truth for companies/entities |
| `companies.identifiers` | 26M | `entity_id` | website/social/profile identifiers |
| `companies.metrics` | 26M | `entity_id` | numeric growth and business metrics |
| `companies.industry_keywords` | 23M | `entity_id` | taxonomy and facet signals |
| `companies.jobs` | 839K | `entity_id`, `job_id` | job postings and hiring signal |
| `companies.posts` | 22.8M | `entity_id`, `post_id` | news/article mentions |
| `companies.competitors` | 59M | `entity_id`, `competitor_domain` | competitor-domain edges |
| `companies.funding_rounds` | 617K | `entity_id`, `funding_round_id` | funding rounds |
| `companies.web_outlinks` | 1.49B | `source_entity_id`, `source_url` | page-level external outlinks |

### web.*

| Table | Rows | Key | Purpose |
|---|---:|---|---|
| `web.domain_entity_bridge` | 16.5M | `domain` | domain → `entity_id` resolver |
| `web.pages` | 1.3B | `domain`, `url` | crawled page evidence |

---

## Graph keys

```text
person_id  → people.nucleus, people.contacts, people.roles_history, people.education, people.repos
entity_id  → companies.nucleus and company sidecars; people current/role company ids; resolved web pages
domain     → web.domain_entity_bridge, web.pages, company websites, outlink/competitor domains
```

Core rule:

```text
hops, not broad joins
```

A graph-valid edge is not automatically a fast ClickHouse lookup. Prefer exact key lookups and left-prefix `ORDER BY` access patterns documented in `speaker schema <table>`.

---

## Security model

The proxy is intentionally small:

- API key auth
- `SELECT`/`DESCRIBE` only
- public logical databases only: `people`, `companies`, `web`
- direct internal databases are not exposed
- dangerous table functions and server fingerprinting functions are blocked
- results are capped and public reader queries time out before the API path does

---

## CLI

Most users should use the CLI:

```bash
speaker login <api-key>
speaker query "SELECT count() FROM companies.nucleus"
speaker schema companies.nucleus
```
