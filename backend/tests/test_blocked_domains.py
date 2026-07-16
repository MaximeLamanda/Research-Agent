from app.agent.blocked_domains import exa_exclude_domains, is_blocked_url


def test_blocks_basedespermis_urls():
    assert is_blocked_url(
        "https://basedespermis.fr/autorisation-pc-0915212500026-2025-11-10"
    )
    assert is_blocked_url("https://www.basedespermis.fr/commune-ris-orangis-91521")


def test_allows_other_domains():
    assert not is_blocked_url("https://www.lemoniteur.fr/article-construction")
    assert not is_blocked_url("https://example.com/project")


def test_blocks_spam_seo_domains():
    assert is_blocked_url("https://42.kuailejiaju.com/html/20260706/816124.html")
    assert is_blocked_url("https://f.yvelinesinfos.com/html/20260706/739449.html")


def test_exa_exclude_domains_skipped_for_company_category():
    assert exa_exclude_domains("company") is None
    excluded = exa_exclude_domains("news")
    assert excluded is not None
    assert "basedespermis.fr" in excluded
    assert "kuailejiaju.com" in excluded
