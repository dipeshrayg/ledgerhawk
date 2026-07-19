"""Shared renewal-date math for auto-renewing contracts -- used by both the
CFO Dashboard's "upcoming renewals" widget and the Renewal Risk Calendar
(F7), so the two views can never disagree about when a vendor's contract
next comes up.
"""
from __future__ import annotations

from datetime import date

from app.schemas.ast import RenewalType


def next_anniversary(start: date, after: date) -> date:
    """Next future occurrence of start's month/day, on/after `after`."""
    year = after.year
    try:
        candidate = date(year, start.month, start.day)
    except ValueError:  # Feb 29 on a non-leap year
        candidate = date(year, 3, 1)
    if candidate < after:
        try:
            candidate = date(year + 1, start.month, start.day)
        except ValueError:
            candidate = date(year + 1, 3, 1)
    return candidate


def next_renewal_date(term_end: date, renewal_type: RenewalType, today: date) -> date:
    """Auto-renewing contracts roll their term forward every year; a term
    whose recorded end_date is already in the past just means one or more
    renewals have silently occurred since -- project the next one."""
    if term_end >= today or renewal_type != RenewalType.AUTO:
        return term_end
    d = term_end
    while d < today:
        try:
            d = date(d.year + 1, term_end.month, term_end.day)
        except ValueError:  # Feb 29 on a non-leap year
            d = date(d.year + 1, 3, 1)
    return d
