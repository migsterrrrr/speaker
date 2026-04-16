# Speaker

Root access for agents to the world's professional information.

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

People. Companies. Connected by career moves, skills, education, web links, code, news. Enter anywhere.

## Use it

```bash
# Install
# Uses /usr/local/bin if writable, otherwise falls back to ~/.local/bin
curl -sL https://raw.githubusercontent.com/migsterrrrr/speaker/master/cli/install.sh | sh

# Install to a custom prefix (npm-style: PREFIX/bin)
curl -sL https://raw.githubusercontent.com/migsterrrrr/speaker/master/cli/install.sh | PREFIX="$HOME/.local" sh

# Install to an exact bin dir
curl -sL https://raw.githubusercontent.com/migsterrrrr/speaker/master/cli/install.sh | BINDIR="$HOME/bin" sh

# Pi
pi install git:github.com/migsterrrrr/speaker
```

## The mesh

```
👤 people.main          📋 people.career        🎓 people.education
📡 people.contact       ⚡ people.repos

🏢 companies.main       💼 companies.jobs        📰 companies.news

🕸️ web.links             📄 web.pages
```

Every edge is a hop. Carry IDs between queries. The insight is never in one table — it's in the connections.

## Schema

Curated schema docs:

```bash
speaker schema
speaker schema people.main
speaker schema --all
```

Human overview:

```bash
speaker mesh
```

Raw DB metadata:

```bash
speaker query "DESCRIBE people.main"
```

## Open data

The two nuclei (`people.main`, `companies.main`) are proprietary and hosted.
Everything else is open — [schemas](tables/), [pipelines](pipelines/).

## Contribute

Add a table to the mesh. See [CONTRIBUTING.md](CONTRIBUTING.md).

```
1. Fork → 2. Add schema + pipeline → 3. PR → 4. Your table joins the mesh
```

The best tables are ones you need. Build it for yourself. The mesh makes it valuable for everyone.

## Philosophy

The insight is never in one table — it's in the connections.
Contribute selfishly, benefit collectively.

more queries = more signal
