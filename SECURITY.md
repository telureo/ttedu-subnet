# Security

## Reporting a problem

Please report a security problem privately. Don't open a public issue for it.

- On GitHub: [Report a vulnerability](https://github.com/telureo/ttedu-subnet/security/advisories/new).
- By email: support@telureo.com

Tell us what you found and how to see it. We will confirm that we received your report, and keep you informed while we fix it.

## What matters most

- Anything that lets a miner gain weight it didn't earn, or take weight from another miner.
- Anything that makes validators compute different weights from the same dataset.
- A way around the signatures on requests, or on a tutor's authorization.
- A leak of a key, a refresh token, or a sign-up link by the command line.

## Your keys

- `ttedu` never asks for a seed phrase. It signs with the wallet files Bittensor's own tools use.
- Signing a request or a tutor's authorization is not a transaction, and it can't move funds.
- A validator's YouTube access is read-only. Its credentials stay on your machine, in `~/.edu/youtube.json`, readable by your user only.
- Nobody from Telureo will ask you for a key, a seed phrase, or a password.
