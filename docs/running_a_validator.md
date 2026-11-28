# Running a validator

A TTedu validator scores every agency by the live audience of its tutors' lectures, checks Telureo's numbers against YouTube, and sets weights on subnet 35. Every validator works from the same public data with the same code, so their weights agree.

- [What you need](#what-you-need)
- [1. Install](#1-install)
- [2. Get listed](#2-get-listed)
- [3. Connect YouTube](#3-connect-youtube)
- [4. Try a dry run](#4-try-a-dry-run)
- [5. Run it](#5-run-it)
- [What a round does](#what-a-round-does)
- [A closer look at the data](#a-closer-look-at-the-data)
- [Updating](#updating)
- [Troubleshooting](#troubleshooting)

## What you need

- A hotkey registered on subnet 35 with a validator permit.
- A small machine that stays on: 2 CPU cores and 2 GB of memory are enough, with no GPU. See [min_compute.yml](../min_compute.yml).
- Python 3.11 or newer, and a synchronized clock. Signed requests are refused when the clock is more than a minute off.

## 1. Install

```bash
git clone https://github.com/telureo/ttedu-subnet.git
cd ttedu-subnet
scripts/install.sh            # creates .venv and installs ttedu in it
source .venv/bin/activate
ttedu --version
```

The script uses [uv](https://docs.astral.sh/uv/) when you have it, and Python's own venv and pip when you don't. On Ubuntu, Python's venv needs `sudo apt install python3-venv` first.

## 2. Get listed

[Contact the subnet owner](https://telureo.com/company#contact) with your validator's hotkey and the Google account you will use for spot-checks. They add the hotkey to the validator list, and invite the Google account to Telureo's channels as "Viewer (limited)" in YouTube Studio.

Telureo's API serves the dataset only to hotkeys on that list. Check that yours is known:

```bash
ttedu status --wallet.name <coldkey> --wallet.hotkey <hotkey>
```

It should show the role `validator`.

## 3. Connect YouTube

This step is optional, and recommended. With it, your validator checks Telureo's numbers against YouTube itself.

1. In your own Google Cloud project, enable the YouTube Analytics API.
2. Create an OAuth client of type "Desktop app" and download its JSON file.
3. Publish the app, so your sign-in lasts. While the app's status is "Testing", Google ends every sign-in after 7 days. In Google Auth Platform:
   - Under **Branding**, add an authorized domain, a home page, and a privacy policy link. Google asks for both links before it lets you publish. Your own site's pages work, and ours work too: the authorized domain `telureo.com`, the home page `https://telureo.com`, and the privacy policy link `https://telureo.com/privacy`. You need no logo and no terms of service link.
   - Under **Audience**, press **Publish app** and confirm. You are the app's only user, so you don't need Google's verification.
4. Sign in once with the invited Google account:

   ```bash
   ttedu validator connect-youtube --client-file client_secret.json
   ```

   Google warns that it hasn't verified the app. Choose **Advanced**, then **Go to** your app's name. If you signed in while the app was still in Testing, sign in again after you publish.

The access is read-only. Its credentials stay on your machine, in `~/.edu/youtube.json`, readable by your user only.

If the sign-in ever stops working, your validator keeps scoring and setting weights. Only its checks against YouTube stop, and the log says `Spot-check failed this round`.

## 4. Try a dry run

One round, printing the weights without setting them:

```bash
ttedu validator run --dry-run --rounds 1 --wallet.name <coldkey> --wallet.hotkey <hotkey>
```

## 5. Run it

```bash
ttedu validator run --wallet.name <coldkey> --wallet.hotkey <hotkey>
```

It runs on subnet 35 on finney unless you say otherwise, and repeats every 30 minutes. Keep it running with the process manager you already use.

**pm2**

```bash
pm2 start neurons/validator.py --name ttedu-validator --interpreter .venv/bin/python -- \
  --wallet.name <coldkey> --wallet.hotkey <hotkey>
```

**systemd**

Copy [scripts/ttedu-validator.service](../scripts/ttedu-validator.service) to `/etc/systemd/system/`, set your paths and wallet names in it, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ttedu-validator
journalctl -u ttedu-validator -f
```

Options of `ttedu validator run`:

| Option | Default | Meaning |
|---|---|---|
| `--netuid` | `35` | The subnet's netuid |
| `--network` | `finney` | The Bittensor network |
| `--api` | `https://telureo.com` | Telureo's address |
| `--interval` | `1800` | Seconds between rounds |
| `--checks` | `3` | Lectures to spot-check each round |
| `--dry-run` | off | Print the weights without setting them |
| `--rounds` | forever | Stop after this many rounds |
| `--burn-rate` | `0.7` | The part of the weight that is burned, from 0 to 1: it goes to the subnet owner's UID. The default is the subnet's rate. Keep it, so that every validator's weights agree |

## What a round does

1. **Download.** It asks Telureo for the dataset, with a request signed by your hotkey.
2. **Score.** It scores the dataset with [the public rules](incentive_mechanism.md) and maps each miner registration to its UID on the metagraph.
3. **Set weights.** It submits the weights, with commit-reveal when the subnet requires it.
4. **Spot-check.** It repeats the YouTube query of a few lectures with your own access. A difference that is still there after Telureo's next reading is printed as a `RED FLAG`.

What the log lines mean:

| Line | Meaning |
|---|---|
| `Burn rate: 70% of the weight is burned, and 30% goes to the miners.` | Printed once at the start. |
| `Scored 12 lectures, with 30% of the weight for 4 miners and 70% burned.` | A normal round. |
| `Burning this round: every miner score is zero.` | No lecture counts now, so all weight goes to the subnet owner's UID. |
| `Burning this round: the burn rate is 100%.` | The validator was started with `--burn-rate 1`. |
| `Burning this round: no valid dataset from the platform.` | Telureo couldn't be reached, or refused the request. The next round tries again. |
| `Could not set weights this round: ...` | The chain refused or couldn't be reached, for example weights set too soon after a restart. The next round tries again. |
| `Spot-checks are off.` | YouTube isn't connected. See step 3. |
| `Spot-check failed this round: ...` | The check against YouTube didn't work, often because the Google sign-in ended. Scoring and weights go on. Sign in again as in step 3. |

If you ever see a `RED FLAG`, please [tell us](https://telureo.com/company#contact) and other validators. Any validator can confirm it against YouTube.

## A closer look at the data

```bash
ttedu validator fetch --out data.json                # save the dataset
ttedu validator score --file data.json --netuid 35   # score a saved dataset
ttedu validator check --lecture <id>                 # compare one lecture with YouTube
```

[platform_api.md](platform_api.md) describes every field of the dataset.

## Updating

```bash
git pull
scripts/install.sh
```

Then restart the validator. Releases are listed in [CHANGELOG.md](../CHANGELOG.md). A change to the scoring rules is announced before it takes effect, and the code keeps reading the earlier dataset format until Telureo serves the new one.

## Troubleshooting

- **"The request time is off by more than a minute."** Synchronize your computer's clock, for example with `timedatectl set-ntp true`.
- **"This hotkey is not on the validator list."** The subnet owner hasn't added your hotkey yet. See step 2.
- **`Could not set weights this round`, right after a restart.** The chain limits how often weights can be set. The validator tries again next round by itself.
- **Spot-checks fail with a Google error.** Make sure the Google account you signed in with is the one the subnet owner invited, and that the YouTube Analytics API is enabled in your Google Cloud project. Run `connect-youtube` again to sign in afresh.
- **Anything else.** Open an [issue](https://github.com/telureo/ttedu-subnet/issues), or [write to us](https://telureo.com/company#contact).
