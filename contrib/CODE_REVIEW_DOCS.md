# Code review

Every pull request is reviewed before it is merged. This is what a review looks for.

## Does it keep validators in agreement?

This comes first. Every validator must compute the same weights from the same dataset.

- No floats in scoring, and no rounding before the last step.
- No clock, network, or randomness inside the rules. Time is passed in.
- No behavior that depends on the machine: the order of a set, the local time zone, the locale.

## Is it fair to miners?

- A lecture counts once, for the registration it was booked under.
- Every lecture gets the same window, whatever happens outside the miner's control.
- When the data is missing or invalid, the validator burns the round. It never guesses.

## Is it tested?

- New behavior has a test that fails without the change.
- Boundaries are tested: the first and last instant of a window, zero, one, and many.
- The tests run without a network, a chain, or a real wallet.

## Is it compatible?

- A change to the dataset gets a new policy name, and the earlier policy is still read.
- A command keeps its options. A removed or renamed option is a breaking change, and the changelog says so.

## Is it safe?

- No key, token, or sign-up link is printed or logged.
- Files that hold credentials are created readable by their user only.
- Requests are signed, and a signature is never reused.

## Is it clear?

- Names say what things are. Rules that are numbers have names.
- Messages say what happened and what to do next, in plain sentences.
- The docs and the changelog describe the change.

## For reviewers

- Review within a few days, or say when you can.
- Be specific and kind. Say what you would change and why.
- Approve when the change is right, not when it is perfect.
