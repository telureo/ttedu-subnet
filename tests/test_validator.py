from datetime import datetime, timedelta, timezone

import pytest

from edu_subnet.dataset import EARLIER_POLICY, SCORING_POLICY
from edu_subnet.validator import Neuron, SpotChecker, plan_weights, run

UTC = timezone.utc
NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
END = NOW - timedelta(hours=60)
NEURONS = [Neuron(0, "owner", 1), Neuron(1, "hotA", 100), Neuron(2, "hotB", 200)]


def row(lecture_id, miner, minutes, fetched_minutes_ago=10, **extra):
    return {"lecture_id": lecture_id, "tutor_id": f"t-{lecture_id}", "miner": miner, "live_minutes": minutes,
            "actual_end_at": END.isoformat(), "completed": True, "disqualified": False,
            "eligibility_start_at": (END + timedelta(hours=48)).isoformat(),
            "fetched_at": (NOW - timedelta(minutes=fetched_minutes_ago)).isoformat(), **extra}


def dataset(*rows, read_at=NOW, policy=SCORING_POLICY):
    return {"scoring_policy": policy, "read_at": read_at.isoformat(), "row_count": len(rows),
            "lectures": list(rows)}


def test_weights_follow_live_minutes():
    plan = plan_weights(dataset(row("1", "hotA@100", 6000), row("2", "hotA@100", 3000), row("3", "hotB@200", 4500)),
                        NEURONS, "owner", NOW)
    assert not plan.burn
    assert plan.weights == pytest.approx({1: 2 / 3, 2: 1 / 3})


def test_a_lecture_youtube_answered_late_still_counts_after_120_hours():
    late_end = NOW - timedelta(hours=125)  # a fixed window would have closed 5 hours ago
    late = row("1", "hotA@100", 600, actual_end_at=late_end.isoformat(),
               eligibility_start_at=(late_end + timedelta(hours=60)).isoformat())  # YouTube answered 12 hours late
    plan = plan_weights(dataset(late, row("2", "hotB@200", 200)), NEURONS, "owner", NOW)
    assert plan.weights == pytest.approx({1: 0.75, 2: 0.25})


def test_a_lecture_still_waiting_for_youtube_counts_for_nothing():
    waiting = row("1", "hotA@100", None, eligibility_start_at=None, fetched_at=None, status="pending")
    plan = plan_weights(dataset(waiting, row("2", "hotB@200", 200)), NEURONS, "owner", NOW)
    assert plan.weights == {2: 1.0}


def test_the_earlier_policy_still_gives_the_same_weights():
    rows = [row("1", "hotA@100", 6000, eligibility_start_at=None), row("2", "hotB@200", 3000, eligibility_start_at=None)]
    plan = plan_weights(dataset(*rows, policy=EARLIER_POLICY), NEURONS, "owner", NOW)
    assert plan.weights == pytest.approx({1: 2 / 3, 2: 1 / 3})


def test_a_reregistered_hotkey_does_not_inherit_old_lectures():
    plan = plan_weights(dataset(row("1", "hotA@50", 6000), row("2", "hotB@200", 100)), NEURONS, "owner", NOW)
    assert plan.weights == {2: 1.0}  # hotA@50 is an earlier registration of hotA


@pytest.mark.parametrize("payload, reason", [
    (None, "no valid dataset"),
    (dataset(row("1", "hotA@100", 0)), "every miner score is zero"),
    (dataset(row("1", "hotA@100", 10), read_at=NOW - timedelta(minutes=10)), "clock"),
    ({"scoring_policy": "other"}, "invalid dataset"),
    (dataset(row("1", "hotA@100", 10), row("1", "hotA@100", 10)), "invalid dataset"),
    (dataset(row("1", "hotA@100", 10, eligibility_start_at=(END + timedelta(hours=48, minutes=5)).isoformat())),
     "invalid dataset"),  # a moved window
])
def test_nothing_to_reward_burns_to_the_owner(payload, reason):
    plan = plan_weights(payload, NEURONS, "owner", NOW)
    assert plan.burn and plan.weights == {0: 1.0} and reason in plan.reason


def test_burning_needs_the_owner_to_be_registered():
    with pytest.raises(ValueError):
        plan_weights(None, NEURONS[1:], "owner", NOW)


def record(fetched_at, minutes=100):
    return {"lecture_id": "L1", "status": "ok", "live_minutes": minutes, "fetched_at": fetched_at,
            "query": {"filters": "video==v1"}}


def test_a_difference_is_a_red_flag_only_after_the_platform_refreshes():
    youtube = {"value": 100}
    checker = SpotChecker(lambda query: youtube["value"])
    assert checker.check_record(record("10:00")) is None  # same value: fine

    youtube["value"] = 120
    assert checker.check_record(record("10:00")) is None  # differs: maybe YouTube updated; wait
    assert checker.check_record(record("10:00")) is None  # no platform refresh yet: still wait
    flag = checker.check_record(record("10:30"))          # refreshed and still different
    assert flag and "RED FLAG" in flag and "120" in flag

    assert checker.check_record(record("10:30", minutes=120)) is None  # agreement clears it


def test_follow_ups_are_checked_first():
    asked = []
    checker = SpotChecker(lambda query: asked.append(query) or 999, sample_size=0)
    checker.pending["L1"] = {"fetched_at": "10:00"}
    flags = checker.check({"lectures": [record("10:30")]})
    assert len(asked) == 1 and flags and "L1" in flags[0]


def test_an_unreachable_platform_means_a_burn_round():
    submitted, reports = [], []
    payloads = iter([RuntimeError("timeout"), dataset(row("1", "hotA@100", 60))])

    def fetch():
        item = next(payloads)
        if isinstance(item, Exception):
            raise item
        return item

    run(fetch, lambda: (NEURONS, "owner"), submitted.append, interval_seconds=0, report=reports.append,
        rounds=2, sleep=lambda seconds: None, now=lambda: NOW)
    assert submitted == [{0: 1.0}, {1: 1.0}]
    assert "Could not get the dataset" in reports[0] and "Burning" in reports[1]


def test_a_refused_round_does_not_stop_the_validator():
    reports, submitted = [], []

    def submit(weights):
        submitted.append(weights)
        if len(submitted) == 1:
            raise RuntimeError("weights were set 40 blocks ago; the rate limit is 100")

    run(lambda: dataset(row("1", "hotA@100", 60)), lambda: (NEURONS, "owner"), submit, interval_seconds=0,
        report=reports.append, rounds=3, sleep=lambda seconds: None, now=lambda: NOW)
    assert len(submitted) == 3
    assert any("Could not set weights this round" in line and "rate limit" in line for line in reports)


def test_an_unreachable_chain_does_not_stop_the_validator():
    reports, submitted, answers = [], [], iter([ConnectionError("no route to the chain"), (NEURONS, "owner")])

    def snapshot():
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    run(lambda: None, snapshot, submitted.append, interval_seconds=0, report=reports.append, rounds=2,
        sleep=lambda seconds: None, now=lambda: NOW)
    assert submitted == [{0: 1.0}]
    assert "Could not set weights this round: no route to the chain" in reports[0]
