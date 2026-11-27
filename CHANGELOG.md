# Changelog

Every change to scoring, timing, or the dataset is listed here before it takes effect.

## 0.3.0, November 27, 2026

- Each lecture's 72-hour scoring window opens at YouTube's first answer. Before, it was fixed from 48 to 120 hours after the lecture's end. Now every lecture gets the same 72 hours, however late YouTube answers.
- Checking starts 48 hours after a lecture ends and runs every 30 minutes, for up to 7 days. A lecture YouTube hasn't answered for by then is never counted.
- During the window, each reading replaces the last, so the score is always YouTube's latest value.
- The dataset policy is `edu-v2`, with `checking_from`, `checking_until`, and a window that is `null` until YouTube's first answer. `edu-v1` is still read.
- Validators refuse a dataset whose window opens anywhere but at one of the lecture's own checks.

## 0.2.0, November 24, 2026

- The command line is `ttedu`, with `ttedu --version`.
- `ttedu miner setup` sets up an agency step by step: its keys, its public name, and its account on telureo.com.
- Every command asks for a wallet, hotkey, or tutor left out, as btcli does, and says plainly what is wrong when a name or a password doesn't fit.
- `ttedu validator run` defaults to subnet 35 on finney.

## 0.1.0, November 23, 2026

- The first version: the incentive rules, the dataset format, signed requests, the validator with spot-checks against YouTube, and the agency commands.
