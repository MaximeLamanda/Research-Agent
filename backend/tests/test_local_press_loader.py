from app.data.local_press_loader import local_press_domains_for_department


def test_returns_domains_for_seine_et_marne():
    domains = local_press_domains_for_department("77", "FR")
    assert "actu.fr" in domains
    assert "leparisien.fr" in domains
    assert len(domains) >= 3


def test_returns_domains_for_rhone():
    domains = local_press_domains_for_department("69", "FR")
    assert "leprogres.fr" in domains


def test_returns_empty_for_unknown_department():
    assert local_press_domains_for_department("99", "FR") == []


def test_returns_empty_for_unsupported_country():
    assert local_press_domains_for_department("77", "XX") == []


def test_gb_london_press_domains():
    domains = local_press_domains_for_department("UKI", "GB")
    assert "standard.co.uk" in domains
    assert len(domains) >= 3


def test_ie_leinster_press_domains():
    domains = local_press_domains_for_department("LE", "IE")
    assert "irishtimes.com" in domains
    assert len(domains) >= 3


def test_all_gb_regions_have_press_domains():
    from app.data.departments import GB_REGIONS

    for code in GB_REGIONS:
        assert len(local_press_domains_for_department(code, "GB")) >= 2


def test_all_ie_provinces_have_press_domains():
    from app.data.departments import IE_PROVINCES

    for code in IE_PROVINCES:
        assert len(local_press_domains_for_department(code, "IE")) >= 2
