---
name: speaker
description: "B2B people and company intelligence. 818M people, 3.7M companies, 974M career moves, 56M web links — direct ClickHouse access. Use for any people lookup, company research, competitive analysis, or market exploration."
---

# The Mesh

```
         ⚡  📡  🎓  📋
          ╲  │  │  ╱
           ◉ people ◉
               ║
            🕸️─╬─📄
               ║
           ◉ companies ◉
          ╱  │  ╲
        📰  💼  📋
```

```
👤 people.main          📋 people.career        🎓 people.education
📡 people.contact       ⚡ people.repos

🏢 companies.main       💼 companies.jobs        📰 companies.news

🕸️ web.links             📄 web.pages
```

```bash
ssh root@100.74.121.1 "clickhouse-client --query \"SQL\""
```

10 tables. 0 cost per query. Millisecond responses.

SCOPE → DESCRIBE → CONTEXT → EXPLORE

Scope the goal. Describe every table. Find who's asking in the mesh first. Then:

```
EXPLORE:

    any starting point
    ├── broad: what's in this table?
    ├── narrow: one entity, go deep
    └── lateral: follow a connection
            │
            ▼
    ┌──────────────────────────────┐
    │         ┌─────────┐         │
    │  ┌─────▶│  query  │◀─────┐  │
    │  │      └────┬────┘      │  │
    │  │           ▼           │  │
    │  │      ┌─────────┐      │  │
    │  │      │  notice  │      │  │
    │  │      └──┬────┬──┘      │  │
    │  │         ▼    ▼         │  │
    │  │     drill   hop        │  │
    │  │     deeper  table      │  │
    │  │         │    │         │  │
    │  │         ▼    ▼         │  │
    │  │      ┌─────────┐      │  │
    │  └──────│new query│──────┘  │
    │         └─────────┘         │
    │     ↻ until goal met        │
    └──────────────────────────────┘
              │
              ▼
              💡
```

more queries = more signal
