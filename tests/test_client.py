import json

import httpx
import pytest
from bittensor_wallet import Keypair

from edu_subnet import protocol
from edu_subnet.client import Platform, PlatformError, authorization_message_for
from edu_subnet.signing import verify_signature


def new_key() -> Keypair:
    return Keypair.create_from_mnemonic(Keypair.generate_mnemonic())


def platform_with(handler) -> Platform:
    return Platform("https://platform.test", http=httpx.Client(transport=httpx.MockTransport(handler)))


def test_signed_requests_verify_against_the_public_payload():
    hotkey, coldkey = new_key(), new_key()
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["request"] = request
        return httpx.Response(200, json={"removed": True})

    platform_with(handler).remove_tutor("tutor-1", hotkey, coldkey)
    request = seen["request"]
    payload = protocol.request_payload(request.method, request.url.raw_path.decode(),
                                       int(request.headers[protocol.TIMESTAMP_HEADER]),
                                       request.headers[protocol.NONCE_HEADER], request.content)
    assert request.url.path == "/api/miner/tutors/tutor-1/remove"
    assert verify_signature(hotkey.ss58_address, payload, request.headers[protocol.SIGNATURE_HEADER])
    assert verify_signature(coldkey.ss58_address, payload, request.headers[protocol.COLDKEY_SIGNATURE_HEADER])


REQUEST = {"code": "ABCD-EFGH", "tutor_account_id": "tutor-1", "tutor_name": "Ada", "miner_hotkey": "",
           "issued_at": "2026-10-15T09:00:00+00:00", "expires_at": "2026-10-15T10:00:00+00:00",
           "platform_domain": "edu.test", "network": "test", "netuid": 7}


def test_authorize_signs_the_message_with_both_keys():
    hotkey, coldkey = new_key(), new_key()
    request = {**REQUEST, "miner_hotkey": hotkey.ss58_address}
    sent = {}

    def handler(http_request: httpx.Request) -> httpx.Response:
        sent.update(json.loads(http_request.content))
        return httpx.Response(201, json={"tutors_in_agency": 1})

    platform_with(handler).authorize(request, coldkey, hotkey)
    message = authorization_message_for(request, coldkey.ss58_address)
    assert sent["miner_coldkey"] == coldkey.ss58_address
    assert verify_signature(coldkey.ss58_address, message, sent["coldkey_signature"])
    assert verify_signature(hotkey.ss58_address, message, sent["hotkey_signature"])


def test_refusals_carry_the_platforms_reason():
    platform = platform_with(lambda request: httpx.Response(410, json={"detail": "This code cannot be used."}))
    with pytest.raises(PlatformError) as refused:
        platform.affiliation_request("abcd-efgh")
    assert refused.value.status == 410 and refused.value.detail == "This code cannot be used."


def test_profile_changes_are_signed_together_with_their_body():
    hotkey = new_key()
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["request"] = request
        return httpx.Response(200, json={"hotkey": hotkey.ss58_address, "name": "Bright Minds"})

    platform_with(handler).set_profile(hotkey, {"name": "Bright Minds"})
    request = seen["request"]
    payload = protocol.request_payload("PUT", "/api/miner/profile", int(request.headers[protocol.TIMESTAMP_HEADER]),
                                       request.headers[protocol.NONCE_HEADER], request.content)
    assert request.method == "PUT" and request.headers["Content-Type"] == "application/json"
    assert json.loads(request.content) == {"name": "Bright Minds"}
    assert verify_signature(hotkey.ss58_address, payload, request.headers[protocol.SIGNATURE_HEADER])
