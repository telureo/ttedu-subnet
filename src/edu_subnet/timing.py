"""Analytics schedule and scoring window (spec §9.1, §9.4, §11.2, and the owner's rule of November 27, 2026).

Every lecture keeps its own clock, from the minute it actually ends:

- 48 hours after the end, the platform starts checking YouTube Analytics for the lecture, once every 30 minutes.
- The first check that YouTube answers with the lecture's live watch-minutes (a LIVE row) opens the lecture's
  scoring window, at that check's due time. The window lasts exactly 72 hours (144 readings of 30 minutes) for every
  lecture, however late YouTube's first answer comes.
- During the window every reading replaces the last one, so the score is always YouTube's latest value. YouTube can
  still change it, for example when its spam filter removes views.
- A lecture YouTube hasn't answered for within 7 days of checking never opens a window and is never counted.

Every datetime must be timezone-aware; the backend works in UTC (F-33).
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

FIRST_FETCH_DELAY = timedelta(hours=48)       # checking starts at the lecture's end + 48 hours
FETCH_INTERVAL = timedelta(minutes=30)        # one check, or one reading, every 30 minutes
SLOT_COUNT = 144                              # readings in a scoring window
WINDOW_LENGTH = FETCH_INTERVAL * SLOT_COUNT   # 72 hours, from YouTube's first answer
WAIT_LIMIT = timedelta(days=7)                # how long checking waits for YouTube's first answer
WAIT_CHECKS = WAIT_LIMIT // FETCH_INTERVAL    # 336 checks
FRESHNESS_LIMIT = timedelta(minutes=60)
# YouTube Analytics reports by Pacific-time day; only the query dates use it.
REPORTING_TZ = ZoneInfo("America/Los_Angeles")


def require_aware(t: datetime) -> datetime:
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError(f"naive datetime {t!r}. Use timezone-aware UTC times.")
    return t


def first_check_at(actual_end: datetime) -> datetime:
    """When checking YouTube starts: the lecture's end + 48 hours."""
    return require_aware(actual_end) + FIRST_FETCH_DELAY


def waiting_ends_at(actual_end: datetime) -> datetime:
    """The first answer must come from a check due before this: 7 days after checking starts (exclusive)."""
    return first_check_at(actual_end) + WAIT_LIMIT


def check_due_at(actual_end: datetime, k: int) -> datetime:
    """Due time of check k (0, 1, 2, ...), always derived from the lecture's own end."""
    if k < 0:
        raise ValueError(f"check {k} is before checking starts")
    return first_check_at(actual_end) + k * FETCH_INTERVAL


def due_check(actual_end: datetime, now: datetime) -> int | None:
    """The check a worker should run now, or None before checking starts.

    A late worker jumps to the current check; missed checks are not replayed.
    """
    start = first_check_at(actual_end)
    if require_aware(now) < start:
        return None
    return (now - start) // FETCH_INTERVAL


def is_window_start(actual_end: datetime, start: datetime) -> bool:
    """Whether `start` can open the lecture's scoring window: the due time of one of its checks before the waiting
    limit. Validators accept no other start, so a window can't be moved."""
    offset = require_aware(start) - first_check_at(actual_end)
    return timedelta(0) <= offset < WAIT_LIMIT and offset % FETCH_INTERVAL == timedelta(0)


def window_closes_at(window_start: datetime) -> datetime:
    """End of the scoring window, exclusive: 72 hours after it opens."""
    return require_aware(window_start) + WINDOW_LENGTH


def in_scoring_window(window_start: datetime | None, at: datetime) -> bool:
    """Half-open interval [start, start + 72h). A lecture YouTube hasn't answered for yet has no window."""
    if window_start is None:
        require_aware(at)
        return False
    return require_aware(window_start) <= require_aware(at) < window_closes_at(window_start)


def is_fresh(fetched_at: datetime, at: datetime) -> bool:
    """A record counts while it is younger than 60 minutes; at 60 it is stale."""
    return require_aware(at) - require_aware(fetched_at) < FRESHNESS_LIMIT


def query_dates(actual_start: datetime, actual_end: datetime) -> tuple[date, date]:
    """Pacific-time reporting dates covering the whole lecture, daylight-saving aware."""
    return (require_aware(actual_start).astimezone(REPORTING_TZ).date(),
            require_aware(actual_end).astimezone(REPORTING_TZ).date())
