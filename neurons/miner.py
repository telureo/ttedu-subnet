"""The TTedu miner's entry point.

A TTedu miner is a tutor agency, and it runs no server: there is no process to keep alive. An agency is set up
once with its keys, and then works from its dashboard on telureo.com.

    python neurons/miner.py

starts the guided setup, the same as `ttedu miner setup`: your keys, your agency's public name, and its account.
The other agency commands are under `ttedu miner`. See docs/running_a_miner.md.
"""
import sys

from edu_subnet.cli import app


def main() -> None:
    app(prog_name="ttedu", args=["miner", "setup", *sys.argv[1:]])


if __name__ == "__main__":
    main()
