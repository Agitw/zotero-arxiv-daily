"""Publication date windows used by retrieval and final candidate filtering."""

from datetime import date, timedelta
from functools import lru_cache

import holidays as holiday_calendar


@lru_cache(maxsize=8)
def _china_holiday_dates(years: tuple[int, ...]) -> frozenset[date]:
    """Return Chinese public-holiday/rest dates for the requested years."""

    return frozenset(holiday_calendar.country_holidays("CN", years=years))


def china_holiday_dates(local_today: date) -> set[date]:
    """Return Chinese holiday dates near ``local_today``.

    Including the previous calendar year handles a run around New Year's Day
    without making callers know how far back the grace window may reach.
    """

    years = tuple(sorted({local_today.year - 1, local_today.year}))
    return set(_china_holiday_dates(years))


def earliest_allowed_publication_date(
    local_today: date,
    holiday_dates: set[date] | frozenset[date] | None = None,
) -> date:
    """Return the oldest publication date allowed for today's run.

    A normal Monday includes Saturday so that papers released over the
    weekend are not lost.  If the preceding Friday was a holiday, Monday is
    treated as the first workday after that holiday and the window walks back
    to the nearest preceding workday.  Other days similarly skip weekends and
    Chinese public holidays when looking for that preceding workday.
    """

    holidays = holiday_dates if holiday_dates is not None else china_holiday_dates(local_today)

    if local_today.weekday() == 0 and local_today not in holidays:
        preceding_friday = local_today - timedelta(days=3)
        if preceding_friday not in holidays:
            return local_today - timedelta(days=2)

    candidate = local_today - timedelta(days=1)
    while candidate.weekday() >= 5 or candidate in holidays:
        candidate -= timedelta(days=1)
    return candidate
