# Platform API used by the subnet

This is the whole contract between the public subnet code and the private platform. The `ttedu` CLI calls only these endpoints. Versions: dataset `edu-v2` (`edu_subnet.dataset.SCORING_POLICY`, which still reads `edu-v1`), signed requests `edu-request-v1` (`edu_subnet.protocol.PREFIX`). Times are ISO 8601 in UTC.

## Signed requests

Endpoints marked *signed* need these headers:

| Header | Value |
|---|---|
| `X-Edu-Hotkey` | The caller's hotkey (SS58) |
| `X-Edu-Timestamp` | Unix seconds, within 60 seconds of the platform's clock |
| `X-Edu-Nonce` | Random, single use, at most 64 characters |
| `X-Edu-Signature` | `0x` hex sr25519 signature of `request_payload(method, path_with_query, timestamp, nonce, body)` |
| `X-Edu-Coldkey`, `X-Edu-Coldkey-Signature` | Only for actions that need the owner's approval: the coldkey and its signature of the same payload |

A replayed nonce, an old timestamp, or a bad signature gets `401`. Errors are JSON: `{"detail": "<reason>"}`.

## Tutor authorization (miners)

`GET /api/affiliation/{code}`: what the miner is about to approve.

```json
{"code": "ABCD-EFGH", "tutor_account_id": "…", "tutor_name": "…", "miner_hotkey": "5…",
 "issued_at": "…", "expires_at": "…", "platform_domain": "…", "network": "…", "netuid": 0,
 "switching_from": "5…" | null}
```

`switching_from` is the hotkey of the tutor's current agency when the tutor is switching. The request is refused (`409`, with the reason and the time the change becomes possible) when the agency-change rules do not allow it now. See "Agency changes" below.

`POST /api/affiliation/{code}/authorize` with

```json
{"miner_coldkey": "5…", "coldkey_signature": "0x…", "hotkey_signature": "0x…"}
```

Both keys sign `edu_subnet.protocol.authorization_message(...)` built from the fields above plus the coldkey. The platform checks both signatures, that the coldkey owns the hotkey on chain, that the hotkey is registered on the subnet and not on the validator list, the 5-tutor cap, and the agency-change rules. For a switch, the tutor's previous affiliation ends at the same moment and their booked lectures that have not started move to the new agency. Answer: `201 {"tutor_account_id", "agency_hotkey", "tutors_in_agency"}`.

## Agency changes

| Change | Allowed | The tutor's booked lectures | Afterwards |
|---|---|---|---|
| Switch to another agency (a new request) | 7 days after joining the current agency, or at once if its hotkey is deregistered | Move to the new agency | Can switch again 7 days later |
| The tutor leaves | Any time outside the freeze | Cancelled | No joining for 14 days |
| The miner removes the tutor | Any time outside the freeze | Cancelled | No joining for 7 days |
| The agency closes, from its dashboard | Any time | Stay booked, and move with the tutor to their next agency | Can join another agency at once |

Freeze: no change of any kind from 12 hours before one of the tutor's lectures starts until its booked end. It continues while the next lecture starts within 12 hours of the previous end. Lectures that have started never move: they count for the agency the tutor was in when they were streamed.

## Agency (miners, signed with the agency hotkey)

| Request | Answer |
|---|---|
| `GET /api/miner/tutors` | `{"tutors": [{"tutor_account_id", "name", "since"}]}` |
| `POST /api/miner/tutors/{tutor_account_id}/remove` | Also coldkey-signed. `{"removed": true, "cancelled_lectures": 1}` |
| `GET /api/miner/report` | Per-tutor current scores, lecture counts, and daily snapshot history |
| `POST /api/miner/signup-link` | Also coldkey-signed. `201 {"url", "expires_at", "linked_to", "agency"}`: a one-time link, for 30 minutes, that creates the agency's account on the website or adds the agency to the account that opens it. `linked_to` is the masked email of the account it is tied to now, if any. |
| `GET /api/miner/requests` | `{"requests": [{"code", "tutor_account_id", "tutor_name", "asked_at", "expires_at", "switch"}]}`: tutors asking to join, oldest first |
| `GET /api/miner/profile` | `{"hotkey", "name", "description", "logo_url"}`, with empty strings when not set |
| `PUT /api/miner/profile` with any of `{"name", "description", "logo_url"}` | Changes only the fields sent, and `""` clears one. The same answer as `GET`. |
| `GET /api/miner/credit` | `{"on", "credits", "booking_credits", "bookings_left", "treasury", "treasury_hotkey", "network", "netuid", "buying", "alpha_per_credit", "entries", "top_ups"}`: the agency's credits, the credits a booking uses, whether credits are sold in the dashboard yet and what one costs in the subnet's alpha, and its latest moves (`{"kind", "credits", "extrinsic", "lecture_id", "note", "created_at"}`) and reported transfers (`{"tx_hash", "extrinsic", "status", "reason", "credits", "submitted_at", "checked_at"}`, with `extrinsic` null while one is on its way). Read-only. |

Agencies count their credit in credits. A credit costs `alpha_per_credit` of the subnet's alpha (50), a price that is fixed. Each lecture a tutor of the agency books uses `booking_credits` (2 to start, a number that may change), taken when the tutor books and never refunded. A booking the credit can't pay is refused with `402`. Each new agency gets 2 welcome credits once, when its account is made. Until a treasury is set, `on` is `false` and booking costs nothing.

Credits are bought only from the agency's dashboard on the website, from any wallet. While `buying` is `false`, the dashboard doesn't sell them yet: credits come from the welcome credits and from the Telureo team, and `top_ups` stays empty. The `treasury` is the wallet that receives what agencies pay, the subnet owner's wallet to start. `netuid` is the subnet whose alpha pays. `treasury_hotkey` is the hotkey the alpha lands on at the treasury, or `null` when it stays on the hotkey it was staked to.

Profile limits: the name is at most 40 characters and unique across agencies regardless of letter case (`409` if taken). The description is at most 200 characters. Both are one line of plain text. The logo is an `https://` link of at most 500 characters. Only a hotkey registered on the subnet and not on the validator list can have a profile. The platform operator can clear abusive or misleading content.

## Validators (signed, with a hotkey on the validator list)

`GET /api/validator/eligible` returns the dataset, from one consistent database read: every lecture that is either still being checked for YouTube's first answer, or inside its scoring window at `read_at`.

How a lecture's clock runs (`edu_subnet.timing`):

- 48 hours after it ends (`checking_from`), the platform checks YouTube Analytics every 30 minutes.
- The first check YouTube answers with the lecture's live watch-minutes opens its scoring window, at that check's due time (`eligibility_start_at`). The window lasts exactly 72 hours (`eligibility_end_at`), however late the answer came.
- Every reading in the window replaces the last one, so the number is always YouTube's latest.
- A lecture YouTube hasn't answered for by `checking_until` (7 days of checks) never opens a window and leaves the dataset.

```json
{"scoring_policy": "edu-v2", "read_at": "…", "network": "…", "netuid": 0, "row_count": 1,
 "lectures": [{
   "lecture_id": "…", "tutor_id": "…", "video_id": "…", "channel_id": "UC…",
   "miner": "5…@1234", "miner_hotkey": "5…", "registration_block": 1234,
   "actual_start_at": "…", "actual_end_at": "…",
   "checking_from": "…", "checking_until": "…", "eligibility_start_at": "… | null", "eligibility_end_at": "… | null",
   "completed": true, "disqualified": false,
   "status": "ok | pending | failing",
   "live_minutes": 120, "latest_slot": 3, "scheduled_fetch_at": "…", "fetched_at": "…",
   "query": {"ids": "channel==UC…", "startDate": "…", "endDate": "…", "dimensions": "liveOrOnDemand",
             "filters": "video==…", "metrics": "estimatedMinutesWatched"},
   "response": {"columnHeaders": […], "rows": […]},
   "last_attempt_at": "…", "last_error": null}]}
```

`eligibility_start_at`, `eligibility_end_at`, `live_minutes` and `fetched_at` are `null` until YouTube's first answer, and `status` is `pending` until then. `latest_slot` counts checks from `checking_from` (0, 1, 2, …). A validator counts a lecture only inside its window, and refuses the whole dataset if a window opens anywhere but at one of the lecture's checks (`edu_subnet.timing.is_window_start`). `query` is the exact YouTube Analytics request, so a validator can repeat it with its own read-only access.

## Status (signed)

`GET /api/status`: `{"hotkey", "role": "validator" | "agency" | "none", "tutors_in_agency", "agency_name"}`.
