# Contributing to Speaker

Speaker is an open-source CLI and schema layer for a hosted professional graph.

The mesh grows when people add useful schemas, safe query recipes, agent workflows, and public datasets that connect to the graph.

## Good contributions

- schema fixes and clearer column descriptions
- safe query examples and agent workflows
- integrations for Claude, Codex, Pi, MCP, or other harnesses
- public datasets that connect through `person_id`, `entity_id`, or `domain`
- docs that make ClickHouse access patterns clearer

## Contributing a table

1. Fork the repo.
2. Copy `contrib/_template/` to `contrib/your-table/`.
3. Fill in `main.yaml`.
4. Add a reproducible pipeline if the table is meant to be built from public data.
5. Open a PR.

## Table rules

- **Must connect.** At least one column should connect to `people.nucleus.person_id`, `companies.nucleus.entity_id`, or `web.domain_entity_bridge.domain`.
- **Public source.** Contributed data pipelines should build from data others can access.
- **Reproducible.** Another contributor should be able to run the pipeline and understand the result.
- **Agent-readable.** Prefer clear names, simple types, and explicit graph keys.
- **Safe.** Do not include secrets, private/provenance-only fields, or data that cannot be redistributed.

## Table ideas

| Table idea | Connects via | Source |
|---|---|---|
| Conference speakers | `person_id`, `domain` | Public conference sites |
| Patents | `person_id`, `entity_id` | USPTO / EPO |
| Research papers | `person_id`, `domain` | Semantic Scholar / arXiv |
| Regulatory filings | `entity_id`, `domain` | Public registries |
| Podcast appearances | `person_id`, `domain` | Public RSS feeds |
| Open-source projects | `person_id`, `domain` | Public code hosts |

The best tables are ones you need. Build it for yourself; the mesh makes it useful for everyone.
