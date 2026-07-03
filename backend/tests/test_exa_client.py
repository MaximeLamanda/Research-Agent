from datetime import date

from app.agent.exa_client import parse_exa_published_date, published_dates_by_url


def test_parse_exa_published_date_iso_datetime():
    assert parse_exa_published_date("2025-06-01T12:00:00.000Z") == date(2025, 6, 1)


def test_parse_exa_published_date_date_only():
    assert parse_exa_published_date("2025-06-01") == date(2025, 6, 1)


def test_parse_exa_published_date_invalid():
    assert parse_exa_published_date(None) is None
    assert parse_exa_published_date("not-a-date") is None


def test_published_dates_by_url_merges_results():
    search = [{"url": "https://a.com", "publishedDate": "2025-01-01"}]
    fetch = [{"url": "https://b.com", "publishedDate": "2025-02-15T00:00:00.000Z"}]
    assert published_dates_by_url(search, fetch) == {
        "https://a.com": date(2025, 1, 1),
        "https://b.com": date(2025, 2, 15),
    }
