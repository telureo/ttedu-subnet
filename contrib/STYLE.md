# Style

The aim is code a careful reader can check in one sitting.

- [Python](#python)
- [Numbers and time](#numbers-and-time)
- [Words people read](#words-people-read)
- [Comments and docstrings](#comments-and-docstrings)
- [Tests](#tests)
- [Commits](#commits)

## Python

- Python 3.11 or newer, with type hints on every function.
- Small functions with one job. The rules in `scoring.py` and `timing.py` are pure functions: no network, no clock, no files. Time is always passed in.
- Dataclasses for records, frozen where the value shouldn't change.
- Standard library first. A new dependency needs a good reason, since every validator installs it.
- Lines up to 120 characters.

## Numbers and time

Every validator must compute the same weights from the same dataset. So:

- **Minutes are integers.** Never a float.
- **Weights are exact fractions** (`fractions.Fraction`). They become floats only at the moment they are handed to the chain.
- **Every datetime is timezone-aware, in UTC.** A naive datetime raises an error.
- **Intervals are half-open.** A window includes its first instant and excludes its last.
- Rounding happens only for display, and the function that rounds says how.

## Words people read

Everything the command line prints follows a few rules:

- Plain sentences. Say what happened, then what to do.
- No em dashes and no semicolons. Use a comma, plain words, or two sentences. `tests/test_copy.py` checks this.
- No tracebacks for expected problems. A wrong wallet name, a wrong password, or a refused request is said in one line.
- Never print a key, a signature's secret input, or a token.

## Comments and docstrings

- A docstring says what the function is for and what a reader couldn't see from the code.
- A comment explains why, not what.
- Where a number is a rule, name it: `FRESHNESS_LIMIT`, not `60`.

## Tests

- A test's name is a sentence about the behavior: `test_a_late_answer_still_gets_72_hours`.
- One behavior per test.
- Boundaries get their own tests: the first instant of a window, the last, one second after.
- Tests never touch the network, the chain, or the real wallet folder.

## Commits

- The first line says what the change does, in the imperative, in 72 characters or fewer.
- The body, when needed, says why.
