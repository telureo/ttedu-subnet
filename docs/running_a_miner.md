# Running an agency (miner)

On TTedu, a miner is a tutor agency. Your hotkey supports up to 5 tutors, and the network rewards your agency for the live audience of the lectures they teach. A good agency finds good teachers, agrees fair pay with them, and helps them improve.

This page is the short path from a wallet to a working agency. The complete guide, with every rule, is [Run an agency](https://docs.telureo.com/agencies/run-an-agency/) in Telureo's docs.

- [What you need](#what-you-need)
- [1. Register a hotkey](#1-register-a-hotkey)
- [2. Install the command line](#2-install-the-command-line)
- [3. Set up your agency](#3-set-up-your-agency)
- [4. Bring your tutors](#4-bring-your-tutors)
- [5. Credit](#5-credit)
- [Day to day](#day-to-day)
- [Rules that affect your rewards](#rules-that-affect-your-rewards)

## What you need

- A Bittensor wallet: a coldkey, and a hotkey for the agency.
- A little TAO for the registration fee.
- Any computer with Python 3.11 or newer. **An agency runs no server and needs no GPU.** You use the command line a few times, on the computer that holds your coldkey. Everything else happens in your dashboard on telureo.com.

## 1. Register a hotkey

Register on subnet 35, as on any Bittensor subnet:

```bash
btcli subnets register --netuid 35 --wallet.name <coldkey> --wallet.hotkey <hotkey>
```

One coldkey may own several miner and validator hotkeys, and each hotkey has one role.

As on every subnet, a registration that earns nothing can be replaced when new miners register. Register when your tutors are ready to teach.

## 2. Install the command line

```bash
git clone https://github.com/telureo/ttedu-subnet.git
cd ttedu-subnet
scripts/install.sh            # creates .venv and installs ttedu in it
source .venv/bin/activate
ttedu --version
```

On Windows, or to do it by hand, create a virtual environment and run `pip install -e .` in it.

`ttedu` talks to telureo.com. Keep your computer's clock synchronized, because signed requests are refused when it is more than a minute off.

## 3. Set up your agency

Run the guided setup on the computer that holds your coldkey:

```bash
ttedu miner setup
```

It asks which wallet and hotkey to use, as btcli does. Then it sets your agency's public name and creates its account on telureo.com.

Creating the account signs with your hotkey and the coldkey that owns it, which proves the agency is yours. Signing is not a transaction and can't move funds. The command prints a link that works once, for 30 minutes. Open it, give an email, confirm it with the 6-digit code, and choose a password.

From then on you sign in on telureo.com like anyone else. Your dashboard is where your agency works: its tutors, its credit, its scores, and its public profile.

`python neurons/miner.py` starts the same guided setup.

## 4. Bring your tutors

Tutors choose an agency by its name and ask to join. Their requests appear under **Tutors** in your dashboard, with each tutor's name, subjects, and LinkedIn profile. Approve or decline each one. A request stays open for 7 days.

You can answer from the command line instead:

```bash
ttedu miner requests
ttedu miner authorize --code ABCD-EFGH
```

Your agency gets its own public page as soon as it has a name, at `telureo.com/agencies/<your-name>`, and its place on the [leaderboard](https://subnet.telureo.com).

## 5. Credit

Each lecture your tutors book uses 2 credits of your agency's credit. That keeps booking open to real teaching and closed to spam.

- A credit costs 50 alpha, the token of subnet 35. That price is fixed.
- Your agency starts with 2 welcome credits, enough for its first lecture.
- You buy credits under **Credit** in your dashboard, from any wallet that holds the subnet's alpha. Your agency's own miner wallet works too, so the alpha your agency earns can pay for its credits.
- A used credit is never refunded, and credits can't be turned back into alpha.

## Day to day

```bash
ttedu miner tutors                       # your tutors (up to 5)
ttedu miner report                       # your agency's scores and lectures (--json for everything)
ttedu miner credit                       # your credits, and how many bookings they pay for
ttedu miner profile                      # your public profile (--name, --description, --logo-url change it)
ttedu miner remove --tutor <account-id>  # needs your coldkey
ttedu status                             # what Telureo knows about your hotkey
```

Every command asks for a wallet, hotkey, or tutor you leave out. It also takes the usual `--wallet.name`, `--wallet.hotkey`, and `--wallet.path`.

## Rules that affect your rewards

- **Your score is your tutors' live audience.** Only live watch-minutes count, each lecture for 72 hours. [Incentive mechanism](incentive_mechanism.md) has every rule.
- **One lecture per tutor per day (UTC)**, 10 to 120 minutes long.
- **A lecture counts for the registration it was booked under.** A tutor who switches agency takes their booked lectures along. Lectures already streamed stay with the old agency.
- **If your hotkey is deregistered**, lectures streamed for that registration earn no rewards, and your tutors can switch at once.
- **Your agency answers for its tutors' lectures.** Violations of Telureo's rules give your agency points, and at 5 points in 30 days it can't book for 30 days. [How moderation works](https://docs.telureo.com/rules/moderation/) has every level, and how to appeal.

Questions about your agency: [write to us](https://telureo.com/company#contact).
