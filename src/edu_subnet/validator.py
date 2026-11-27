"""The validator: score the platform's dataset with the public rules, set weights, spot-check.

Every validator runs this same code on the same platform data, so validators agree
(spec §10.1, §11.1). The platform supplies numbers, never scores or weights.
"""
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from fractions import Fraction

from . import scoring
from .dataset import miner_ref, parse_dataset

log = logging.getLogger(__name__)
MAX_READ_SKEW_SECONDS = 300


@dataclass(frozen=True)
class Neuron:
    uid: int
    hotkey: str
    registration_block: int


@dataclass(frozen=True)
class WeightPlan:
    burn: bool
    weights: dict[int, float]   # uid -> weight
    miner_scores: dict[str, int]
    lectures: int
    reason: str


def plan_weights(payload: dict | None, neurons: list[Neuron], owner_hotkey: str, now: datetime,
                 burn_rate: Fraction | float = scoring.BURN_RATE) -> WeightPlan:
    """The weights to submit for one dataset.

    `burn_rate` is the part of the weight that is burned, from 0 to 1: it goes to the subnet owner's UID. The rest
    is shared among the miners by their scores. With nothing to reward, everything is burned (F-40).
    """
    burned = burn_rate if isinstance(burn_rate, Fraction) else Fraction(str(burn_rate))
    if not 0 <= burned <= 1:
        raise ValueError("The burn rate is a number from 0 to 1.")
    owner_uid = next((n.uid for n in neurons if n.hotkey == owner_hotkey), None)
    if owner_uid is None:
        raise ValueError("The subnet owner's hotkey is not registered on the subnet, so there is no UID to burn to.")

    def burn(reason: str, scores: dict | None = None, lectures: int = 0) -> WeightPlan:
        return WeightPlan(True, {owner_uid: 1.0}, scores or {}, lectures, reason)

    if burned == 1:
        return burn("the burn rate is 100%")
    if payload is None:
        return burn("no valid dataset from the platform")
    try:
        read_at, records = parse_dataset(payload)
        if abs((now - read_at).total_seconds()) > MAX_READ_SKEW_SECONDS:
            return burn("the dataset's read time is far from this computer's clock")
        # A miner is eligible only as the exact registration (hotkey + block) the lecture was booked under.
        uids = {miner_ref(n.hotkey, n.registration_block): n.uid for n in neurons}
        scores = scoring.score(records, read_at, set(uids))
    except (ValueError, KeyError, TypeError) as err:
        return burn(f"invalid dataset: {err}")
    weights = scoring.target_weights(scores.miners)
    if weights.burn:
        return burn("every miner score is zero", scores.miners, len(records))
    planned = {uids[m]: float(share * (1 - burned)) for m, share in weights.shares.items()}
    if burned > 0:
        planned[owner_uid] = planned.get(owner_uid, 0.0) + float(burned)
    return WeightPlan(False, planned, scores.miners, len(records), "scored")


@dataclass
class SpotChecker:
    """Compares a few platform numbers with YouTube each round (spec §10.6).

    A difference is a red flag only if it is still there after the platform's next
    refresh of that lecture, because YouTube can update a value between the two reads.
    """
    live_minutes: Callable[[dict], int | None]  # repeats a query with the validator's own access
    sample_size: int = 3
    pending: dict[str, dict] = field(default_factory=dict)

    def check(self, payload: dict) -> list[str]:
        records = {r["lecture_id"]: r for r in payload["lectures"] if r.get("status") == "ok" and r.get("query")}
        follow_ups = [r for lid, r in records.items()
                      if lid in self.pending and r["fetched_at"] != self.pending[lid]["fetched_at"]]
        others = [r for lid, r in records.items() if lid not in self.pending]
        sample = follow_ups + random.sample(others, min(self.sample_size, len(others)))
        flags = []
        for record in sample:
            flag = self.check_record(record)
            if flag:
                flags.append(flag)
        return flags

    def check_record(self, record: dict) -> str | None:
        lecture = record["lecture_id"]
        youtube = self.live_minutes(record["query"])
        if youtube == record["live_minutes"]:
            self.pending.pop(lecture, None)
            return None
        earlier = self.pending.get(lecture)
        if earlier and earlier["fetched_at"] != record["fetched_at"]:
            del self.pending[lecture]
            return (f"RED FLAG lecture {lecture}: the platform reports {record['live_minutes']} live minutes "
                    f"(fetched {record['fetched_at']}), YouTube reports {youtube}, and the difference survived "
                    f"the platform's refresh.")
        self.pending[lecture] = {"fetched_at": record["fetched_at"]}
        return None


def run(fetch: Callable[[], dict], snapshot: Callable[[], tuple[list[Neuron], str]],
        submit: Callable[[dict[int, float]], None], *, interval_seconds: float,
        checker: SpotChecker | None = None, report: Callable[[str], None] = log.info,
        rounds: int | None = None, sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        burn_rate: Fraction | float = scoring.BURN_RATE) -> None:
    """Download, score, submit, spot-check; repeat. `rounds=None` runs forever.

    A round the chain refuses or cannot be reached for (weights set too soon after a restart, a dropped
    connection) is reported, and the next round tries again: a validator never stops over one round.
    """
    done = 0
    while rounds is None or done < rounds:
        try:
            payload = fetch()
        except Exception as err:  # an unreachable platform means a burn round, never invented scores
            report(f"Could not get the dataset: {err}")
            payload = None
        try:
            neurons, owner_hotkey = snapshot()
            plan = plan_weights(payload, neurons, owner_hotkey, now(), burn_rate)
            if plan.burn:
                report(f"Burning this round: {plan.reason}.")
            elif float(burn_rate) > 0:
                paid = sum(1 for score in plan.miner_scores.values() if score > 0)
                report(f"Scored {plan.lectures} lectures, with {1 - float(burn_rate):.0%} of the weight for {paid} miners "
                       f"and {float(burn_rate):.0%} burned.")
            else:
                report(f"Scored {plan.lectures} lectures, with weights for {len(plan.weights)} miners.")
            submit(plan.weights)
        except Exception as err:
            report(f"Could not set weights this round: {err}")
        if checker is not None and payload is not None:
            try:
                for flag in checker.check(payload):
                    report(flag)
            except Exception as err:
                report(f"Spot-check failed this round: {err}")
        done += 1
        if rounds is None or done < rounds:
            sleep(interval_seconds)
