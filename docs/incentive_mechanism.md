# Incentive mechanism

TTedu rewards tutor agencies for live teaching that people choose to watch. This page is the whole mechanism. Every rule here is code in [`src/edu_subnet`](../src/edu_subnet), and the test suite checks each one.

- [The measure](#the-measure)
- [A lecture's clock](#a-lectures-clock)
- [Which lectures count](#which-lectures-count)
- [From minutes to weight](#from-minutes-to-weight)
- [Burn](#burn)
- [A worked example](#a-worked-example)
- [What a validator refuses](#what-a-validator-refuses)
- [Try it yourself](#try-it-yourself)

## The measure

A lecture's score is the minutes people spent watching it **while it was live**, as YouTube Analytics reports them: the LIVE row of `estimatedMinutesWatched` for the lecture's video.

- Replays never count. The ON_DEMAND row is ignored.
- There is no cap and no scaling. A lecture watched live for 6,000 minutes scores 6,000.
- The score measures live audience, not teaching quality.

The exact query is built in [`metric.py`](../src/edu_subnet/metric.py). Telureo sends it, and a validator repeats the same query with its own read-only access to check the answer.

## A lecture's clock

Every lecture keeps its own clock, from the minute it actually ends.

| Step | When | What happens |
|---|---|---|
| Waiting | The first 48 hours after the end | Nothing is asked. YouTube needs time to work out a lecture's numbers. |
| Checking | From 48 hours after the end, every 30 minutes | Telureo asks YouTube for the lecture's live watch-minutes, until YouTube answers. |
| Counting | 72 hours from YouTube's first answer | The lecture counts. Its number is read every 30 minutes, and each reading replaces the last. |
| Final | After the 72 hours | The lecture stops counting. Its last number stays as its score in the rankings. |

The details that matter:

- **The first answer opens the window.** The first check YouTube answers with a LIVE row opens the lecture's scoring window, at that check's due time. The window lasts exactly 72 hours for every lecture, however late the answer comes. A slow answer never takes counting time away from a lecture.
- **The latest value counts.** YouTube can change a number after its first answer, for example when its spam filter removes views. Each reading replaces the last, so the score follows YouTube.
- **Freshness.** A number counts only while it is less than 60 minutes old. If Telureo can't read a new number in time, the lecture stops counting until a new reading arrives.
- **The waiting limit.** Checking goes on for 7 days. A lecture YouTube hasn't answered for by then never opens a window and is never counted.

The clock is [`timing.py`](../src/edu_subnet/timing.py).

## Which lectures count

At any moment, a lecture counts when all of these are true:

1. It was a delivered lecture on Telureo.
2. It isn't disqualified. Telureo can exclude a lecture that breaks its published rules, and each decision is logged with its reason.
3. Its miner registration is on the subnet now. A registration is the hotkey together with the block it registered at. A lecture belongs to the registration its tutor belonged to when the lecture was booked, and it never moves to another one. A hotkey that deregisters and registers again is a new registration, so its old lectures don't count for the new one.
4. The moment is inside the lecture's 72-hour window.
5. It has a number, and that number is fresh.

This is `is_scored` in [`scoring.py`](../src/edu_subnet/scoring.py).

## From minutes to weight

- A lecture's score is its latest live watch-minutes.
- A miner's score is the sum of the scores of its lectures that count now.
- A miner's share is its score divided by the total of all miners' scores.
- A miner's weight is its share of the part that isn't burned.

Minutes are whole numbers and shares are exact fractions, so every validator computes the same weights from the same dataset. A lecture is never counted twice. A dataset that lists one twice is refused.

## Burn

**The burn rate is 70%.** TTedu is in its test phase, with few agencies so far. During it, a validator puts 70% of its weight on the subnet owner's UID, where it is burned, and shares the other 30% among the miners.

The rate is `BURN_RATE` in [`scoring.py`](../src/edu_subnet/scoring.py). A change to it is listed in the [changelog](../CHANGELOG.md) before it takes effect.

A validator burns everything when there is nothing to reward:

- every miner score is zero, or
- it can't get a valid dataset from Telureo.

A validator never invents scores. An unreachable or invalid dataset means a burn round, and the next round tries again.

## A worked example

Three lectures are inside their windows, with fresh numbers.

| Lecture | Miner | Live watch-minutes |
|---|---|---|
| A | Agency 1 | 600 |
| B | Agency 1 | 300 |
| C | Agency 2 | 100 |

Agency 1 scores 900 and Agency 2 scores 100. The total is 1,000, so Agency 1's share is 9/10 and Agency 2's is 1/10.

With the burn rate at 70%, the miners share 30% of the weight. Agency 1's weight is 27/100, Agency 2's is 3/100, and 70/100 goes to the subnet owner's UID.

An hour later YouTube lowers lecture A to 400. Agency 1 now scores 700 of 800, so its share is 7/8 and Agency 2's is 1/8.

When lecture C's 72 hours end, it stops counting. Agency 1 then holds the whole 30%, until another agency's lecture starts counting.

## What a validator refuses

A validator burns the round, instead of scoring, when any of these is true of the dataset:

- It names a scoring policy this code doesn't know.
- Its row count doesn't match its lectures.
- It lists a lecture twice.
- A window opens anywhere but at one of the lecture's own checks: 48 hours after its end plus a whole number of 30-minute steps, within the 7 days. A window can't be moved.
- It was read more than 5 minutes away from the validator's own clock.

These checks are in [`dataset.py`](../src/edu_subnet/dataset.py) and [`validator.py`](../src/edu_subnet/validator.py).

## Try it yourself

A listed validator can save the dataset and score it by hand:

```bash
ttedu validator fetch --out data.json
ttedu validator score --file data.json --netuid 35
```

Anyone can score a saved dataset without a wallet:

```bash
ttedu validator score --file data.json --offline
```

The live result of these rules is on the [leaderboard](https://subnet.telureo.com), with every lecture's clock.
