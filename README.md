# EPL SQL Agent

A small agentic AI project: ask questions about the Premier League in
plain English, and an LLM agent writes and runs the SQL against a local
SQLite database, then explains the result.

This is the same `epl_2025-26.db` database from my
[EPL SQL project](https://github.com/VPraja92/EPL_26_27_-SQL-Project),
now wrapped with an agent layer that can reason about the schema and
query it on demand instead of running fixed, hand-written queries.

## Why this exists

Most of my earlier data projects run a fixed script against a fixed
query. This one is agentic in the actual sense: the model decides
*which* tool to call and *what* SQL to write based on the question,
inspects its own results, and can ask a clarifying question if the
request is ambiguous -- rather than me writing every query in advance.

## How it works

```
You ask a question
        |
        v
Claude decides: "I need the schema first" -> calls get_schema()
        |
        v
Claude writes a SELECT statement -> calls run_query()
        |
        v
db_tools.py validates it's read-only, runs it, returns rows
        |
        v
Claude explains the result in plain English
```

Two tools, defined in `src/db_tools.py`:

- **`get_schema`** -- lists every table and column so the model never
  has to guess a column name.
- **`run_query`** -- runs a single `SELECT` statement. Anything that
  isn't a plain SELECT (INSERT, DROP, ATTACH, stacked statements,
  etc.) is rejected before it reaches the database, and results are
  capped at 200 rows so one bad query can't dump the whole table.

The agent loop itself lives in `src/agent.py`. It's a plain
`while True` loop: send the conversation to Claude, and if the
response asks for a tool, run it and feed the result back in; if it's
a text answer, return it. That loop is the whole "agentic" part --
everything else is plumbing.

## Setup

```bash
cd epl-sql-agent
pip install -r requirements.txt
cp .env.example .env
# edit .env: add your ANTHROPIC_API_KEY, and point EPL_DB_PATH at
# your actual epl_2025-26.db (copy it into data/, or update the path)
```

## Run it

```bash
cd src
python cli.py
```

```
You: Who scored the most goals for Arsenal this season?
Agent: [checks schema, queries, answers with the actual player and goal count]

You: How does that compare to last season?
Agent: [asks a clarifying question if the DB only covers one season,
        or answers if it doesn't]
```

## Design notes / talking points

- **Read-only by construction, not by prompt instruction.** The system
  prompt tells Claude to only use SELECT, but `db_tools.py` enforces it
  regardless -- a regex check rejects anything else before it touches
  `sqlite3`. Prompt instructions are not a security boundary; the code
  is.
- **Schema discovery over hardcoding.** The agent doesn't have the
  schema baked into the prompt -- it calls `get_schema` itself. That
  means this same code works against any SQLite database, not just
  this one.
- **Multi-turn tool loop.** A single question can trigger more than
  one tool call (schema, then query, then maybe a follow-up query) --
  the `while True` loop in `agent.py` keeps going until Claude returns
  a plain-text answer instead of a tool request.

## Stretch goals

- **Expose this as an MCP server** instead of a standalone CLI, so any
  MCP client (Claude Desktop, Claude Code, etc.) can query the EPL
  database directly as a tool -- same `db_tools.py`, a different
  wrapper on top.
- **Add a Streamlit chat UI** for a two-minute interview demo instead
  of a terminal.
- **Swap providers.** `db_tools.py` has no Anthropic-specific code in
  it -- pointing this at OpenAI function calling or a local model via
  Ollama would mean rewriting `agent.py` only.

## Project structure

```
epl-sql-agent/
├── README.md
├── requirements.txt
├── .env.example
├── data/                  # put epl_2025-26.db here
└── src/
    ├── db_tools.py        # schema introspection + safe query execution
    ├── agent.py           # the agent loop (Anthropic tool calling)
    └── cli.py             # terminal chat interface
```
