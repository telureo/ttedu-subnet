# Development workflow

- [Branches](#branches)
- [Pull requests](#pull-requests)
- [Tests](#tests)
- [Versions](#versions)
- [Releases](#releases)
- [Dataset policies](#dataset-policies)

## Branches

- `main` is always releasable. Validators run it.
- Work happens on short branches from `main`: `fix/short-name` for a fix, `feature/short-name` for something new, `docs/short-name` for words only.
- Nothing is pushed straight to `main`. Every change arrives through a pull request.

## Pull requests

- One purpose per pull request. A small one is reviewed quickly.
- The description says what changes and why. Link the issue it answers.
- CI must pass: the tests run on Python 3.11, 3.12, 3.13, and 3.14.
- A pull request that touches scoring, timing, or the dataset also updates `CHANGELOG.md` and the docs.
- Pull requests are squashed when merged, so `main` reads as one line per change.

## Tests

```bash
uv run pytest                     # everything
uv run pytest tests/test_scoring.py
uv run pytest -k window           # tests whose name mentions a word
```

The tests use no network and no chain. Telureo's API and the chain are replaced by small fakes inside the tests, and wallets are created in temporary folders.

`tests/test_copy.py` reads every message the package prints. It fails on an em dash or a semicolon, because the command line speaks in plain sentences.

## Versions

The version is in `pyproject.toml`, and `ttedu --version` prints it.

- While the version starts with 0, the second number goes up for a change in behavior, and the third for fixes.
- A change to the rules, or to what a command does, always moves the second number.

## Releases

1. Update `version` in `pyproject.toml` and in `min_compute.yml`, and run `uv lock`.
2. Add the release to `CHANGELOG.md`, with its date.
3. Merge to `main` through a pull request.
4. Tag the merge commit `vX.Y.Z` and publish a GitHub release with the changelog entry.

## Dataset policies

The dataset Telureo serves names its policy, for example `edu-v2`. The policy says how a lecture's window is described, and a validator refuses a policy it doesn't know.

When the format changes:

1. The new policy gets a new name.
2. The code reads both the new and the earlier policy.
3. Validators update first. Telureo starts serving the new policy afterwards.

So a validator that updates early keeps working, and no round is lost to the change.
