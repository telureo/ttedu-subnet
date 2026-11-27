"""Validator scoring and the public tutor ranking (spec §7.3, §8, §11).

Validators and the platform's ranking display use this same code, so there is no
second reward formula. Minutes are integers and weights are exact fractions.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from typing import Iterable

from . import timing

NO_POSITIVE_ACTIVITY = "No positive scored activity"
AWAITING_ANALYTICS = "Awaiting analytics"


@dataclass(frozen=True)
class LectureRecord:
    """One lecture as the validator download describes it (spec §10.2)."""
    lecture_id: str
    tutor_id: str
    miner: str                   # miner registration pinned at booking (hotkey + registration)
    actual_end_at: datetime
    live_minutes: int | None     # LIVE estimatedMinutesWatched; None while pending or unavailable
    fetched_at: datetime | None  # the platform's source_fetched_at for live_minutes
    completed: bool = True       # a valid delivered platform session
    disqualified: bool = False   # excluded under a published, auditable decision
    window_start_at: datetime | None = None  # YouTube's first answer opened the 72 hours; None until then


def is_scored(record: LectureRecord, at: datetime, eligible_miners: set[str]) -> bool:
    """The eligibility indicator I of spec §8.4."""
    return (record.completed
            and not record.disqualified
            and record.miner in eligible_miners
            and timing.in_scoring_window(record.window_start_at, at)
            and record.live_minutes is not None
            and record.fetched_at is not None
            and timing.is_fresh(record.fetched_at, at))


def _unique(records: Iterable[LectureRecord]) -> list[LectureRecord]:
    records = list(records)
    seen = set()
    for record in records:
        if record.lecture_id in seen:
            raise ValueError(f"lecture {record.lecture_id} appears twice. A lecture is never counted twice.")
        seen.add(record.lecture_id)
    return records


@dataclass(frozen=True)
class Scores:
    tutors: dict[str, int]  # T_u
    miners: dict[str, int]  # M_m


def score(records: Iterable[LectureRecord], at: datetime, eligible_miners: set[str]) -> Scores:
    """Raw tutor and miner scores, L = I × W summed per tutor and per pinned miner."""
    tutors: dict[str, int] = {}
    miners: dict[str, int] = {}
    for record in _unique(records):
        if is_scored(record, at, eligible_miners):
            tutors[record.tutor_id] = tutors.get(record.tutor_id, 0) + record.live_minutes
            miners[record.miner] = miners.get(record.miner, 0) + record.live_minutes
    return Scores(tutors, miners)


@dataclass(frozen=True)
class Weights:
    burn: bool                   # True: put all weight on the subnet owner's UID (F-40)
    shares: dict[str, Fraction]  # miner -> exact share of the total; empty when burning


def target_weights(miner_scores: dict[str, int]) -> Weights:
    total = sum(miner_scores.values())
    if total <= 0:
        return Weights(burn=True, shares={})
    return Weights(burn=False,
                   shares={miner: Fraction(s, total) for miner, s in miner_scores.items() if s > 0})


@dataclass(frozen=True)
class Standing:
    tutor_id: str
    raw_score: int
    index: Fraction | None  # Audience Performance Index, 0..100; None when not ranked
    rank: int | None        # ties share a rank: 1, 1, 3
    label: str | None       # AWAITING_ANALYTICS or NO_POSITIVE_ACTIVITY


def awaiting_analytics(record: LectureRecord, at: datetime) -> bool:
    """Whether the lecture's number may still come: checking YouTube for its first answer, or inside its window
    without a number yet."""
    if record.window_start_at is None:
        return at < timing.waiting_ends_at(record.actual_end_at)
    return (at < timing.window_closes_at(record.window_start_at)
            and (at < record.window_start_at or record.live_minutes is None))


def standings(records: Iterable[LectureRecord], at: datetime, eligible_miners: set[str]) -> list[Standing]:
    """Public tutor ranking: index = 100 × T_u / max T over tutors with scored lectures."""
    records = _unique(records)
    scored = score(records, at, eligible_miners).tutors
    awaiting = {r.tutor_id for r in records
                if r.tutor_id not in scored
                and r.completed and not r.disqualified and r.miner in eligible_miners
                and awaiting_analytics(r, at)}

    top = max(scored.values(), default=0)
    rows: list[Standing] = []
    if top > 0:
        rank, previous = 0, None
        ordered = sorted(scored.items(), key=lambda item: (-item[1], item[0]))
        for position, (tutor, raw) in enumerate(ordered, start=1):
            if raw != previous:
                rank, previous = position, raw
            rows.append(Standing(tutor, raw, Fraction(100 * raw, top), rank, None))
    else:
        rows += [Standing(tutor, raw, None, None, NO_POSITIVE_ACTIVITY) for tutor, raw in sorted(scored.items())]
    rows += [Standing(tutor, 0, None, None, AWAITING_ANALYTICS) for tutor in sorted(awaiting)]
    return rows


def format_index(index: Fraction) -> str:
    """Round only for display, to one decimal place, half up."""
    value = Decimal(index.numerator) / Decimal(index.denominator)
    return str(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
