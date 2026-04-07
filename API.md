# Speaker API

HTTP API for the Speaker mesh. Use this to build MCP servers, CLIs, integrations.

**Base URL:** `https://api.speaker.sh`

---

## Authentication

All query endpoints require an API key in the `X-API-Key` header.

```bash
curl https://api.speaker.sh/query \
  -H "X-API-Key: sk-xxxxx" \
  -d "SELECT count() FROM people.main"
```

Get an API key via `/signup` with an invite code (see below).

---

## Endpoints

### `GET /health`

Public. No auth. Use for health checks.

```bash
curl https://api.speaker.sh/health
```

Response:
```json
{"status":"ok","people":"818M","companies":"3.7M","tables":10,"version":"3.0.0"}
```

---

### `POST /query`

Execute a SQL query against the mesh.

**Request:**
- Method: `POST`
- Headers: `X-API-Key: sk-xxxxx`
- Body: raw SQL (plain text, not JSON)

**Response:**
- Content-Type: `application/x-ndjson`
- Body: one JSON object per line (JSONEachRow)

```bash
curl https://api.speaker.sh/query \
  -H "X-API-Key: sk-xxxxx" \
  -d "SELECT first, last, title, org FROM people.main WHERE country = 'uk' AND seniority = 'c_suite' LIMIT 3"
```

Response:
```
{"first":"Jane","last":"Doe","title":"CEO","org":"Stripe"}
{"first":"John","last":"Smith","title":"CTO","org":"Monzo"}
{"first":"Sarah","last":"Lee","title":"Founder","org":"Wise"}
```

**Supported SQL:**
- `SELECT` queries on any allowed table
- `DESCRIBE database.table` (returns schema)
- Subqueries with `IN (SELECT ...)`
- Aggregations: `count()`, `GROUP BY`, `ORDER BY`, etc.
- Array functions: `has()`, `hasAny()`, `arrayJoin()`, etc.

**Restrictions:**
- Only `SELECT` and `DESCRIBE` statements
- Must use `database.table` format (e.g. `people.main`, not `main`)
- Max 100,000 rows returned per query
- Query timeout: 60 seconds
- Rate limit: 20 queries/second per API key
- No daily limit

**Errors:**
- `400` — SQL syntax error, no database prefix, or blocked statement
- `401` — Missing or invalid API key
- `403` — Database not allowed (only `people`, `companies`, `web`)
- `429` — Rate limit exceeded (20 queries/sec)
- `502` — Database unavailable

---

### `GET /schema`

Returns mesh schema. Requires API key.

```bash
curl https://api.speaker.sh/schema -H "X-API-Key: sk-xxxxx"
```

Response:
```json
{
  "mesh": {
    "people.main":      {"rows": "818M", "description": "Identity, role, skills, education, scores"},
    "people.career":    {"rows": "974M", "description": "Full role history"},
    "people.education": {"rows": "333M", "description": "Schools, degrees, fields of study"},
    "people.contact":   {"rows": "863M", "description": "LinkedIn, email, Twitter, GitHub, website"},
    "people.repos":     {"rows": "40M",  "description": "GitHub repositories"},
    "companies.main":   {"rows": "3.7M", "description": "AI-synthesized company profiles"},
    "companies.jobs":   {"rows": "755K", "description": "Active job postings"},
    "companies.news":   {"rows": "19M",  "description": "News articles"},
    "web.links":        {"rows": "56M",  "description": "Domain-to-domain link graph"},
    "web.pages":        {"rows": "1.3B", "description": "Company web pages (always filter by domain)"}
  },
  "notes": "Use DESCRIBE database.table for full column list. Hops not JOINs. Carry IDs between queries."
}
```

For full column schemas of each table, see `tables/*.yaml` in the repo, or use `DESCRIBE database.table` at query time.

---

### `POST /signup`

Create a new account with an invite code.

**Request:**
```bash
curl https://api.speaker.sh/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "invite_code": "INV-xxxxx"}'
```

**Response:**
```json
{"status": "active", "email": "you@example.com", "api_key": "sk-xxxxx"}
```

Store the `api_key` — it's the only credential you need going forward.

---

### `POST /login`

Alternative auth (email + password). Most users use API key directly.

```bash
curl https://api.speaker.sh/login \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "xxx"}'
```

Response:
```json
{"api_key": "sk-xxxxx", "email": "you@example.com"}
```

---

## Tables

The mesh has 10 tables across 3 databases.

### people.*

| Table | Rows | Key columns |
|---|---|---|
| `people.main` | 818M | speaker_person_id, first, last, country, title, org, entity_id, seniority, technologies[], domain_knowledge[], credentials[], languages[], highest_degree, school, influencer_score, depth |
| `people.career` | 974M | person_id, title, start, end, org_name, entity_id, org_domain, roles_context, location |
| `people.education` | 333M | speaker_person_id, school, degree, degree_level, field_of_study, start, end |
| `people.contact` | 863M | speaker_person_id, linkedin_slug, email_work, twitter, github, website |
| `people.repos` | 40M | speaker_person_id, owner, repo, language, description, stars, forks, license, created_at |

### companies.*

| Table | Rows | Key columns |
|---|---|---|
| `companies.main` | 3.7M | entity_id, name, summary, keywords[], offerings[], market, headcount, size, founded, country, city, website, reputation |
| `companies.jobs` | 755K | entity_id, domain, title, category, description, location, date_added |
| `companies.news` | 19M | entity_id, domain, title, publisher, published_date, url |

### web.*

| Table | Rows | Key columns |
|---|---|---|
| `web.links` | 56M | source_entity_id, source_domain, target_domain, page_count |
| `web.pages` | 1.3B (view) | domain, url, title, text, headings, emails, phones, tools, lang |

---

## Join keys

```
people.main.speaker_person_id
  ← people.career.person_id
  ← people.education.speaker_person_id
  ← people.contact.speaker_person_id
  ← people.repos.speaker_person_id

companies.main.entity_id
  ← people.main.entity_id            (16% fill)
  ← people.career.entity_id
  ← web.links.source_entity_id

companies.main.website (domain)
  ← companies.jobs.domain
  ← companies.news.domain
  ← web.links.source_domain / target_domain
  ← web.pages.domain
```

**Pattern:** hops not JOINs. Query one table, collect IDs, query the next table with `WHERE id IN (...)`. Two fast lookups beat one expensive JOIN.

---

## Query patterns

### Find people at a company (2 hops)
```sql
-- Hop 1: get entity_id from company
SELECT entity_id, name FROM companies.main WHERE website = 'stripe.com';

-- Hop 2: get people at that company
SELECT first, last, title FROM people.main
WHERE entity_id = 'spk_xxx' AND seniority IN ('c_suite', 'vp', 'director')
ORDER BY influencer_score DESC LIMIT 20;
```

### Full person profile (5 queries)
```sql
-- Identity + skills
SELECT * FROM people.main WHERE speaker_person_id = 'spkp_xxx';

-- Career history
SELECT title, org_name, start, end FROM people.career
WHERE person_id = 'spkp_xxx' ORDER BY start DESC;

-- Education
SELECT school, degree_level, field_of_study FROM people.education
WHERE speaker_person_id = 'spkp_xxx';

-- Contact
SELECT linkedin_slug, email_work, twitter, github FROM people.contact
WHERE speaker_person_id = 'spkp_xxx';

-- GitHub repos (if they have a github username)
SELECT owner, repo, language, stars FROM people.repos
WHERE speaker_person_id = 'spkp_xxx' AND stars > 0 ORDER BY stars DESC;
```

### Talent flow (3 hops)
```sql
-- Hop 1: who worked at X
SELECT DISTINCT person_id FROM people.career
WHERE entity_id = 'spk_xxx' AND end IS NOT NULL;

-- Hop 2: where are they now
SELECT first, last, org, entity_id FROM people.main
WHERE speaker_person_id IN ('spkp_1', 'spkp_2', ...);

-- Hop 3: profile their new companies
SELECT name, headcount, market FROM companies.main
WHERE entity_id IN ('spk_1', 'spk_2', ...);
```

### Competitive landscape via web links
```sql
-- Who links to X
SELECT source_domain, page_count FROM web.links
WHERE target_domain = 'stripe.com' ORDER BY page_count DESC LIMIT 20;

-- Sites that link to BOTH X and Y (shared context)
SELECT source_domain FROM web.links
WHERE target_domain = 'stripe.com'
  AND source_domain IN (
    SELECT source_domain FROM web.links WHERE target_domain = 'adyen.com'
  );
```

---

## Quirks

- Country codes: `people.main` uses `'uk'` for United Kingdom, `companies.main` uses `'gb'`. Check which table.
- `people.main.entity_id` only 16% fill — filter `WHERE entity_id != ''` when you need the company link.
- `web.pages` is a view over 1.3B rows — **always filter by domain first**, never scan without a domain filter.
- `company_name` queries are ambiguous — always resolve to `entity_id` first via `companies.main`.

---

## Example: complete agent integration (pseudocode)

```python
import httpx

API_KEY = "sk-xxxxx"
BASE = "https://api.speaker.sh"

def query(sql: str) -> list[dict]:
    resp = httpx.post(
        f"{BASE}/query",
        headers={"X-API-Key": API_KEY},
        content=sql,
        timeout=60.0,
    )
    resp.raise_for_status()
    return [json.loads(line) for line in resp.text.strip().split("\n") if line]

# Find Stripe
company = query("SELECT entity_id, name FROM companies.main WHERE website = 'stripe.com'")[0]

# Get CTOs there
people = query(f"""
    SELECT speaker_person_id, first, last, title
    FROM people.main
    WHERE entity_id = '{company['entity_id']}'
      AND title ILIKE '%CTO%'
    LIMIT 5
""")

# Enrich with contact info
for p in people:
    contact = query(f"""
        SELECT linkedin_slug, email_work
        FROM people.contact
        WHERE speaker_person_id = '{p['speaker_person_id']}'
    """)
    if contact:
        p['linkedin'] = contact[0].get('linkedin_slug')
        p['email'] = contact[0].get('email_work')

print(people)
```

---

## Philosophy

```
more queries = more signal
```

- No daily limit. Fire as many queries as you need.
- No cost per query.
- The insight is never in one table — it's in the connections.
- Start broad, drill, hop, notice, hop again. Curiosity compounds.

---

## Support

- GitHub: https://github.com/migsterrrrr/speaker
- Schemas: https://github.com/migsterrrrr/speaker/tree/master/tables
- Agent skill: https://github.com/migsterrrrr/speaker/blob/master/SKILL.md
