"""LangChain tool-calling agent for natural language chess analytics queries."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CHROMA_DIR = ROOT / "data" / "agent" / "chroma"
COLLECTION_NAME = "chess_knowledge"

_SCHEMA = """
DuckDB tables available (all data from Lichess December 2016, 9.4M games):

analytics.opening_stats
  eco_code VARCHAR, opening_family VARCHAR, elo_bucket VARCHAR,
  time_control_type VARCHAR, year BIGINT, games_count BIGINT,
  white_win_rate DOUBLE, black_win_rate DOUBLE, draw_rate DOUBLE,
  avg_game_length DOUBLE, most_common_response VARCHAR

analytics.player_profiles
  player VARCHAR, year BIGINT, month BIGINT, games_played BIGINT,
  wins BIGINT, losses BIGINT, draws BIGINT, win_rate DOUBLE,
  avg_elo DOUBLE, elo_change INTEGER,
  most_played_opening_white VARCHAR, most_played_opening_black VARCHAR

analytics.time_pressure
  time_remaining_bucket VARCHAR, game_phase VARCHAR, time_control_type VARCHAR,
  year INTEGER, games_count INTEGER, evaluated_positions BIGINT,
  blunder_count BIGINT, avg_cp_loss DOUBLE, blunder_rate DOUBLE

analytics.blunder_positions
  game_id VARCHAR, ply_number INTEGER, fen VARCHAR, move_uci VARCHAR,
  square VARCHAR, game_phase VARCHAR, time_control_type VARCHAR, year INTEGER,
  player_elo INTEGER, time_remaining_seconds INTEGER, material_balance INTEGER,
  is_in_check BOOLEAN, eval_before_cp INTEGER, eval_after_cp INTEGER,
  cp_loss INTEGER, is_blunder BOOLEAN
"""

_SYSTEM = (
    "You are a chess analytics assistant for KnightVision, a data engineering platform "
    "processing 9.4 million Lichess games from December 2016.\n\n"
    f"{_SCHEMA}\n"
    "Rules:\n"
    "- Use search_chess_knowledge for chess concepts, opening explanations, and factual questions.\n"
    "- Use query_analytics for specific counts, rankings, win rates, and player lookups.\n"
    "- Only run SELECT queries. Return concise, factual answers. Cite numbers when available."
)


def _get_collection():
    if not CHROMA_DIR.exists():
        return None
    try:
        import chromadb

        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        return client.get_collection(COLLECTION_NAME)
    except Exception:
        return None


def build_agent(duckdb_path: str):
    from langchain.agents import AgentExecutor, create_tool_calling_agent
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain_core.tools import tool

    collection = _get_collection()

    @tool
    def search_chess_knowledge(query: str) -> str:
        """Search the chess knowledge base for opening explanations, chess concepts, and player profiles."""
        if collection is None:
            return "Knowledge base index not found. Run `make build-agent-index` first."
        results = collection.query(query_texts=[query], n_results=6)
        docs = results.get("documents", [[]])[0]
        return "\n\n".join(docs) if docs else "No relevant results found."

    @tool
    def query_analytics(sql: str) -> str:
        """Execute a SELECT query against the KnightVision DuckDB warehouse for analytics data."""
        import duckdb

        stripped = sql.strip()
        if not stripped.upper().startswith("SELECT"):
            return "Error: only SELECT queries are permitted."
        try:
            con = duckdb.connect(duckdb_path, read_only=True)
            df = con.execute(stripped).fetchdf()
            con.close()
            if df.empty:
                return "Query returned no rows."
            return df.to_string(index=False, max_rows=25)
        except Exception as e:
            return f"Query error: {e}"

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _SYSTEM),
            MessagesPlaceholder("chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )

    llm = ChatGoogleGenerativeAI(
        model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        google_api_key=os.environ.get("GOOGLE_API_KEY", ""),
        max_output_tokens=1024,
    )

    tools = [search_chess_knowledge, query_analytics]
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, max_iterations=6, verbose=False, return_intermediate_steps=True)


_agent_cache: dict[str, Any] = {}


def get_agent(duckdb_path: str):
    if duckdb_path not in _agent_cache:
        _agent_cache[duckdb_path] = build_agent(duckdb_path)
    return _agent_cache[duckdb_path]
