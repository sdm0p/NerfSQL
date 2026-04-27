from typing import TypedDict, Optional
import re
from langchain_core.messages import HumanMessage
from app.llm.client import get_llm
from app.llm.prompts import GENERATE_PROMPT, CORRECT_PROMPT, VALIDATE_PROMPT
from app.db.engine import execute_query
from app.validators.sql_guard import is_safe
from app.utils.toon import extract_sql_from_toon, schema_text_to_toon

MAX_RETRIES = 3


def _normalize_sql(sql: str) -> str:
    cleaned = sql.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    if cleaned.lower().startswith("sql\n"):
        cleaned = cleaned[4:].strip()
    # Strip any residual ''' wrapping the LLM emitted despite instructions
    if cleaned.startswith("'''"):
        cleaned = cleaned[3:]
    if cleaned.endswith("'''") or cleaned.endswith("''''"):
        cleaned = cleaned.rstrip("'")
    # Fix doubled single-quotes from old TOON wrapping artifact (''value'' -> 'value')
    cleaned = re.sub(r"''([^']+)''", r"'\1'", cleaned)
    return cleaned.strip()

class AgentState(TypedDict):
    question: str
    schema: str
    sql: str
    result: Optional[list]
    error: Optional[str]
    retries: int

def generate_sql(state: AgentState) -> AgentState:
    llm = get_llm()
    prompt = GENERATE_PROMPT.format(
        schema_toon=schema_text_to_toon(state["schema"]),
        question=state["question"],
    )
    raw = llm.invoke([HumanMessage(content=prompt)]).content
    sql = _normalize_sql(extract_sql_from_toon(raw))
    return {**state, "sql": sql, "error": None}

def _extract_tables_from_sql(sql: str) -> list:
    """Extract table names from SQL query."""
    # Match FROM and JOIN clauses
    pattern = r'(?:FROM|JOIN)\s+(\w+)'
    matches = re.findall(pattern, sql, re.IGNORECASE)
    return [m.lower() for m in matches]

def _get_available_tables(schema: str) -> list:
    """Extract available table names from schema text."""
    # Schema format: "Table: table_name\nColumns: ..."
    pattern = r'Table:\s+(\w+)'
    matches = re.findall(pattern, schema)
    return [m.lower() for m in matches]

def validate_sql_semantic(state: AgentState) -> AgentState:
    """Validate that generated SQL is semantically appropriate for the question."""
    sql = state["sql"]
    available_tables = _get_available_tables(state["schema"])

    llm = get_llm()
    prompt = VALIDATE_PROMPT.format(
        available_tables=", ".join(available_tables),
        question=state["question"],
        sql=sql,
    )
    response = llm.invoke([HumanMessage(content=prompt)]).content.strip().upper()

    if "INVALID" in response:
        return {
            **state,
            "sql": "",  # Clear SQL on validation failure
            "error": f"Cannot answer this question: the requested data does not exist in the database or is not relevant to the available schema.",
            "result": None
        }
    return state

def validate_and_execute(state: AgentState) -> AgentState:
    # Skip execution if there's already a validation error
    if state.get("error"):
        return state

    sql = state["sql"]
    if not is_safe(sql):
        return {**state, "error": "Blocked: destructive SQL detected", "result": None}
    try:
        result = execute_query(sql)
        return {**state, "result": result, "error": None}
    except Exception as e:
        return {**state, "error": str(e), "result": None}

def correct_sql(state: AgentState) -> AgentState:
    llm = get_llm()
    prompt = CORRECT_PROMPT.format(
        sql=state["sql"],
        error=state["error"],
        schema_toon=schema_text_to_toon(state["schema"]),
    )
    raw = llm.invoke([HumanMessage(content=prompt)]).content
    sql = _normalize_sql(extract_sql_from_toon(raw))
    return {**state, "sql": sql, "retries": state["retries"] + 1}

def should_retry(state: AgentState) -> str:
    if state.get("error") and state["retries"] < MAX_RETRIES:
        return "correct"
    return "end"
