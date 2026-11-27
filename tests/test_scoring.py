from datetime import datetime, timedelta, timezone
from fractions import Fraction

import pytest

from edu_subnet import timing
from edu_subnet.scoring import (AWAITING_ANALYTICS, NO_POSITIVE_ACTIVITY, LectureRecord,
                              format_index, score, standings, target_weights)

UTC = timezone.utc
END = datetime(2026, 10, 14, 10, 0, tzinfo=UTC)
AT = END + timedelta(hours=60)  # inside the window of every lecture that ends at END
FRESH = AT - timedelta(minutes=10)
MINERS = {"A", "B"}


FIRST = object()  # YouTube answered the first check, 48 hours after the end


def lecture(lecture_id, tutor, miner, minutes, *, end=END, fetched_at=FRESH, window_start=FIRST, **extra):
    start = timing.first_check_at(end) if window_start is FIRST else window_start
    return LectureRecord(lecture_id, tutor, miner, end, minutes, fetched_at, window_start_at=start, **extra)


SPEC_EXAMPLE = [  # spec §8.5
    lecture("A-101", "tutor-1", "A", 6000),
    lecture("A-102", "tutor-2", "A", 3000),
    lecture("B-201", "tutor-3", "B", 4500),
]


def test_spec_example_scores_and_weights():
    scores = score(SPEC_EXAMPLE, AT, MINERS)
    assert scores.miners == {"A": 9000, "B": 4500}
    weights = target_weights(scores.miners)
    assert not weights.burn
    assert weights.shares == {"A": Fraction(2, 3), "B": Fraction(1, 3)}
    assert sum(weights.shares.values()) == 1


def test_a_new_value_replaces_the_old_one():
    # A-101 drops from 6,000 to 5,000: A becomes 8,000, not 14,000 and not 9,000.
    updated = [lecture("A-101", "tutor-1", "A", 5000)] + SPEC_EXAMPLE[1:]
    assert score(updated, AT, MINERS).miners["A"] == 8000


def test_nothing_to_reward_burns():
    assert target_weights(score([], AT, MINERS).miners).burn
    zero = [lecture("A-101", "tutor-1", "A", 0)]
    assert target_weights(score(zero, AT, MINERS).miners).burn


def test_lectures_outside_the_window_count_zero():
    early = lecture("A-1", "tutor-1", "A", 100, end=AT - timedelta(hours=47))
    expired = lecture("A-2", "tutor-1", "A", 100, end=AT - timedelta(hours=120))
    assert score([early, expired], AT, MINERS).miners == {}


def test_a_late_first_answer_still_counts_for_72_hours():
    # YouTube first answered 10 hours late, at the 21st check: the lecture counts from then for 72 hours,
    # past the 120 hours a fixed window would have ended at.
    opened = timing.check_due_at(END, 20)
    late = lecture("A-1", "tutor-1", "A", 700, window_start=opened, fetched_at=END + timedelta(hours=125))
    assert score([late], END + timedelta(hours=125, minutes=10), MINERS).miners == {"A": 700}
    closing = lecture("A-1", "tutor-1", "A", 700, window_start=opened, fetched_at=opened + timedelta(hours=71, minutes=50))
    assert score([closing], opened + timedelta(hours=72), MINERS).miners == {}
    before = lecture("A-1", "tutor-1", "A", 700, window_start=opened, fetched_at=opened - timedelta(minutes=5))
    assert score([before], opened - timedelta(minutes=1), MINERS).miners == {}


def test_nothing_counts_before_youtube_answers():
    checking = lecture("A-1", "tutor-1", "A", None, fetched_at=None, window_start=None)
    assert score([checking], AT, MINERS).miners == {}
    # Even a number without an opened window counts for nothing.
    orphan = lecture("A-2", "tutor-1", "A", 500, window_start=None)
    assert score([orphan], AT, MINERS).miners == {}


def test_stale_and_pending_records_count_zero():
    stale = lecture("A-1", "tutor-1", "A", 100, fetched_at=AT - timedelta(minutes=60))
    nearly_stale = lecture("A-2", "tutor-1", "A", 50, fetched_at=AT - timedelta(minutes=59))
    pending = lecture("A-3", "tutor-1", "A", None, fetched_at=None)
    assert score([stale, nearly_stale, pending], AT, MINERS).miners == {"A": 50}


def test_an_ineligible_miner_is_withheld_not_redirected():
    records = [lecture("C-1", "tutor-9", "C", 700)] + SPEC_EXAMPLE
    assert "C" not in score(records, AT, MINERS).miners


def test_contributions_stay_with_the_miner_pinned_at_booking():
    # tutor-1 moved from agency A to agency B; each lecture keeps its own miner.
    records = [lecture("L-1", "tutor-1", "A", 100), lecture("L-2", "tutor-1", "B", 40)]
    scores = score(records, AT, MINERS)
    assert scores.miners == {"A": 100, "B": 40}
    assert scores.tutors == {"tutor-1": 140}


def test_disqualified_or_undelivered_lectures_count_zero():
    records = [lecture("A-1", "tutor-1", "A", 100, disqualified=True),
               lecture("A-2", "tutor-1", "A", 100, completed=False)]
    assert score(records, AT, MINERS).miners == {}


def test_a_lecture_is_never_counted_twice():
    with pytest.raises(ValueError):
        score(SPEC_EXAMPLE + [SPEC_EXAMPLE[0]], AT, MINERS)


def test_display_index_is_relative_to_the_top_tutor():
    rows = standings([lecture("1", "tutor-1", "A", 6000), lecture("2", "tutor-2", "B", 3000)], AT, MINERS)
    assert [(r.tutor_id, r.rank, format_index(r.index)) for r in rows] == [
        ("tutor-1", 1, "100.0"), ("tutor-2", 2, "50.0")]
    assert [r.raw_score for r in rows] == [6000, 3000]  # rewards use raw scores, not the index


def test_ties_share_a_rank():
    rows = standings([lecture("1", "t1", "A", 10), lecture("2", "t2", "A", 10),
                      lecture("3", "t3", "B", 5)], AT, MINERS)
    assert [(r.tutor_id, r.rank) for r in rows] == [("t1", 1), ("t2", 1), ("t3", 3)]


def test_no_positive_activity_has_no_winner():
    rows = standings([lecture("1", "tutor-1", "A", 0)], AT, MINERS)
    assert rows[0].label == NO_POSITIVE_ACTIVITY and rows[0].index is None


def test_a_new_tutor_is_awaiting_analytics():
    new = lecture("1", "tutor-new", "A", None, end=AT - timedelta(hours=10), fetched_at=None)
    rows = standings([new, lecture("2", "tutor-1", "A", 500)], AT, MINERS)
    assert rows[-1].tutor_id == "tutor-new" and rows[-1].label == AWAITING_ANALYTICS


def test_a_tutor_is_awaiting_while_youtube_is_checked_and_not_after_7_days():
    checking = lecture("1", "tutor-wait", "A", None, end=AT - timedelta(hours=100), fetched_at=None, window_start=None)
    rows = standings([checking, lecture("2", "tutor-1", "A", 500)], AT, MINERS)
    assert rows[-1].tutor_id == "tutor-wait" and rows[-1].label == AWAITING_ANALYTICS
    given_up = lecture("1", "tutor-wait", "A", None, end=AT - timedelta(hours=48) - timedelta(days=7), fetched_at=None,
                       window_start=None)
    rows = standings([given_up, lecture("2", "tutor-1", "A", 500)], AT, MINERS)
    assert [row.tutor_id for row in rows] == ["tutor-1"]


def test_index_rounds_half_up_for_display_only():
    assert format_index(Fraction(1001, 20)) == "50.1"  # 50.05
    assert format_index(Fraction(200, 3)) == "66.7"
