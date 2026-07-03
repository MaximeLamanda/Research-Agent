from urllib.parse import urlparse

BLOCKED_ROOT_DOMAINS = frozenset(
    {
        "basedespermis.fr",
    }
)


def url_domain(url: str) -> str | None:
    host = urlparse(url).netloc.lower()
    if not host:
        return None
    if host.startswith("www."):
        host = host[4:]
    return host


def is_blocked_url(url: str) -> bool:
    domain = url_domain(url)
    if not domain:
        return False
    return any(domain == blocked or domain.endswith(f".{blocked}") for blocked in BLOCKED_ROOT_DOMAINS)


def exa_exclude_domains(category: str | None) -> list[str] | None:
    if category in {"company", "people"}:
        return None
    return sorted(BLOCKED_ROOT_DOMAINS)
