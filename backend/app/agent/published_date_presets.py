from datetime import date, timedelta

PRESET_ALL = "all"
PRESET_TODAY = "today"
PRESET_THIS_WEEK = "this_week"
PRESET_THIS_MONTH = "this_month"
PRESET_THIS_YEAR = "this_year"
PRESET_LAST_7_DAYS = "last_7_days"
PRESET_LAST_30_DAYS = "last_30_days"
PRESET_LAST_90_DAYS = "last_90_days"
PRESET_CUSTOM = "custom"

VALID_PRESETS = frozenset(
    {
        PRESET_ALL,
        PRESET_TODAY,
        PRESET_THIS_WEEK,
        PRESET_THIS_MONTH,
        PRESET_THIS_YEAR,
        PRESET_LAST_7_DAYS,
        PRESET_LAST_30_DAYS,
        PRESET_LAST_90_DAYS,
        PRESET_CUSTOM,
    }
)


def resolve_published_date_range(
    preset: str | None,
    start: date | None,
    end: date | None,
    *,
    reference: date | None = None,
) -> tuple[date | None, date | None]:
    today = reference or date.today()

    if not preset or preset == PRESET_ALL:
        return None, None
    if preset == PRESET_CUSTOM:
        return start, end
    if preset == PRESET_TODAY:
        return today, today
    if preset == PRESET_THIS_WEEK:
        start_of_week = today - timedelta(days=today.weekday())
        return start_of_week, today
    if preset == PRESET_THIS_MONTH:
        return today.replace(day=1), today
    if preset == PRESET_THIS_YEAR:
        return today.replace(month=1, day=1), today
    if preset == PRESET_LAST_7_DAYS:
        return today - timedelta(days=6), today
    if preset == PRESET_LAST_30_DAYS:
        return today - timedelta(days=29), today
    if preset == PRESET_LAST_90_DAYS:
        return today - timedelta(days=89), today

    return start, end
