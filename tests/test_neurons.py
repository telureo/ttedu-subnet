"""The entry points in neurons/ open the same commands as the `ttedu` command line."""
import pathlib
import subprocess
import sys

NEURONS = pathlib.Path(__file__).resolve().parents[1] / "neurons"


def help_of(script: str) -> str:
    done = subprocess.run([sys.executable, str(NEURONS / script), "--help"], capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    return " ".join(done.stdout.split())


def test_the_validator_entry_point_is_validator_run():
    text = help_of("validator.py")
    assert "ttedu validator run" in text and "--dry-run" in text and "--wallet.hotkey" in text


def test_the_miner_entry_point_is_the_guided_setup():
    text = help_of("miner.py")
    assert "ttedu miner setup" in text and "--wallet.name" in text
