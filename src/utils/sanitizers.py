import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

SENSITIVE_PATTERNS = [
    (re.compile(r"X-Amz-Signature=[^&\s'\"]+", re.IGNORECASE), "X-Amz-Signature=[FILTERED]"),
    (re.compile(r"X-Amz-Security-Token=[^&\s'\"]+", re.IGNORECASE), "X-Amz-Security-Token=[FILTERED]"),
    (re.compile(r"X-Amz-Credential=[^&\s'\"]+", re.IGNORECASE), "X-Amz-Credential=[FILTERED]"),
    (re.compile(r"X-Amz-Date=[^&\s'\"]+", re.IGNORECASE), "X-Amz-Date=[FILTERED]"),
    (re.compile(r"(password|senha|token|secret|authorization|bearer)\s*[:=]\s*['\"]?[^'\",\s]+['\"]?", re.IGNORECASE), r"\1=[FILTERED]"),
]

def sanitize_url(url: str) -> str:
    """Remove parâmetros sensíveis (AWS S3 pre-signed, tokens) de URLs."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        if not parsed.query:
            return url
        params = parse_qs(parsed.query, keep_blank_values=True)
        sanitized_params = {}
        for k, v in params.items():
            if k.lower().startswith("x-amz-") or k.lower() in ("token", "signature", "auth", "credential"):
                sanitized_params[k] = ["[FILTERED]"]
            else:
                sanitized_params[k] = v
        
        new_query = urlencode(sanitized_params, doseq=True)
        return urlunparse(parsed._replace(query=new_query))
    except Exception:
        return "[URL_SANITIZATION_FAILED]"

def sanitize_text(text: str) -> str:
    """Varre e mascara qualquer ocorrência de segredos ou tokens sensíveis."""
    if not text:
        return ""
    sanitized = str(text)
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized
