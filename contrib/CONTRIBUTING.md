# Contributing to TTedu

Thank you for helping. TTedu's code is small on purpose: agencies and validators should be able to read all of it.

- [Ways to help](#ways-to-help)
- [Set up](#set-up)
- [Make a change](#make-a-change)
- [Changes to the incentive rules](#changes-to-the-incentive-rules)
- [Security](#security)

## Ways to help

- **Report a bug.** Open an [issue](https://github.com/telureo/ttedu-subnet/issues) with the command you ran and what it printed. Never paste a key, a seed phrase, or a sign-up link.
- **Improve the docs.** If a guide left you guessing, tell us where, or send the fix.
- **Send a fix or a feature.** For anything larger than a small fix, open an issue first, so we can agree on the approach before you write it.

## Set up

You need Python 3.11 or newer and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/telureo/ttedu-subnet.git
cd ttedu-subnet
uv sync
uv run pytest
```

The tests need no wallet, no network, and no chain. They run in under a minute.

## Make a change

1. Create a branch from `main`.
2. Write the change with its test. Every rule in this repository has a test that would fail without it.
3. Run `uv run pytest`.
4. Update the docs that describe what you changed.
5. Open a pull request and say what it changes and why.

[DEVELOPMENT_WORKFLOW.md](DEVELOPMENT_WORKFLOW.md) has the details, [STYLE.md](STYLE.md) how the code is written, and [CODE_REVIEW_DOCS.md](CODE_REVIEW_DOCS.md) what a review looks for.

## Changes to the incentive rules

`scoring.py`, `timing.py`, and `dataset.py` decide who earns what. A change there affects every agency and validator, so it follows a stricter path:

1. It starts as an issue that says what changes, why, and who gains or loses.
2. It is merged only with the subnet owner's agreement.
3. It is listed in [CHANGELOG.md](../CHANGELOG.md) and announced before it takes effect.
4. The code keeps reading the earlier dataset format until Telureo serves the new one, so validators can update at their own pace.

## Security

Please report a security problem privately. See [SECURITY.md](../SECURITY.md).
