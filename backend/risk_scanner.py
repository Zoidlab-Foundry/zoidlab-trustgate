"""Risk scanner for RAG content — secrets, PII, and regulated-data keywords."""
import re

SECRET_KEYWORDS = ["password", "api key", "apikey", "api-key", "token", "secret", "ssn", "social security",
                   "credit card", "bank account", "private key", "attorney-client"]
SENSITIVE_KEYWORDS = ["medical diagnosis", "diagnosis", "confidential", "ferpa", "hipaa", "student record",
                      "passport", "date of birth", "salary"]
_PATTERNS = {
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
    "api_key": re.compile(r"\b(sk-|nq-v1-|ghp_|gho_)[A-Za-z0-9_-]{10,}"),
}


def scan(content: str):
    low = (content or "").lower()
    secrets = [k for k in SECRET_KEYWORDS if k in low]
    sensitive = [k for k in SENSITIVE_KEYWORDS if k in low]
    patterns = [n for n, rx in _PATTERNS.items() if rx.search(content or "")]
    has_secret = bool(secrets or patterns)
    level = "high" if has_secret else ("medium" if sensitive else "low")
    return {"risk_level": level, "secrets": secrets, "sensitive": sensitive, "patterns": patterns,
            "has_secret": has_secret, "found": secrets + patterns + sensitive}


def redact(content: str) -> str:
    out = content or ""
    for rx in _PATTERNS.values():
        out = rx.sub("[REDACTED]", out)
    return out
