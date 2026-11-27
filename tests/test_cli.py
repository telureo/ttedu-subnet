import pytest
import typer
from bittensor_wallet import Wallet
from bittensor_wallet.errors import KeyFileError
from typer.testing import CliRunner

from edu_subnet import cli
from edu_subnet.client import PlatformError


@pytest.fixture(autouse=True)
def no_saved_choices(monkeypatch, tmp_path):
    """Each test starts without btcli's saved choices or Bittensor's wallet variables from the machine it runs on."""
    monkeypatch.setenv("BTCLI_CONFIG_PATH", str(tmp_path / "no-btcli-config.yml"))
    for name in ("BT_WALLET_NAME", "BT_WALLET_HOTKEY", "BT_WALLET_PATH", "EDU_API_URL"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def wallet_path(tmp_path):
    wallet = Wallet(name="test", hotkey="default", path=str(tmp_path))
    wallet.create_new_coldkey(use_password=False, overwrite=True, suppress=True)
    wallet.create_new_hotkey(use_password=False, overwrite=True, suppress=True)
    return str(tmp_path), wallet


class FakePlatform:
    calls: list = []
    switching_from = None
    saved = {"name": "", "description": "", "logo_url": ""}

    def __init__(self, api):
        self.api = api

    def affiliation_request(self, code):
        return {"code": code, "tutor_account_id": "tutor-1", "tutor_name": "Ada",
                "miner_hotkey": FakePlatform.hotkey, "issued_at": "2026-10-15T09:00:00+00:00",
                "expires_at": "2026-10-15T10:00:00+00:00", "platform_domain": "edu.test",
                "network": "test", "netuid": 7, "switching_from": FakePlatform.switching_from}

    def authorize(self, request, coldkey, hotkey):
        FakePlatform.calls.append(("authorize", coldkey.ss58_address, hotkey.ss58_address))
        return {"tutors_in_agency": 2}

    def profile(self, hotkey):
        return {"hotkey": hotkey.ss58_address, **FakePlatform.saved}

    def set_profile(self, hotkey, changes):
        if not FakePlatform.registered:
            raise PlatformError(409, "This hotkey is not registered on subnet 35.")
        if changes.get("name") in FakePlatform.taken:
            raise PlatformError(409, "Another agency already uses this name. Choose a different one.")
        FakePlatform.calls.append(("set_profile", changes))
        FakePlatform.saved = {**FakePlatform.saved, **changes}
        return self.profile(hotkey)

    top_ups: list = []

    def credit(self, hotkey):
        return {"on": True, "credits": 12, "booking_credits": 1, "bookings_left": 12, "treasury": "5Treasury",
                "network": "finney", "entries": [], "top_ups": FakePlatform.top_ups}

    def signup_link(self, hotkey, coldkey):
        if not FakePlatform.registered:
            raise PlatformError(409, f"This hotkey is not registered on subnet {FakePlatform.netuid}.")
        FakePlatform.calls.append(("signup_link", hotkey.ss58_address, coldkey.ss58_address))
        return {"url": "https://telureo.test/agency/signup?token=abc", "expires_at": "2026-10-15T09:30:00+00:00",
                "linked_to": FakePlatform.linked_to, "agency": {"name": "Bright Minds", "description": "", "logo_url": ""}}

    linked_to = None
    waiting: list = []
    taken: set = set()  # names another agency uses
    registered = True
    netuid = 35

    def config(self):
        return {"netuid": FakePlatform.netuid, "network": "finney" if FakePlatform.netuid else "test"}

    def requests(self, hotkey):
        return {"requests": FakePlatform.waiting}


def run(args):
    return CliRunner().invoke(cli.app, args)


def test_help_lists_the_commands():
    result = run(["--help"])
    assert result.exit_code == 0 and "miner" in result.output and "validator" in result.output
    assert "authorize" in run(["miner", "--help"]).output
    assert "connect-youtube" in run(["validator", "--help"]).output


def test_authorize_shows_the_request_and_signs_with_both_keys(monkeypatch, wallet_path):
    path, wallet = wallet_path
    FakePlatform.hotkey, FakePlatform.calls = wallet.hotkey.ss58_address, []
    monkeypatch.setattr(cli, "Platform", FakePlatform)
    result = run(["miner", "authorize", "--code", "ABCD-EFGH", "--yes", "--wallet.name", "test",
                  "--wallet.path", path])
    assert result.exit_code == 0, result.output
    assert "Tutor:          Ada" in result.output and "cannot move funds" in result.output
    assert "Code expires:   2026-10-15 10:00 UTC" in result.output
    assert "now in your agency (2 of 5 tutors)" in result.output
    assert FakePlatform.calls == [("authorize", wallet.coldkeypub.ss58_address, wallet.hotkey.ss58_address)]


def test_authorize_refuses_a_code_for_another_hotkey(monkeypatch, wallet_path):
    path, _ = wallet_path
    FakePlatform.hotkey, FakePlatform.calls = "5SomeoneElse", []
    monkeypatch.setattr(cli, "Platform", FakePlatform)
    result = run(["miner", "authorize", "--code", "ABCD-EFGH", "--yes", "--wallet.name", "test",
                  "--wallet.path", path])
    assert result.exit_code == 1 and "not your hotkey" in result.output
    assert FakePlatform.calls == []


def test_authorize_says_when_the_tutor_is_switching_agency(monkeypatch, wallet_path):
    path, wallet = wallet_path
    FakePlatform.hotkey, FakePlatform.calls, FakePlatform.switching_from = wallet.hotkey.ss58_address, [], "5OldAgency"
    monkeypatch.setattr(cli, "Platform", FakePlatform)
    result = run(["miner", "authorize", "--code", "ABCD-EFGH", "--yes", "--wallet.name", "test",
                  "--wallet.path", path])
    FakePlatform.switching_from = None
    assert result.exit_code == 0, result.output
    assert "Switching from: 5OldAgency" in result.output and "will move to your agency" in result.output


def test_profile_shows_and_changes_only_the_given_fields(monkeypatch, wallet_path):
    path, _ = wallet_path
    FakePlatform.calls, FakePlatform.saved = [], {"name": "Bright Minds", "description": "", "logo_url": ""}
    monkeypatch.setattr(cli, "Platform", FakePlatform)
    shown = run(["miner", "profile", "--wallet.name", "test", "--wallet.path", path])
    assert shown.exit_code == 0 and "Name:         Bright Minds" in shown.output
    assert "Description:  (not set)" in shown.output and FakePlatform.calls == []

    changed = run(["miner", "profile", "--description", "Maths and physics.", "--logo-url", "",
                   "--wallet.name", "test", "--wallet.path", path])
    assert changed.exit_code == 0, changed.output
    assert FakePlatform.calls == [("set_profile", {"description": "Maths and physics.", "logo_url": ""})]
    assert "Saved." in changed.output and "Description:  Maths and physics." in changed.output


def test_credit_shows_the_balance_and_points_to_the_dashboard(monkeypatch, wallet_path):
    path, _ = wallet_path
    FakePlatform.calls = []
    FakePlatform.top_ups = [{"extrinsic": None, "status": "pending", "reason": None, "credits": None},
                            {"extrinsic": "4500123-5", "status": "credited", "reason": None, "credits": 5}]
    monkeypatch.setattr(cli, "Platform", FakePlatform)
    shown = run(["miner", "credit", "--wallet.name", "test", "--wallet.path", path])
    assert shown.exit_code == 0, shown.output
    assert "12 credits, enough for 12 bookings at 1 credit each" in shown.output
    assert "4500123-5        added to your credit  5 credits" in shown.output
    assert "on its way       the platform checks it on the chain" in shown.output
    assert "Add credit from your agency's dashboard." in shown.output and "Treasury" not in shown.output
    assert FakePlatform.calls == []  # it only reads
    # Credit is added only from the dashboard, so the command reports nothing.
    assert run(["miner", "credit", "--extrinsic", "4500123-5", "--wallet.name", "test", "--wallet.path", path]).exit_code != 0


def test_credit_says_what_a_credit_costs_while_buying_is_closed(monkeypatch, wallet_path):
    """Until the dashboard sells credits, the command doesn't send a leader there to add any: it says what one will
    cost, in the subnet's alpha."""
    path, _ = wallet_path
    closed = {"on": True, "credits": 20, "booking_credits": 2, "bookings_left": 10, "treasury": "5Treasury",
              "network": "finney", "buying": False, "alpha_per_credit": 50, "entries": [], "top_ups": []}
    monkeypatch.setattr(FakePlatform, "credit", lambda self, hotkey: closed)
    monkeypatch.setattr(cli, "Platform", FakePlatform)
    shown = run(["miner", "credit", "--wallet.name", "test", "--wallet.path", path])
    assert shown.exit_code == 0, shown.output
    assert "20 credits, enough for 10 bookings at 2 credits each" in shown.output
    assert "Buying credits opens soon in your agency's dashboard, at 50 alpha a credit." in shown.output
    assert "Add credit" not in shown.output and "Treasury" not in shown.output


def test_credits_read_plainly():
    assert [cli._credits(v) for v in (1, 12, 1.5, 1250, -1, 2_000_000)] == [
        "1 credit", "12 credits", "1.5 credits", "1,250 credits", "-1 credit", "2,000,000 credits"]


def test_signup_prints_a_one_time_link_signed_with_both_keys(monkeypatch, wallet_path):
    path, wallet = wallet_path
    FakePlatform.calls, FakePlatform.linked_to = [], None
    monkeypatch.setattr(cli, "Platform", FakePlatform)
    result = run(["miner", "signup", "--wallet.name", "test", "--wallet.path", path])
    assert result.exit_code == 0, result.output
    assert FakePlatform.calls == [("signup_link", wallet.hotkey.ss58_address, wallet.coldkey.ss58_address)]
    assert "within 30 minutes" in result.output and "https://telureo.test/agency/signup?token=abc" in result.output
    FakePlatform.linked_to = "r•••@example.com"
    moved = run(["miner", "signup", "--wallet.name", "test", "--wallet.path", path])
    assert "already has an account (r•••@example.com)" in moved.output


def test_requests_lists_the_tutors_waiting_with_their_codes(monkeypatch, wallet_path):
    path, _ = wallet_path
    monkeypatch.setattr(cli, "Platform", FakePlatform)
    FakePlatform.waiting = []
    assert "No tutor is asking" in run(["miner", "requests", "--wallet.name", "test", "--wallet.path", path]).output
    FakePlatform.waiting = [{"code": "ABCD-EFGH", "tutor_name": "Nora", "tutor_account_id": "t-1",
                             "asked_at": "2026-10-15T09:00:00+00:00", "expires_at": "2026-10-22T09:00:00+00:00",
                             "switch": True}]
    listed = run(["miner", "requests", "--wallet.name", "test", "--wallet.path", path])
    assert "ABCD-EFGH  Nora, switching from another agency" in listed.output
    assert "ttedu miner authorize --code" in listed.output


def help_of(args: list[str], columns: int = 100) -> str:
    result = CliRunner().invoke(cli.app, args, env={"COLUMNS": str(columns)})
    return result.output


def test_the_main_help_opens_with_the_wordmark():
    for args in ([], ["--help"]):
        out = help_of(args)
        assert cli.WORDMARK[0] in out and cli.WORDMARK[-1] in out
        assert out.index(cli.TAGLINE) < out.index("Usage:")
        assert "TTedu: commands for agencies (miners) and validators." in out


def test_the_groups_and_commands_keep_their_plain_help():
    for args in (["miner", "--help"], ["validator", "--help"], ["status", "--help"]):
        out = help_of(args)
        assert "Usage:" in out
        assert cli.WORDMARK[0] not in out and cli.TAGLINE not in out


def test_a_narrow_window_shows_the_name_on_one_line():
    out = help_of(["--help"], columns=40)
    assert cli.WORDMARK[0] not in out
    assert " TTedu\n" in out and cli.TAGLINE in out



# ----------------------------------------------------------------------------- choosing the wallet, like btcli

def ask(monkeypatch, args, answers):
    """Runs the command as a person at a terminal would, typing the answers."""
    monkeypatch.setattr(cli, "_interactive", lambda: True)
    return CliRunner().invoke(cli.app, args, input="".join(f"{a}\n" for a in answers))


def test_it_talks_to_telureo_unless_told_otherwise():
    assert cli.DEFAULT_API == "https://telureo.com" and cli.NETUID == 35


def test_a_wallet_left_out_is_asked_for_with_the_only_one_as_the_answer(monkeypatch, wallet_path):
    path, _ = wallet_path
    FakePlatform.saved = {"name": "Bright Minds", "description": "", "logo_url": ""}
    monkeypatch.setattr(cli, "Platform", FakePlatform)
    result = ask(monkeypatch, ["miner", "profile", "--wallet.path", path], ["", ""])  # Enter, Enter
    assert result.exit_code == 0, result.output
    assert f"Wallets in {path}: test" in result.output and "Which wallet [test]" in result.output
    assert "Hotkeys in wallet test: default" in result.output and "Which hotkey [default]" in result.output
    assert "Name:         Bright Minds" in result.output


def test_a_name_that_is_not_there_lists_what_is(monkeypatch, wallet_path):
    path, _ = wallet_path
    monkeypatch.setattr(cli, "Platform", FakePlatform)
    wrong = run(["miner", "profile", "--wallet.name", "tedu", "--wallet.path", path])
    assert wrong.exit_code == 1 and "There is no wallet named tedu" in wrong.output and "Wallets there: test." in wrong.output
    hotkey = run(["miner", "profile", "--wallet.name", "test", "--wallet.hotkey", "tedu-official", "--wallet.path", path])
    assert hotkey.exit_code == 1 and "Wallet test has no hotkey named tedu-official. Its hotkeys: default." in hotkey.output
    assert "Traceback" not in wrong.output + hotkey.output


def test_without_a_terminal_it_takes_the_only_wallet_or_names_the_flag(monkeypatch, wallet_path, tmp_path):
    path, _ = wallet_path
    FakePlatform.saved = {"name": "Bright Minds", "description": "", "logo_url": ""}
    monkeypatch.setattr(cli, "Platform", FakePlatform)
    assert run(["miner", "profile", "--wallet.path", path]).exit_code == 0  # the only wallet and hotkey
    other = Wallet(name="other", hotkey="default", path=path)
    other.create_new_coldkey(use_password=False, overwrite=True, suppress=True)
    two = run(["miner", "profile", "--wallet.path", path])
    assert two.exit_code == 1 and "Say which wallet to use with --wallet.name. There: other, test." in two.output
    # btcli's saved choice settles it, as in btcli.
    (tmp_path / "btcli.yml").write_text("network: finney\nwallet_name: test\nwallet_hotkey: default\nwallet_path: null\n")
    monkeypatch.setenv("BTCLI_CONFIG_PATH", str(tmp_path / "btcli.yml"))
    assert run(["miner", "profile", "--wallet.path", path]).exit_code == 0


def test_a_wrong_coldkey_password_is_said_plainly(tmp_path, capsys):
    (tmp_path / "test").mkdir()
    (tmp_path / "test" / "coldkey").write_text("encrypted")

    class Locked:
        name, hotkey_str, path = "test", "default", str(tmp_path)

        @property
        def coldkey(self):
            raise KeyFileError("Decryption error: Wrong password for decryption.")

    with pytest.raises(typer.Exit):
        cli._coldkey(Locked())
    assert "That password doesn't open the coldkey of wallet test. Nothing was signed." in capsys.readouterr().err
    (tmp_path / "test" / "coldkey").unlink()  # only the public coldkey here, as on a validator's server
    with pytest.raises(typer.Exit):
        cli._coldkey(Locked())
    assert "Run this on the computer that holds the coldkey." in capsys.readouterr().err


def test_a_crash_never_prints_the_values_it_held():
    assert cli.app.pretty_exceptions_show_locals is False


# ----------------------------------------------------------------------------- the guided setup

def test_setup_walks_through_keys_name_and_account(monkeypatch, wallet_path):
    path, wallet = wallet_path
    FakePlatform.calls, FakePlatform.saved, FakePlatform.linked_to = [], {"name": "", "description": "", "logo_url": ""}, None
    FakePlatform.taken, FakePlatform.registered = {"Bright Minds"}, True
    monkeypatch.setattr(cli, "Platform", FakePlatform)
    # Enter for the wallet and the hotkey, a name that is taken, then another, no description, yes to the link.
    result = ask(monkeypatch, ["miner", "setup", "--wallet.path", path],
                 ["", "", "Bright Minds", "", "Clear Minds", "Maths and physics.", "y"])
    assert result.exit_code == 0, result.output
    out = result.output
    assert out.index("Step 1 of 3") < out.index("Step 2 of 3") < out.index("Step 3 of 3") < out.index("Next:")
    assert "Setting up your agency on telureo.com, subnet 35 on finney." in out and wallet.hotkey.ss58_address in out
    assert "Another agency already uses this name." in out and "Saved: Clear Minds" in out
    assert "It is not a transaction and moves no funds." in out and "within 30 minutes" in out
    assert "enter an email address, the 6-digit code" in out and "ttedu miner requests" in out
    assert FakePlatform.calls == [("set_profile", {"name": "Clear Minds", "description": "Maths and physics."}),
                                  ("signup_link", wallet.hotkey.ss58_address, wallet.coldkey.ss58_address)]


def test_setup_keeps_a_name_already_set_and_can_stop_before_the_link(monkeypatch, wallet_path):
    path, _ = wallet_path
    FakePlatform.calls, FakePlatform.saved = [], {"name": "Bright Minds", "description": "", "logo_url": ""}
    monkeypatch.setattr(cli, "Platform", FakePlatform)
    result = ask(monkeypatch, ["miner", "setup", "--wallet.path", path], ["", "", "n"])
    assert result.exit_code == 0, result.output
    assert "Name: Bright Minds." in result.output and "do it later with: ttedu miner signup" in result.output
    assert FakePlatform.calls == []


def test_setup_says_how_to_register_a_hotkey_the_subnet_does_not_know(monkeypatch, wallet_path):
    path, _ = wallet_path
    FakePlatform.calls, FakePlatform.saved, FakePlatform.registered = [], {"name": "", "description": "", "logo_url": ""}, False
    monkeypatch.setattr(cli, "Platform", FakePlatform)
    result = ask(monkeypatch, ["miner", "setup", "--wallet.path", path], ["", "", "Clear Minds", ""])
    FakePlatform.registered = True
    assert result.exit_code == 1
    assert "not registered on subnet 35. Register it first with btcli: btcli subnets register --netuid 35" in result.output


def test_authorize_without_a_code_lists_the_requests_and_asks(monkeypatch, wallet_path):
    path, wallet = wallet_path
    FakePlatform.hotkey, FakePlatform.calls = wallet.hotkey.ss58_address, []
    FakePlatform.waiting = [{"code": "ABCD-EFGH", "tutor_name": "Nora", "tutor_account_id": "t-1",
                             "asked_at": "2026-10-15T09:00:00+00:00", "expires_at": "2026-10-22T09:00:00+00:00",
                             "switch": False}]
    monkeypatch.setattr(cli, "Platform", FakePlatform)
    result = ask(monkeypatch, ["miner", "authorize", "--yes", "--wallet.path", path], ["", "", ""])
    assert result.exit_code == 0, result.output
    assert "1. ABCD-EFGH  Nora" in result.output and "now in your agency" in result.output
    assert FakePlatform.calls == [("authorize", wallet.coldkeypub.ss58_address, wallet.hotkey.ss58_address)]
    monkeypatch.setattr(cli, "_interactive", lambda: False)  # a script, with nobody to ask
    script = run(["miner", "authorize", "--yes", "--wallet.path", path])
    assert script.exit_code == 1 and "Say which request to approve with --code." in script.output


def test_it_tells_its_version():
    result = run(["--version"])
    assert result.exit_code == 0 and result.output.strip() == f"ttedu {cli._version()}"
    assert result.output.startswith("ttedu ") and cli._version() != "unknown"


def test_a_platform_with_stand_in_agencies_says_so_before_anything_is_typed(monkeypatch, wallet_path):
    """The live site before it moves to subnet 35 reads agencies from a stand-in (subnet 0): a real hotkey can't set
    up there, and the setup says it at the start, then again in place of a btcli hint that would not help."""
    path, _ = wallet_path
    FakePlatform.calls, FakePlatform.saved = [], {"name": "", "description": "", "logo_url": ""}
    FakePlatform.netuid, FakePlatform.registered = 0, False
    monkeypatch.setattr(cli, "Platform", FakePlatform)
    result = ask(monkeypatch, ["miner", "setup", "--wallet.path", path], ["", "", "Clear Minds", ""])
    FakePlatform.netuid, FakePlatform.registered = 35, True
    out = result.output
    assert result.exit_code == 1
    assert out.startswith("Setting up your agency on telureo.com, with stand-in agencies until it moves to subnet 35.")
    assert out.index("takes only its stand-in agencies") < out.index("Step 1 of 3")
    assert "btcli subnets register" not in out and "use a platform on subnet 35, with --api" in out


def test_signup_says_how_to_register_a_hotkey_the_platform_does_not_know(monkeypatch, wallet_path):
    path, _ = wallet_path
    FakePlatform.calls, FakePlatform.registered = [], False
    monkeypatch.setattr(cli, "Platform", FakePlatform)
    result = run(["miner", "signup", "--wallet.name", "test", "--wallet.path", path])
    FakePlatform.registered = True
    assert result.exit_code == 1 and "Platform:       telureo.com, subnet 35 on finney" in result.output
    assert "not registered on subnet 35. Register it first with btcli: btcli subnets register --netuid 35" in result.output

