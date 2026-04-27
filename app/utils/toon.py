import re

import toons


def schema_text_to_toon(schema_text: str) -> str:
    """Convert retrieved schema text into TOON via the official toons serializer."""
    lines = [line.strip() for line in (schema_text or "").splitlines() if line.strip()]
    if not lines:
        return toons.dumps({"tables": []})

    tables: list[dict[str, list[str] | str]] = []
    current: dict[str, list[str] | str] | None = None

    for line in lines:
        if line.startswith("Table: "):
            if current:
                tables.append(current)
            current = {
                "name": line.replace("Table: ", "", 1).strip(),
                "columns": [],
                "foreign_keys": [],
            }
            continue

        if current is None:
            continue

        if line.startswith("Columns: "):
            cols = line.replace("Columns: ", "", 1).strip()
            current["columns"] = [c.strip() for c in cols.split(",") if c.strip()]
            continue

        if line.startswith("Foreign keys: "):
            fks = line.replace("Foreign keys: ", "", 1).strip()
            current["foreign_keys"] = [fk.strip() for fk in fks.split(";") if fk.strip()]

    if current:
        tables.append(current)

    return toons.dumps({"tables": tables})


def extract_sql_from_toon(raw_output: str) -> str:
    """Extract SQL from TOON response. Falls back to regex/raw output on malformed TOON."""
    text = (raw_output or "").strip()
    if not text:
        return ""

    text = _strip_code_fence(text)

    try:
        payload = toons.loads(text, strict=False)
        sql_value = payload.get("sql") if isinstance(payload, dict) else None
        if isinstance(sql_value, str) and sql_value.strip():
            return _strip_wrapping_quotes(sql_value.strip())
    except ValueError:
        pass

    # Bare multiline: sql: SELECT ...\n... (no surrounding quotes — preferred format)
    bare = re.search(r"(?im)^\s*sql\s*:\s*(SELECT\b.*)", text, re.DOTALL)
    if bare:
        return bare.group(1).strip().rstrip("'\"")

    triple_single = re.search(r"(?is)sql\s*:\s*'''(.*?)'''", text, re.DOTALL)
    if triple_single:
        return triple_single.group(1).strip()

    triple_double = re.search(r'(?is)sql\s*:\s*"""(.*?)"""', text, re.DOTALL)
    if triple_double:
        return triple_double.group(1).strip()

    single = re.search(r"(?is)^\s*sql\s*:\s*'(.*?)'\s*$", text, re.MULTILINE | re.DOTALL)
    if single:
        return single.group(1).strip()

    double = re.search(r'(?is)^\s*sql\s*:\s*"(.*?)"\s*$', text, re.MULTILINE | re.DOTALL)
    if double:
        return double.group(1).strip()

    line = re.search(r"(?im)^\s*sql\s*:\s*(.+)$", text)
    if line:
        return line.group(1).strip()

    return text


def _strip_code_fence(value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith("```"):
        parts = cleaned.splitlines()
        if parts and parts[0].startswith("```"):
            parts = parts[1:]
        if parts and parts[-1].strip() == "```":
            parts = parts[:-1]
        return "\n".join(parts).strip()
    return cleaned


def _strip_wrapping_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1].strip()
    return value
