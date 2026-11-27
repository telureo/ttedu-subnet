"""The TTedu validator's entry point, for the process managers validators already use (pm2, systemd, a shell):

    python neurons/validator.py --wallet.name <coldkey> --wallet.hotkey <hotkey>

It is the same as `ttedu validator run`, with the same options. Every 30 minutes it downloads the dataset from
Telureo, scores it with the public rules in `edu_subnet.scoring`, sets weights on subnet 35, and spot-checks a few
lectures against YouTube. See docs/running_a_validator.md.
"""
import sys

from edu_subnet.cli import app


def main() -> None:
    app(prog_name="ttedu", args=["validator", "run", *sys.argv[1:]])


if __name__ == "__main__":
    main()
