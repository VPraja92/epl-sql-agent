"""
agent.py

The actual "agentic" part: a loop that lets Claude decide when to call
get_schema / run_query, look at the results, and either call another
tool or answer in plain English.

Swap-out note: this uses the Anthropic API because that's the
ecosystem you already have a cert in, but the db_tools functions are
provider-agnostic. Pointing this at OpenAI's function calling or a
local Ollama model that supports tool use would mean rewriting this
file only -- db_tools.py doesn't change.
"""

import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv

from db_tools import get_schema, run_query

load_dotenv()

MODEL = "claude-sonnet-4-6"
DB_PATH = os.environ.get("EPL_DB_PATH", "./data/epl_2025-26.db")

SYSTEM_PROMPT = f"""You are a data analyst assistant for an English Premier
League SQLite database at {DB_PATH}.

Rules:
- Call get_schema first if you haven't already seen the schema this session.
- Only use run_query with SELECT statements. Never guess column or table
  names -- check the schema first.
- If a query returns nothing, say so plainly rather than making up numbers.
- Explain results in a sentence or two of plain English, not just a raw
  table dump. Mention the actual numbers.
- If a question is ambiguous (e.g. "best team" -- by what metric?), ask
  a brief clarifying question instead of guessing.
"""

TOOLS = [
    {
        "name": "get_schema",
        "description": (
            "Get the list of tables and columns in the EPL database. "
            "Call this before writing any SQL if you don't already know "
            "the schema."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "run_query",
        "description": (
            "Run a read-only SELECT query against the EPL database and "
            "get back the results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "A single SELECT statement.",
                }
            },
            "required": ["sql"],
        },
    },
]


class EPLAgent:
    def __init__(self, db_path: str = DB_PATH):
        self.client = Anthropic()  # reads ANTHROPIC_API_KEY from env
        self.db_path = db_path
        self.history: list[dict] = []

    def _call_tool(self, name: str, tool_input: dict) -> str:
        if name == "get_schema":
            result = get_schema(self.db_path)
        elif name == "run_query":
            result = run_query(self.db_path, tool_input["sql"])
        else:
            result = {"error": f"Unknown tool: {name}"}

        return result if isinstance(result, str) else json.dumps(result)

    def ask(self, user_message: str) -> str:
        """Send one user turn through the agent loop and return the
        final plain-English answer. Conversation history persists
        across calls so follow-up questions work."""
        self.history.append({"role": "user", "content": user_message})

        while True:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=self.history,
            )

            self.history.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                # Model gave a final text answer -- we're done this turn.
                return "".join(
                    block.text for block in response.content if block.type == "text"
                )

            # Otherwise, execute every tool call the model asked for and
            # feed the results back in, then loop again.
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    output = self._call_tool(block.name, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": output,
                        }
                    )

            self.history.append({"role": "user", "content": tool_results})
