import re

BLOCKED = re.compile(r"\b(DROP|DELETE|TRUNCATE|ALTER|INSERT|UPDATE|CREATE)\b", re.IGNORECASE)

def is_safe(sql: str) -> bool:
    return not bool(BLOCKED.search(sql))
