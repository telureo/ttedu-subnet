from datetime import date, datetime, timedelta, timezone

import pytest

from edu_subnet import timing

UTC = timezone.utc
END = datetime(2026, 10, 14, 10, 7, tzinfo=UTC)
TICK = timedelta(microseconds=1)


def test_checking_starts_48_hours_after_the_end_and_runs_every_30_minutes():
    assert timing.first_check_at(END) == END + timedelta(hours=48)
    assert timing.check_due_at(END, 0) == END + timedelta(hours=48)
    assert timing.check_due_at(END, 1) == END + timedelta(hours=48, minutes=30)
    assert timing.check_due_at(END, 335) == END + timedelta(hours=48) + timedelta(days=7) - timedelta(minutes=30)
    with pytest.raises(ValueError):
        timing.check_due_at(END, -1)


def test_each_lecture_keeps_its_own_clock():
    # Spec §9.1 example: ends at 10:07 and 11:23:42 are never rounded to a shared grid.
    a = datetime(2026, 10, 14, 10, 7, tzinfo=UTC)
    b = datetime(2026, 10, 14, 11, 23, 42, tzinfo=UTC)
    assert timing.check_due_at(a, 0) == datetime(2026, 10, 16, 10, 7, tzinfo=UTC)
    assert timing.check_due_at(a, 1) == datetime(2026, 10, 16, 10, 37, tzinfo=UTC)
    assert timing.check_due_at(b, 0) == datetime(2026, 10, 16, 11, 23, 42, tzinfo=UTC)
    assert timing.check_due_at(b, 1) == datetime(2026, 10, 16, 11, 53, 42, tzinfo=UTC)


def test_a_late_worker_jumps_to_the_current_check_without_drift():
    start = timing.first_check_at(END)
    assert timing.due_check(END, start - TICK) is None
    assert timing.due_check(END, start) == 0
    late = start + timedelta(minutes=65)  # check 1 was due 35 minutes ago
    assert timing.due_check(END, late) == 2
    assert timing.check_due_at(END, 2) == start + timedelta(minutes=60)


def test_the_window_opens_at_youtubes_first_answer_and_lasts_exactly_72_hours():
    opened = timing.check_due_at(END, 9)  # YouTube first answered the tenth check, 4.5 hours late
    closes = timing.window_closes_at(opened)
    assert closes == opened + timedelta(hours=72) == END + timedelta(hours=124, minutes=30)
    assert not timing.in_scoring_window(opened, opened - TICK)
    assert timing.in_scoring_window(opened, opened)
    assert timing.in_scoring_window(opened, closes - TICK)
    assert not timing.in_scoring_window(opened, closes)


def test_every_lecture_gets_the_same_72_hours_however_late_youtube_answers():
    for first_answer in (0, 1, 20, 96, 335):
        opened = timing.check_due_at(END, first_answer)
        assert timing.is_window_start(END, opened)
        assert timing.window_closes_at(opened) - opened == timing.WINDOW_LENGTH == timedelta(hours=72)
        assert timing.WINDOW_LENGTH == timing.SLOT_COUNT * timing.FETCH_INTERVAL  # 144 readings of 30 minutes


def test_no_window_before_youtube_answers():
    assert not timing.in_scoring_window(None, END + timedelta(hours=60))


def test_checking_waits_7_days_for_the_first_answer():
    assert timing.WAIT_CHECKS == 336
    assert timing.waiting_ends_at(END) == END + timedelta(hours=48) + timedelta(days=7)
    assert timing.is_window_start(END, timing.check_due_at(END, timing.WAIT_CHECKS - 1))
    assert not timing.is_window_start(END, timing.check_due_at(END, timing.WAIT_CHECKS))  # 7 days of checks have passed


def test_a_window_can_open_only_at_one_of_the_lectures_checks():
    assert timing.is_window_start(END, END + timedelta(hours=48))
    assert timing.is_window_start(END, END + timedelta(hours=61, minutes=30))
    assert not timing.is_window_start(END, END + timedelta(hours=47, minutes=30))  # before checking starts
    assert not timing.is_window_start(END, END + timedelta(hours=48, minutes=1))  # not a check's due time
    assert not timing.is_window_start(END, END + timedelta(hours=48) + TICK)


def test_fresh_before_60_minutes_and_stale_at_60():
    fetched = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
    assert timing.is_fresh(fetched, fetched + timedelta(minutes=59))
    assert not timing.is_fresh(fetched, fetched + timedelta(minutes=60))


def test_query_dates_across_pacific_midnight():
    # 23:30 PDT on Oct 14 to 00:30 PDT on Oct 15.
    start = datetime(2026, 10, 15, 6, 30, tzinfo=UTC)
    end = datetime(2026, 10, 15, 7, 30, tzinfo=UTC)
    assert timing.query_dates(start, end) == (date(2026, 10, 14), date(2026, 10, 15))


def test_query_dates_after_daylight_saving_ends():
    # US daylight saving ends Nov 1, 2026, so 07:45 UTC on Nov 2 is 23:45 PST on Nov 1.
    # A fixed UTC-7 offset would wrongly give Nov 2 as the end date.
    start = datetime(2026, 11, 2, 6, 45, tzinfo=UTC)
    end = datetime(2026, 11, 2, 7, 45, tzinfo=UTC)
    assert timing.query_dates(start, end) == (date(2026, 11, 1), date(2026, 11, 1))


def test_naive_times_are_rejected():
    naive = datetime(2026, 10, 14, 10, 7)
    for call in (lambda: timing.first_check_at(naive), lambda: timing.in_scoring_window(naive, END),
                 lambda: timing.in_scoring_window(None, naive), lambda: timing.is_window_start(END, naive)):
        with pytest.raises(ValueError):
            call()
