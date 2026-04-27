GENERATE_PROMPT = """\
You are a SQL expert. Given the schema below, write a single read-only SQL query.
The schema is provided in TOON (Token-Oriented Object Notation).
Return ONLY a TOON object with a single field named sql.

Rules:
- Write the SQL value with NO surrounding quotes of any kind.
- Use single quotes only for string literals inside the SQL (e.g. WHERE category = 'food').
- Write table names, column names, and aliases bare with no quotes.

Output format:
sql: SELECT ...;

Schema:
{schema_toon}

Question: {question}
"""

CORRECT_PROMPT = """\
The following SQL query produced an error. Fix it.
The schema is provided in TOON (Token-Oriented Object Notation).
Return ONLY a TOON object with a single field named sql.

Rules:
- Write the SQL value with NO surrounding quotes of any kind.
- Use single quotes only for string literals inside the SQL (e.g. WHERE category = 'food').
- Write table names, column names, and aliases bare with no quotes.

Output format:
sql: 'SELECT ...;'

SQL:
{sql}

Error:
{error}

Schema:
{schema_toon}
"""

VALIDATE_PROMPT = """\
You are a SQL semantic validator. Your job is to check if a SQL query is appropriate for a user's question.

Given a user question and the generated SQL, determine if the SQL is semantically correct:
- Does the SQL query the right tables/columns for what was asked?
- If the user asks for something that doesn't exist in the database (e.g., "bank transactions"), should fail validation.
- If the SQL queries unrelated tables (e.g., user asks "my food entries" but SQL queries "travel_entries"), should fail validation.

Available tables in the schema: {available_tables}

Question: {question}

SQL: {sql}

Respond with ONLY one of:
- "VALID" if the SQL is semantically appropriate
- "INVALID" if the SQL doesn't match the question intent

Respond with exactly one word: VALID or INVALID
"""
