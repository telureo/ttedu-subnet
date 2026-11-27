"""Client for the platform API (docs/platform-api.md). Requests are signed with Bittensor keys."""
import json
import secrets
import time
from collections.abc import Callable
from datetime import datetime

import httpx
from bittensor_wallet import Keypair

from . import protocol
from .signing import sign


class PlatformError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(f"{detail} (HTTP {status})")
        self.status = status
        self.detail = detail


def authorization_message_for(request: dict, miner_coldkey: str) -> bytes:
    """The message to sign, built from what GET /api/affiliation/{code} returned."""
    return protocol.authorization_message(
        platform_domain=request["platform_domain"], network_id=request["network"], subnet_id=request["netuid"],
        miner_hotkey=request["miner_hotkey"], miner_coldkey=miner_coldkey,
        tutor_account_id=request["tutor_account_id"], code=request["code"],
        issued_at=datetime.fromisoformat(request["issued_at"]),
        expires_at=datetime.fromisoformat(request["expires_at"])).encode()


class Platform:
    def __init__(self, base_url: str, http: httpx.Client | None = None,
                 clock: Callable[[], float] = time.time):
        self.base_url = base_url.rstrip("/")
        self.http = http or httpx.Client(timeout=120)
        self._clock = clock  # unix seconds used to sign requests

    def _send(self, method: str, path: str, *, hotkey: Keypair | None = None, coldkey: Keypair | None = None,
              payload: dict | None = None) -> dict:
        body = b"" if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        headers = {} if payload is None else {"Content-Type": "application/json"}
        if hotkey is not None:
            timestamp, nonce = int(self._clock()), secrets.token_hex(16)
            signed = protocol.request_payload(method, path, timestamp, nonce, body)
            headers.update({protocol.HOTKEY_HEADER: hotkey.ss58_address,
                            protocol.TIMESTAMP_HEADER: str(timestamp), protocol.NONCE_HEADER: nonce,
                            protocol.SIGNATURE_HEADER: sign(hotkey, signed)})
            if coldkey is not None:
                headers.update({protocol.COLDKEY_HEADER: coldkey.ss58_address,
                                protocol.COLDKEY_SIGNATURE_HEADER: sign(coldkey, signed)})
        response = self.http.request(method, self.base_url + path, content=body, headers=headers)
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise PlatformError(response.status_code, str(detail))
        return response.json()

    def config(self) -> dict:
        """The platform's public settings, among them the network and the subnet it reads agencies from."""
        return self._send("GET", "/api/config")

    # Miners
    def affiliation_request(self, code: str) -> dict:
        return self._send("GET", f"/api/affiliation/{code.strip().upper()}")

    def authorize(self, request: dict, coldkey: Keypair, hotkey: Keypair) -> dict:
        message = authorization_message_for(request, coldkey.ss58_address)
        return self._send("POST", f"/api/affiliation/{request['code']}/authorize",
                          payload={"miner_coldkey": coldkey.ss58_address,
                                   "coldkey_signature": sign(coldkey, message),
                                   "hotkey_signature": sign(hotkey, message)})

    def tutors(self, hotkey: Keypair) -> dict:
        return self._send("GET", "/api/miner/tutors", hotkey=hotkey)

    def remove_tutor(self, tutor_id: str, hotkey: Keypair, coldkey: Keypair) -> dict:
        return self._send("POST", f"/api/miner/tutors/{tutor_id}/remove", hotkey=hotkey, coldkey=coldkey)

    def report(self, hotkey: Keypair) -> dict:
        return self._send("GET", "/api/miner/report", hotkey=hotkey)

    def signup_link(self, hotkey: Keypair, coldkey: Keypair) -> dict:
        """A one-time link (30 minutes) that creates the agency's account on the website, or adds the agency to the
        account it's opened in. Signed with both keys: that proves the agency is yours, once."""
        return self._send("POST", "/api/miner/signup-link", hotkey=hotkey, coldkey=coldkey)

    def requests(self, hotkey: Keypair) -> dict:
        """Tutors asking to join the agency, each with the code `authorize` takes."""
        return self._send("GET", "/api/miner/requests", hotkey=hotkey)

    def profile(self, hotkey: Keypair) -> dict:
        return self._send("GET", "/api/miner/profile", hotkey=hotkey)

    def set_profile(self, hotkey: Keypair, changes: dict[str, str]) -> dict:
        """Change the given fields of the agency's public profile; "" clears a field."""
        return self._send("PUT", "/api/miner/profile", hotkey=hotkey, payload=changes)

    def credit(self, hotkey: Keypair) -> dict:
        return self._send("GET", "/api/miner/credit", hotkey=hotkey)

    # Validators
    def eligible(self, hotkey: Keypair) -> dict:
        return self._send("GET", "/api/validator/eligible", hotkey=hotkey)

    # Everyone
    def status(self, hotkey: Keypair) -> dict:
        return self._send("GET", "/api/status", hotkey=hotkey)
