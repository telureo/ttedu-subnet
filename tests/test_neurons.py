"""The entry points in neurons/ open the same commands as the `ttedu` command line."""
import os
import pathlib
import re
import subprocess
import sys

NEURONS = pathlib.Path(__file__).resolve().parents[1] / "neurons"
COLOUR = re.compile(r"\x1b\[[0-9;]*m")
# What makes a terminal's help colourful, on a CI runner too. The help is read here as plain words.
FORCES_COLOUR = ("FORCE_COLOR", "PY_COLORS", "GITHUB_ACTIONS", "CLICOLOR_FORCE")


def help_of(script: str) -> str:
    plain = {key: value for key, value in os.environ.items() if key not in FORCES_COLOUR}
    plain.update(NO_COLOR="1", TERM="dumb", COLUMNS="200")
    done = subprocess.run([sys.executable, str(NEURONS / script), "--help"], capture_output=True, text=True, timeout=120,
                          env=plain)
    assert done.returncode == 0, done.stderr
    return " ".join(COLOUR.sub("", done.stdout).split())


def test_the_validator_entry_point_is_validator_run():
    text = help_of("validator.py")
    assert "ttedu validator run" in text and "--dry-run" in text and "--wallet.hotkey" in text


def test_the_miner_entry_point_is_the_guided_setup():
    text = help_of("miner.py")
    assert "ttedu miner setup" in text and "--wallet.name" in text
