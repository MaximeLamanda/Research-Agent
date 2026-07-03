from app.agent.blocked_domains import exa_exclude_domains, is_blocked_url


def test_blocks_basedespermis_urls():
    assert is_blocked_url(
        "https://basedespermis.fr/autorisation-pc-0915212500026-2025-11-10"
    )
    assert is_blocked_url("https://www.basedespermis.fr/commune-ris-orangis-91521")


def test_allows_other_domains():
    assert not is_blocked_url("https://www.lemoniteur.fr/article-construction")
    assert not is_blocked_url("https://example.com/project")


def test_exa_exclude_domains_skipped_for_company_category():
    assert exa_exclude_domains("company") is None
    assert exa_exclude_domains("news") == ["basedespermis.fr"]
