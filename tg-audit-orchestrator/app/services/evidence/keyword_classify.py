"""Keyword-based evidence classifier — MVP, no AI required.

Maps document content to pack category names.
The function signature is the seam: swap the body for LLM-based
classification when needed without touching callers.
"""

_RULES: list[tuple[list[str], str]] = [
    (["privacy notice", "data subject", "processing purpose", "lawful basis"], "notice"),
    (["consent", "withdraw consent", "opt-in", "opt-out"], "consent"),
    (["access request", "erasure", "portability", "rectification", "rights"], "rights"),
    (["encryption", "access control", "firewall", "patch", "vulnerability", "security policy"], "security"),
    (["breach notification", "incident report", "data breach", "72 hours", "supervisory authority"], "breach"),
    (["dpo", "data protection officer", "governance", "policy register", "accountability"], "governance"),
    # VAPT categories
    (["dns", "subdomain", "nameserver", "mx record"], "recon"),
    (["ssl", "tls", "certificate", "cipher", "hsts"], "crypto"),
    (["sql injection", "xss", "cross-site", "command injection", "rce", "injection"], "input"),
    (["authentication", "login", "mfa", "password policy", "brute force"], "auth"),
    (["authorization", "privilege", "rbac", "idor", "access control"], "authz"),
    (["session", "cookie", "token", "csrf", "same-site"], "session"),
    (["api", "endpoint", "swagger", "openapi", "rest", "graphql"], "api"),
    (["business logic", "workflow bypass", "rate limit", "abuse"], "business_logic"),
    (["server configuration", "header", "cors", "csp", "x-frame"], "config"),
]


def classify_text(text: str, *, mime: str = "", filename: str = "") -> str:
    """Return the best-matching category or 'general'."""
    haystack = (text + " " + filename).lower()
    best = ("general", 0)
    for keywords, category in _RULES:
        hits = sum(1 for kw in keywords if kw in haystack)
        if hits > best[1]:
            best = (category, hits)
    return best[0]
