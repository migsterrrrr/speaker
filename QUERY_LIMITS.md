# Query Limits

Speaker queries run through a public API proxy in front of ClickHouse. The proxy is intentionally permissive enough for exploratory SQL, but bounded so one expensive query does not keep running forever after a client disconnects.

## Public API behavior

The proxy accepts read-only SQL against the public logical databases:

```text
people.*
companies.*
web.*
```

Direct access to internal databases is blocked by the proxy.

The proxy also:

- accepts `SELECT` / `DESCRIBE` style queries only
- appends `FORMAT JSONEachRow` to query responses
- caps returned rows at `100,000`
- injects `LIMIT 100000` if a `SELECT` has no limit
- waits up to `60s` for ClickHouse before returning an API timeout/error

Important: the row cap limits returned rows, not rows scanned. A query with `LIMIT 20` can still be expensive if it scans a huge table.

## ClickHouse execution limits

The public ClickHouse reader role is configured with server-side limits so ClickHouse cancels expensive API queries before the proxy times out.

Effective behavior:

```text
readonly = 1
max_execution_time = 50
timeout_before_checking_execution_speed = 0
timeout_overflow_mode = throw
cancel_http_readonly_queries_on_client_close = 1
max_concurrent_queries_for_user = 8
```

What these mean:

| Setting | Value | Purpose |
|---|---:|---|
| `readonly` | `1` | Public API user can only read. |
| `max_execution_time` | `50` | ClickHouse should stop long-running queries before the proxy's 60s timeout. |
| `timeout_before_checking_execution_speed` | `0` | Makes `max_execution_time` use wall-clock style timing instead of delayed speed estimation. |
| `timeout_overflow_mode` | `throw` | Timeout returns an error instead of partial results. |
| `cancel_http_readonly_queries_on_client_close` | `1` | If the API/proxy/client disconnects, ClickHouse cancels the running read query instead of continuing in the background. |
| `max_concurrent_queries_for_user` | `8` | Limits concurrent public API ClickHouse queries for the shared reader user. |

## Why ClickHouse timeout is 50s, not 60s

The API/proxy timeout is 60s. ClickHouse is set lower at 50s so the database fails first and returns a clean timeout to the proxy.

If ClickHouse were also set to 60s, the proxy might give up first. That can produce confusing client errors and, without client-close cancellation, may leave ClickHouse work running after the user has already disconnected.

## Query patterns to avoid

These are likely to timeout or put heavy load on the system:

```sql
-- Full text scan over the web corpus
SELECT *
FROM web.pages
WHERE lower(text) LIKE '%some broad phrase%'
LIMIT 20;

-- Filtering a huge people table on a non-primary-key field
SELECT *
FROM people.nucleus
WHERE current_company_id = '...'
LIMIT 100;

-- Large joins before narrowing to a small ID set
SELECT *
FROM people.roles_history r
LEFT JOIN people.nucleus p ON p.person_id = r.person_id
WHERE r.speaker_company_id = '...';
```

Prefer narrowing first using indexed/serving-friendly fields, exact IDs, domains, or small `IN (...)` lists. Carry IDs between steps rather than doing broad joins across billion-row tables.

## Operational notes

If users report slow or stuck queries, operators should inspect active ClickHouse queries for the public reader role and confirm no old work is still running after client timeouts.

The key safety invariant is:

```text
ClickHouse query timeout < proxy timeout
```

Current intended values:

```text
ClickHouse max_execution_time: 50s
Proxy ClickHouse request timeout: 60s
```
