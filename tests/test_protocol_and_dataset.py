from datetime import datetime, timezone

import pytest

from edu_subnet.dataset import EARLIER_POLICY, SCORING_POLICY, miner_ref, parse_dataset
from edu_subnet.protocol import authorization_message, request_payload

UTC = timezone.utc


def test_request_payload_binds_every_part():
    base = request_payload("get", "/api/validator/eligible", 1760000000, "n1", b"")
    assert base.startswith(b"edu-request-v1\nGET\n/api/validator/eligible\n1760000000\nn1\n")
    for changed in [request_payload("POST", "/api/validator/eligible", 1760000000, "n1", b""),
                    request_payload("GET", "/api/validator/eligible?x=1", 1760000000, "n1", b""),
                    request_payload("GET", "/api/validator/eligible", 1760000001, "n1", b""),
                    request_payload("GET", "/api/validator/eligible", 1760000000, "n2", b""),
                    request_payload("GET", "/api/validator/eligible", 1760000000, "n1", b"{}")]:
        assert changed != base


def test_miner_ref_includes_the_registration():
    assert miner_ref("5Fhot", 1234) == "5Fhot@1234"
    assert miner_ref("5Fhot", 1234) != miner_ref("5Fhot", 9999)


def dataset(row_changes=None, **changes):
    row = {"lecture_id": "L1", "tutor_id": "T1", "miner": "5Fhot@1", "live_minutes": 120,
           "actual_end_at": "2026-10-14T10:00:00+00:00", "fetched_at": "2026-10-16T10:30:00+00:00",
           "eligibility_start_at": "2026-10-16T10:00:00+00:00", "completed": True, "disqualified": False}
    row.update(row_changes or {})
    payload = {"scoring_policy": SCORING_POLICY, "read_at": "2026-10-16T10:45:00+00:00",
               "row_count": 1, "lectures": [row]}
    payload.update(changes)
    return payload


def test_parse_dataset():
    assert SCORING_POLICY == "edu-v2"
    read_at, records = parse_dataset(dataset())
    assert read_at == datetime(2026, 10, 16, 10, 45, tzinfo=UTC)
    assert records[0].live_minutes == 120 and records[0].miner == "5Fhot@1"
    assert records[0].fetched_at == datetime(2026, 10, 16, 10, 30, tzinfo=UTC)
    assert records[0].window_start_at == datetime(2026, 10, 16, 10, 0, tzinfo=UTC)


def test_a_lecture_youtube_has_not_answered_for_has_no_window():
    _, records = parse_dataset(dataset({"eligibility_start_at": None, "live_minutes": None, "fetched_at": None}))
    assert records[0].window_start_at is None


def test_a_window_that_opens_anywhere_but_at_a_check_is_refused():
    for start in ("2026-10-16T09:30:00+00:00",   # before checking starts, 48 hours after the end
                  "2026-10-16T10:01:00+00:00",   # not a check's due time
                  "2026-10-23T10:00:00+00:00"):  # 7 days of checks have passed
        with pytest.raises(ValueError):
            parse_dataset(dataset({"eligibility_start_at": start}))
    _, records = parse_dataset(dataset({"eligibility_start_at": "2026-10-23T09:30:00+00:00"}))  # the last check
    assert records[0].window_start_at == datetime(2026, 10, 23, 9, 30, tzinfo=UTC)


def test_the_earlier_policy_is_still_read_with_its_fixed_window():
    _, records = parse_dataset(dataset({"eligibility_start_at": None}, scoring_policy=EARLIER_POLICY))
    assert records[0].window_start_at == datetime(2026, 10, 16, 10, 0, tzinfo=UTC)  # the end + 48 hours


def test_parse_dataset_rejects_unknown_policy_and_bad_counts():
    with pytest.raises(ValueError):
        parse_dataset(dataset(scoring_policy="other"))
    with pytest.raises(ValueError):
        parse_dataset(dataset(row_count=2))


MESSAGE_FIELDS = dict(platform_domain="edu.example", network_id="test", subnet_id=999,
                      miner_hotkey="5FHotkeyA", miner_coldkey="5FColdkey", tutor_account_id="tutor-1",
                      code="ABCD-EFGH", issued_at=datetime(2026, 10, 15, 9, 0, tzinfo=UTC),
                      expires_at=datetime(2026, 10, 15, 10, 0, tzinfo=UTC))


def test_authorization_message_lists_every_field_in_order():
    message = authorization_message(**MESSAGE_FIELDS)
    keys = [line.split(": ", 1)[0] for line in message.splitlines()]
    assert keys == ["purpose", "platform_domain", "network_id", "subnet_id", "miner_hotkey",
                    "miner_coldkey", "tutor_account_id", "code", "issued_at", "expires_at",
                    "authorization_version"]
    assert "purpose: authorize_tutor_affiliation" in message
    assert "expires_at: 2026-10-15T10:00:00Z" in message


def test_authorization_message_rejects_line_breaks_and_naive_times():
    with pytest.raises(ValueError):
        authorization_message(**{**MESSAGE_FIELDS, "platform_domain": "edu.example\npurpose: transfer"})
    with pytest.raises(ValueError):
        authorization_message(**{**MESSAGE_FIELDS, "issued_at": datetime(2026, 10, 15, 9, 0)})
