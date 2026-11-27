"""The validator dataset: what GET /api/validator/eligible returns (spec §10.2, §10.3).

The backend builds it; the validator CLI parses it with `parse_dataset` and scores
it with `edu_subnet.scoring`.

Policies:
- `edu-v2`: each lecture's 72-hour window opens at the check YouTube first answered (`eligibility_start_at`, null
  until then), at least 48 hours after the lecture ends (`edu_subnet.timing`).
- `edu-v1`: the earlier rule, a window fixed from 48 to 120 hours after the end. Still read, so a validator that
  updates first keeps working until the platform serves `edu-v2`.
"""
from datetime import datetime

from . import timing
from .scoring import LectureRecord

SCORING_POLICY = "edu-v2"
EARLIER_POLICY = "edu-v1"


def miner_ref(hotkey: str, registration_block: int) -> str:
    """A miner registration: the hotkey plus the block it registered at.

    A hotkey that deregisters and registers again is a new registration, so old
    lectures never move to the new one (spec §3.2).
    """
    return f"{hotkey}@{registration_block}"


def _time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _window_start(policy: str, row: dict, actual_end: datetime) -> datetime | None:
    """When the lecture's window opened. Under `edu-v2` it must be the due time of one of its checks, or the whole
    dataset is refused: a window can't be moved."""
    if policy == EARLIER_POLICY:
        return timing.first_check_at(actual_end)
    start = _time(row.get("eligibility_start_at"))
    if start is not None and not timing.is_window_start(actual_end, start):
        raise ValueError(f"lecture {row['lecture_id']}: a window can't open at {start.isoformat()}")
    return start


def parse_dataset(payload: dict) -> tuple[datetime, list[LectureRecord]]:
    """Return the dataset's read time and its lecture records."""
    policy = payload.get("scoring_policy")
    if policy not in (SCORING_POLICY, EARLIER_POLICY):
        raise ValueError(f"unsupported scoring policy {policy!r}")
    lectures = payload["lectures"]
    if payload.get("row_count") != len(lectures):
        raise ValueError("row_count does not match the number of lectures")
    records = []
    for row in lectures:
        actual_end = _time(row["actual_end_at"])
        records.append(LectureRecord(lecture_id=row["lecture_id"],
                                     tutor_id=row["tutor_id"],
                                     miner=row["miner"],
                                     actual_end_at=actual_end,
                                     live_minutes=row["live_minutes"],
                                     fetched_at=_time(row["fetched_at"]),
                                     completed=row["completed"],
                                     disqualified=row["disqualified"],
                                     window_start_at=_window_start(policy, row, actual_end)))
    return datetime.fromisoformat(payload["read_at"]), records
