"""A validator's read-only YouTube access, used only to spot-check the platform (spec §10.6).

`ttedu validator connect-youtube` signs in once with the Google account the subnet owner
invited as "Viewer (limited)" on the platform channels, and stores a refresh token on this
computer. The CLI then repeats the platform's exact query for a few lectures each round.
"""
import base64
import hashlib
import json
import os
import pathlib
import secrets
import time
import urllib.parse

import httpx

from . import metric

SCOPES = ("https://www.googleapis.com/auth/yt-analytics.readonly",
          "https://www.googleapis.com/auth/youtube.readonly")
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REDIRECT_URI = "http://localhost:8765/"
DEFAULT_CREDENTIALS = pathlib.Path.home() / ".edu" / "youtube.json"


class YouTubeAccessError(Exception):
    pass


def start_sign_in(client_id: str) -> tuple[str, str, str]:
    """(url to open, state, PKCE verifier) for a manual sign-in."""
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    url = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": client_id, "redirect_uri": REDIRECT_URI, "response_type": "code",
        "scope": " ".join(SCOPES), "state": state, "code_challenge": challenge,
        "code_challenge_method": "S256", "access_type": "offline", "prompt": "consent"})
    return url, state, verifier


def finish_sign_in(client: dict, pasted_address: str, state: str, verifier: str,
                   http: httpx.Client | None = None) -> dict:
    """Exchange the code from the pasted redirect address for long-lived credentials."""
    params = urllib.parse.parse_qs(urllib.parse.urlparse(pasted_address.strip()).query)
    if "error" in params:
        raise YouTubeAccessError(f"Google refused the sign-in: {params['error'][0]}")
    if params.get("state", [None])[0] != state or "code" not in params:
        raise YouTubeAccessError("That address does not belong to this sign-in. Run the command again.")
    response = (http or httpx.Client(timeout=30)).post(TOKEN_URL, data={
        "code": params["code"][0], "client_id": client["client_id"], "client_secret": client["client_secret"],
        "redirect_uri": REDIRECT_URI, "grant_type": "authorization_code", "code_verifier": verifier})
    if response.status_code >= 400:
        raise YouTubeAccessError(f"Google refused the token exchange: {response.text[:200]}")
    token = response.json()
    if "refresh_token" not in token:
        raise YouTubeAccessError("Google returned no refresh token. Remove the app's access in your Google "
                                 "account settings and sign in again.")
    return {"client_id": client["client_id"], "client_secret": client["client_secret"],
            "refresh_token": token["refresh_token"]}


def save_credentials(credentials: dict, path: pathlib.Path = DEFAULT_CREDENTIALS) -> None:
    """Readable by this user only from the first byte: the file holds a Google refresh token."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)  # an existing file keeps its old mode through os.open
    with os.fdopen(fd, "w") as file:
        file.write(json.dumps(credentials))


def load_credentials(path: pathlib.Path = DEFAULT_CREDENTIALS) -> dict | None:
    return json.loads(path.read_text()) if path.exists() else None


class YouTubeChecker:
    """Repeats the platform's query with the validator's own read-only access."""

    def __init__(self, credentials: dict, http: httpx.Client | None = None):
        self._credentials = credentials
        self._http = http or httpx.Client(timeout=30)
        self._token: tuple[str, float] | None = None

    def _access_token(self) -> str:
        if self._token and self._token[1] > time.monotonic() + 60:
            return self._token[0]
        response = self._http.post(TOKEN_URL, data={**{k: self._credentials[k] for k in ("client_id", "client_secret",
                                                                                         "refresh_token")},
                                                    "grant_type": "refresh_token"})
        if response.status_code >= 400:
            raise YouTubeAccessError(f"Google refused to refresh access: {response.text[:200]}")
        body = response.json()
        self._token = (body["access_token"], time.monotonic() + body.get("expires_in", 3600))
        return self._token[0]

    def live_minutes(self, query: dict) -> int | None:
        response = self._http.get(metric.ANALYTICS_URL, params=query,
                                  headers={"Authorization": f"Bearer {self._access_token()}"})
        if response.status_code >= 400:
            raise YouTubeAccessError(f"YouTube answered {response.status_code}: {response.text[:200]}")
        return metric.live_minutes(response.json())
