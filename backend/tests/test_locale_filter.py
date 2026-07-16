from app.agent.locale_filter import (
    exa_user_location_for_country,
    is_likely_foreign_candidate,
)


def test_exa_user_location_for_france():
    assert exa_user_location_for_country("FR") == "FR"


def test_exa_user_location_for_germany():
    assert exa_user_location_for_country("DE") == "DE"


def test_exa_user_location_gb_ie():
    assert exa_user_location_for_country("GB") == "GB"
    assert exa_user_location_for_country("IE") == "IE"


def test_detects_chinese_title():
    assert is_likely_foreign_candidate(
        "国产封测龙头长电科技78亿投建新厂",
        "",
        "https://example.com/article",
        country="FR",
    )


def test_detects_chinese_domain():
    assert is_likely_foreign_candidate(
        "Title",
        "",
        "https://example.com/春梦无痕网",
        country="FR",
    )


def test_detects_spam_url_path_pattern():
    assert is_likely_foreign_candidate(
        "Title",
        "",
        "https://42.kuailejiaju.com/html/20260706/816124.html",
        country="FR",
    )


def test_french_candidate_not_foreign():
    assert not is_likely_foreign_candidate(
        "Nouvelle usine logistique en Seine-et-Marne",
        "Projet d'extension à Meaux",
        "https://actu.fr/article",
        country="FR",
    )
