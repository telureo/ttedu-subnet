"""`ttedu`: the subnet CLI for miners (agencies) and validators (spec §12.5)."""
import json
import logging
import os
import pathlib
import sys
from typing import Annotated, NoReturn
from urllib.parse import urlsplit

import httpx
import typer
from rich.console import Console  # comes with typer, which draws its help with it
from typer.core import TyperGroup

from . import scoring
from .client import Platform, PlatformError

# The subnet's wordmark, over the main help only (`ttedu`, `ttedu --help`). The subnet is TTedu, Bittensor subnet 35, as
# its identity on the chain says, and the platform it serves is Telureo. The working commands print what people and
# scripts read, so they stay plain.
NAME = "TTedu"
WORDMARK = (
    '████████╗████████╗███████╗██████╗ ██╗   ██╗',
    '╚══██╔══╝╚══██╔══╝██╔════╝██╔══██╗██║   ██║',
    '   ██║      ██║   █████╗  ██║  ██║██║   ██║',
    '   ██║      ██║   ██╔══╝  ██║  ██║██║   ██║',
    '   ██║      ██║   ███████╗██████╔╝╚██████╔╝',
    '   ╚═╝      ╚═╝   ╚══════╝╚═════╝  ╚═════╝',
)
TAGLINE = "Bittensor subnet 35, the network behind Telureo."
BLUE = "#3B63F0"  # Telureo's blue, the shade made for dark backgrounds, as most terminals are


def print_wordmark(console: Console) -> None:
    """The big letters, or the name on one line where they would break: a window narrower than the letters, or a
    terminal whose encoding has no box-drawing characters. Colour only where the terminal shows it (rich decides)."""
    try:
        "".join(WORDMARK).encode(console.encoding)
        drawable = console.width > max(map(len, WORDMARK))  # one more for the indent that lines up with "Usage"
    except (UnicodeEncodeError, LookupError):
        drawable = False
    console.print()
    for line in WORDMARK if drawable else (NAME,):
        console.print(f" {line}", style=f"bold {BLUE}", markup=False, highlight=False, soft_wrap=True)
    # Whole, and wrapped by the terminal itself where the window is narrow, as the letters above are.
    console.print(f" {TAGLINE}", markup=False, highlight=False, soft_wrap=True)


class MainHelp(TyperGroup):
    """`ttedu` and `ttedu --help` open with the wordmark. The groups under it (miner, validator) keep their plain help."""

    def format_help(self, ctx, formatter):
        print_wordmark(Console())
        super().format_help(ctx, formatter)


app = typer.Typer(cls=MainHelp, help="TTedu: commands for agencies (miners) and validators.",
                  no_args_is_help=True, add_completion=False,
                  # Help text is read as Markdown: lines wrapped in the code join up, `edu ...` shows as a command.
                  rich_markup_mode="markdown",
                  # A crash shows where it happened, never the values it held: those can be keys.
                  pretty_exceptions_show_locals=False)
miner = typer.Typer(help="Agency commands. New here? Start with: `ttedu miner setup`", no_args_is_help=True,
                    rich_markup_mode="markdown")
validator = typer.Typer(help="Validator commands: score and set weights, check the platform.",
                        no_args_is_help=True, rich_markup_mode="markdown")
app.add_typer(miner, name="miner")
app.add_typer(validator, name="validator")


def _version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("edu-subnet")
    except PackageNotFoundError:
        return "unknown"


def _show_version(value: bool) -> None:
    if value:
        typer.echo(f"ttedu {_version()}")
        raise typer.Exit()


@app.callback()
def main(version: Annotated[bool, typer.Option("--version", callback=_show_version, is_eager=True,
                                               help="Show the version and exit.")] = False) -> None:
    """TTedu: commands for agencies (miners) and validators."""

DEFAULT_API = "https://telureo.com"
WALLETS = "~/.bittensor/wallets"
NETUID = 35  # TTedu, Bittensor subnet 35
BURN_RATE = float(scoring.BURN_RATE)  # the subnet's burn rate, a validator's default
Api = Annotated[str, typer.Option("--api", envvar="EDU_API_URL", help="The platform's address.")]
# Like btcli: a wallet or hotkey left out is asked for, with btcli's saved choice (btcli config set) as the answer to
# accept with Enter. Bittensor's own variables work too.
WalletName = Annotated[str | None, typer.Option("--wallet.name", envvar="BT_WALLET_NAME", show_default=False,
                                                 help="Wallet (coldkey) name. Asked for when left out.")]
WalletHotkey = Annotated[str | None, typer.Option("--wallet.hotkey", envvar="BT_WALLET_HOTKEY", show_default=False,
                                                   help="Hotkey name. Asked for when left out.")]
WalletPath = Annotated[str | None, typer.Option("--wallet.path", envvar="BT_WALLET_PATH", show_default=False,
                                                 help=f"Folder that holds your wallets, {WALLETS} by default.")]
Yes = Annotated[bool, typer.Option("--yes", help="Skip the confirmation question.")]
Network = Annotated[str, typer.Option("--network", envvar="EDU_NETWORK", help="Bittensor network.")]
Netuid = Annotated[int, typer.Option("--netuid", envvar="EDU_NETUID", help="The subnet's netuid.")]


def _fail(message: str) -> NoReturn:
    typer.secho(message, fg="red", err=True)
    raise typer.Exit(1)


def _interactive() -> bool:
    """A person at a terminal, who can be asked (not a script or a service)."""
    return sys.stdin.isatty()


def _host(api: str) -> str:
    return urlsplit(api).netloc or api


def _btcli_saved() -> dict[str, str]:
    """What `btcli config set` saved (wallet_name, wallet_hotkey, wallet_path), so both tools start from the same
    choices. A plain read of btcli's flat YAML file: nothing else in it is used."""
    path = pathlib.Path(os.environ.get("BTCLI_CONFIG_PATH") or "~/.bittensor/config.yml").expanduser()
    try:
        lines = path.read_text().splitlines()
    except (OSError, UnicodeDecodeError):
        return {}
    saved = {}
    for line in lines:
        key, colon, value = line.partition(":")
        value = value.split(" #")[0].strip().strip("'\"")
        if colon and key.strip() in ("wallet_name", "wallet_hotkey", "wallet_path") and value not in ("", "~", "null"):
            saved[key.strip()] = value
    return saved


def _found(folder: pathlib.Path, keep) -> list[str]:
    try:
        return sorted(entry.name for entry in folder.iterdir() if keep(entry))
    except OSError:
        return []


def _choose(what: str, flag: str, given: str | None, saved: str | None, found: list[str], where: str) -> str:
    """The wallet or hotkey to use. Given: that one. Otherwise a person is asked, with btcli's saved choice, or the
    only one there, as the answer to accept with Enter. A script without a terminal gets that same answer when there
    is one, and is told the flag when there isn't."""
    if given:
        return given.strip()
    suggestion = (saved if saved in found else found[0] if len(found) == 1
                  else "default" if "default" in found else None)
    if _interactive():
        if found:
            typer.echo(f"{what.capitalize()}s in {where}: {', '.join(found)}")
        return typer.prompt(f"Which {what}", default=suggestion).strip()
    if suggestion:
        return suggestion
    listed = f" There: {', '.join(found)}." if found else ""
    _fail(f"Say which {what} to use with {flag}.{listed}")


def _wallet(name: str | None, hotkey: str | None, path: str | None):
    """The wallet and hotkey to sign with: from the flags, else asked for, and checked before anything is signed."""
    from bittensor_wallet import Wallet

    saved = _btcli_saved()
    folder = pathlib.Path(path or saved.get("wallet_path") or WALLETS).expanduser()
    wallets = _found(folder, lambda e: e.is_dir() and ((e / "coldkeypub.txt").is_file() or (e / "hotkeys").is_dir()))
    if not wallets and not name:
        _fail(f"No wallet found in {folder}. Create one with btcli (btcli wallet create), or give --wallet.path.")
    name = _choose("wallet", "--wallet.name", name, saved.get("wallet_name"), wallets, str(folder))
    if name not in wallets:
        listed = f" Wallets there: {', '.join(wallets)}." if wallets else ""
        _fail(f"There is no wallet named {name} in {folder}.{listed}")
    hotkeys = _found(folder / name / "hotkeys", lambda e: e.is_file() and not e.name.endswith("pub.txt"))
    if not hotkeys and not hotkey:
        _fail(f"Wallet {name} has no hotkey yet. Create one with btcli (btcli wallet new-hotkey), then register it.")
    hotkey = _choose("hotkey", "--wallet.hotkey", hotkey, saved.get("wallet_hotkey"), hotkeys, f"wallet {name}")
    if hotkey not in hotkeys:
        listed = f" Its hotkeys: {', '.join(hotkeys)}." if hotkeys else ""
        _fail(f"Wallet {name} has no hotkey named {hotkey}.{listed}")
    return Wallet(name=name, hotkey=hotkey, path=str(folder))


def _hotkey(wallet):
    from bittensor_wallet.errors import KeyFileError, PasswordError, WalletError

    try:
        return wallet.hotkey
    except (KeyFileError, PasswordError, WalletError) as err:
        _fail(f"Could not open hotkey {wallet.hotkey_str} of wallet {wallet.name}: {err}")


def _coldkey(wallet):
    """The coldkey, which asks for its password. A wrong password is said plainly, and nothing is signed."""
    from bittensor_wallet.errors import KeyFileError, PasswordError, WalletError

    if not (pathlib.Path(wallet.path).expanduser() / wallet.name / "coldkey").is_file():
        _fail(f"Wallet {wallet.name} has only its public coldkey here. Run this on the computer that holds the "
              "coldkey.")
    try:
        return wallet.coldkey
    except (KeyFileError, PasswordError, WalletError) as err:
        if "password" in str(err).lower():
            _fail(f"That password doesn't open the coldkey of wallet {wallet.name}. Nothing was signed.")
        _fail(f"Could not open the coldkey of wallet {wallet.name}: {err}")


def _subnet_of(platform) -> tuple[int | None, str | None]:
    """The subnet and network the platform reads agencies from, from its public settings. Nothing when it can't say."""
    try:
        config = platform.config()
    except (PlatformError, httpx.HTTPError):
        return None, None
    return config.get("netuid"), config.get("network")


def _where(api: str, netuid: int | None, network: str | None) -> str:
    """The platform, and the subnet it reads agencies from. Subnet 0 is no subnet: the platform's stand-in."""
    if netuid is None:
        return _host(api)
    if netuid == 0:
        return f"{_host(api)}, with stand-in agencies until it moves to subnet {NETUID}"
    return f"{_host(api)}, subnet {netuid} on {network}"


def _register_hint(api: str, netuid: int | None, network: str | None) -> str:
    if netuid == 0:
        return (f"{_host(api)} takes only its stand-in agencies until it moves to subnet {NETUID}. For a hotkey "
                f"registered on subnet {NETUID}, use a platform on subnet {NETUID}, with --api.")
    on = f" --network {network}" if network and network != "finney" else ""
    return f"Register it first with btcli: btcli subnets register --netuid {netuid if netuid is not None else NETUID}{on}"


def _who(wallet, hotkey, where: str) -> None:
    typer.echo(f"Agency hotkey:  {hotkey.ss58_address} (wallet {wallet.name}, hotkey {wallet.hotkey_str})\n"
               f"Platform:       {where}")


def _pick(items: list[dict], describe, question: str) -> dict:
    """One of the listed items, chosen by its number."""
    for number, item in enumerate(items, 1):
        typer.echo(f"  {number}. {describe(item)}")
    while True:
        answer = typer.prompt(question, default="1" if len(items) == 1 else None).strip()
        if answer.isdigit() and 1 <= int(answer) <= len(items):
            return items[int(answer) - 1]
        typer.echo(f"Type a number from 1 to {len(items)}.")


def _utc(iso: str) -> str:
    """'2026-10-15T03:40:59.027+00:00' -> '2026-10-15 03:40 UTC'."""
    from datetime import datetime, timezone

    return datetime.fromisoformat(iso).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _call(function, *args):
    try:
        return function(*args)
    except PlatformError as err:
        typer.secho(f"The platform refused: {err.detail}", fg="red", err=True)
    except httpx.HTTPError as err:
        typer.secho(f"Could not reach the platform: {err}", fg="red", err=True)
    raise typer.Exit(1)


def _signup_link(platform, hotkey, coldkey, api: str, netuid: int | None, network: str | None) -> dict:
    """The one-time link to the agency's account, signed with both keys. A hotkey the platform's subnet doesn't know
    gets the way to fix it."""
    try:
        return platform.signup_link(hotkey, coldkey)
    except PlatformError as err:
        if "not registered" in err.detail:
            _fail(f"{err.detail} {_register_hint(api, netuid, network)}")
        _fail(f"The platform refused: {err.detail}")
    except httpx.HTTPError as err:
        _fail(f"Could not reach the platform: {err}")


def _print_signup(result: dict) -> None:
    name = result["agency"]["name"] or "your agency"
    if result.get("linked_to"):
        typer.echo(f"{name} already has an account ({result['linked_to']}). This link moves it to the account that "
                   "opens it.")
    typer.echo(f"Open this link within 30 minutes. It creates the account for {name}, or adds the agency to the "
               f"account you're signed in to.\n{result['url']}")
    if not result.get("linked_to"):
        typer.echo("On that page, enter an email address, the 6-digit code it sends you, and a password.")


# ----------------------------------------------------------------------------- miners

@miner.command("setup")
def miner_setup(api: Api = DEFAULT_API, wallet_name: WalletName = None, wallet_hotkey: WalletHotkey = None,
                wallet_path: WalletPath = None):
    """Set up your agency step by step: your keys, its public name, and its account on the website."""
    platform = Platform(api)
    netuid, network = _subnet_of(platform)
    typer.secho(f"Setting up your agency on {_where(api, netuid, network)}.", bold=True)
    if netuid == 0:
        typer.secho(_register_hint(api, netuid, network), fg="yellow")
    typer.echo("\nStep 1 of 3. Your keys")
    wallet = _wallet(wallet_name, wallet_hotkey, wallet_path)
    hotkey = _hotkey(wallet)
    _who(wallet, hotkey, _where(api, netuid, network))

    typer.echo("\nStep 2 of 3. Your agency's public name")
    profile = _call(platform.profile, hotkey)
    if profile["name"]:
        typer.echo(f"Name: {profile['name']}. You can change it any time with: ttedu miner profile --name")
    elif not _interactive():
        _fail('Your agency has no name yet. Set it with: ttedu miner profile --name "Your agency"')
    else:
        typer.echo("Tutors choose an agency by its name: up to 40 characters, and unique.")
        while True:
            changes = {"name": typer.prompt("Agency name").strip()}
            about = typer.prompt("A short description, up to 200 characters (Enter to skip)", default="",
                                 show_default=False).strip()
            if about:
                changes["description"] = about
            try:
                profile = platform.set_profile(hotkey, changes)
                break
            except PlatformError as err:
                if err.status in (409, 422) and "name" in err.detail.lower():
                    typer.secho(err.detail, fg="red", err=True)
                    continue
                if "not registered" in err.detail:
                    _fail(f"{err.detail} {_register_hint(api, netuid, network)}")
                _fail(f"The platform refused: {err.detail}")
            except httpx.HTTPError as err:
                _fail(f"Could not reach the platform: {err}")
        typer.secho(f"Saved: {profile['name']}", fg="green")

    typer.echo("\nStep 3 of 3. Your agency's account on the website")
    typer.echo("It's where you approve tutors, add credit, and follow your scores. Creating it needs your coldkey's "
               "password, which proves the agency is yours. It is not a transaction and moves no funds.")
    if _interactive() and not typer.confirm("Create the link now?", default=True):
        typer.echo("You can do it later with: ttedu miner signup")
        return
    _print_signup(_signup_link(platform, hotkey, _coldkey(wallet), api, netuid, network))
    typer.echo("\nNext:\n"
               "  1. Tutors ask to join your agency by its name, on the website.\n"
               "  2. Approve them in your agency's dashboard, or here with: ttedu miner requests\n"
               "  3. Follow your scores with: ttedu miner report")


@miner.command("authorize")
def miner_authorize(code: Annotated[str | None, typer.Option("--code", show_default=False,
                                                             help="The tutor's code. Asked for when left out.")] = None,
                    yes: Yes = False, api: Api = DEFAULT_API, wallet_name: WalletName = None,
                    wallet_hotkey: WalletHotkey = None, wallet_path: WalletPath = None):
    """Add a tutor to your agency by signing their code with your coldkey and hotkey."""
    wallet = _wallet(wallet_name, wallet_hotkey, wallet_path)
    hotkey = _hotkey(wallet)
    platform = Platform(api)
    if not code:
        waiting = _call(platform.requests, hotkey)["requests"]
        if not waiting:
            typer.echo("No tutor is asking to join right now.")
            return
        if not _interactive():
            _fail("Say which request to approve with --code. See them with: ttedu miner requests")
        code = _pick(waiting, lambda r: f"{r['code']}  {r['tutor_name']}", "Which tutor (number)")["code"]
    request = _call(platform.affiliation_request, code)
    if request["miner_hotkey"] != hotkey.ss58_address:
        _fail(f"This code is for hotkey {request['miner_hotkey']}, not your hotkey {hotkey.ss58_address}.")
    typer.echo(f"Tutor:          {request['tutor_name']} (account {request['tutor_account_id']})\n"
               f"Agency hotkey:  {hotkey.ss58_address}\n"
               f"Coldkey:        {wallet.coldkeypub.ss58_address}\n"
               f"Subnet:         {request['netuid']} on {request['network']}\n"
               f"Platform:       {request['platform_domain']}\n"
               f"Code expires:   {_utc(request['expires_at'])}\n"
               + (f"Switching from: {request['switching_from']}\n"
                  "                The tutor's booked lectures that have not started will move to your agency.\n"
                  if request.get("switching_from") else "")
               + "\n"
               "You will sign a plain-text message with your coldkey and hotkey.\n"
               "It is not a transaction and cannot move funds.")
    if not yes:
        typer.confirm("Authorize this tutor?", abort=True)
    result = _call(platform.authorize, request, _coldkey(wallet), hotkey)  # asks for the coldkey password
    typer.secho(f"Done. {request['tutor_name']} is now in your agency "
                f"({result['tutors_in_agency']} of 5 tutors).", fg="green")


@miner.command("tutors")
def miner_tutors(api: Api = DEFAULT_API, wallet_name: WalletName = None, wallet_hotkey: WalletHotkey = None,
                 wallet_path: WalletPath = None):
    """List the tutors in your agency."""
    tutors = _call(Platform(api).tutors, _hotkey(_wallet(wallet_name, wallet_hotkey, wallet_path)))["tutors"]
    typer.echo(f"{len(tutors)} of 5 tutors")
    for tutor in tutors:
        typer.echo(f"  {tutor['name']:<30} {tutor['tutor_account_id']}  since {tutor['since'][:10]}")


@miner.command("signup")
def miner_signup(api: Api = DEFAULT_API, wallet_name: WalletName = None, wallet_hotkey: WalletHotkey = None,
                 wallet_path: WalletPath = None):
    """A one-time link to your agency's account on the website.

    The account is where you approve tutors and add credit. The link needs your coldkey, which proves the agency is
    yours, so the website never asks you for a wallet."""
    platform = Platform(api)
    netuid, network = _subnet_of(platform)
    wallet = _wallet(wallet_name, wallet_hotkey, wallet_path)
    hotkey = _hotkey(wallet)
    _who(wallet, hotkey, _where(api, netuid, network))
    _print_signup(_signup_link(platform, hotkey, _coldkey(wallet), api, netuid, network))


@miner.command("requests")
def miner_requests(api: Api = DEFAULT_API, wallet_name: WalletName = None, wallet_hotkey: WalletHotkey = None,
                   wallet_path: WalletPath = None):
    """Tutors asking to join your agency. Approve one with `ttedu miner authorize`, or in your dashboard."""
    waiting = _call(Platform(api).requests, _hotkey(_wallet(wallet_name, wallet_hotkey, wallet_path)))["requests"]
    if not waiting:
        typer.echo("No tutor is asking to join right now.")
        return
    for request in waiting:
        switch = ", switching from another agency" if request["switch"] else ""
        typer.echo(f"  {request['code']}  {request['tutor_name']}{switch}, asked {request['asked_at'][:10]}")
    typer.echo("Approve one with: ttedu miner authorize --code <code>, or just: ttedu miner authorize")


@miner.command("remove")
def miner_remove(tutor: Annotated[str | None, typer.Option("--tutor", show_default=False,
                                                           help="The tutor's account id. Asked for when left out.")] = None,
                 yes: Yes = False, api: Api = DEFAULT_API, wallet_name: WalletName = None,
                 wallet_hotkey: WalletHotkey = None, wallet_path: WalletPath = None):
    """Remove a tutor from your agency (needs your coldkey)."""
    wallet = _wallet(wallet_name, wallet_hotkey, wallet_path)
    hotkey = _hotkey(wallet)
    platform = Platform(api)
    if not tutor:
        tutors = _call(platform.tutors, hotkey)["tutors"]
        if not tutors:
            typer.echo("Your agency has no tutors.")
            return
        if not _interactive():
            _fail("Say which tutor to remove with --tutor. See them with: ttedu miner tutors")
        tutor = _pick(tutors, lambda t: f"{t['name']} ({t['tutor_account_id']})",
                      "Which tutor to remove (number)")["tutor_account_id"]
    if not yes:
        typer.confirm(f"Remove tutor {tutor} from your agency?", abort=True)
    _call(platform.remove_tutor, tutor, hotkey, _coldkey(wallet))
    typer.secho("Removed.", fg="green")


@miner.command("profile")
def miner_profile(name: Annotated[str | None, typer.Option(help="Agency name, up to 40 characters.")] = None,
                  description: Annotated[str | None, typer.Option(
                      help="Short description, up to 200 characters.")] = None,
                  logo_url: Annotated[str | None, typer.Option(
                      "--logo-url", help="An https:// link to your logo image.")] = None,
                  api: Api = DEFAULT_API, wallet_name: WalletName = None, wallet_hotkey: WalletHotkey = None,
                  wallet_path: WalletPath = None):
    """Show or change your agency's public name, description, and logo. Use "" to clear a field."""
    hotkey = _hotkey(_wallet(wallet_name, wallet_hotkey, wallet_path))
    changes = {field: value for field, value in (("name", name), ("description", description),
                                                 ("logo_url", logo_url)) if value is not None}
    platform = Platform(api)
    if changes:
        profile = _call(platform.set_profile, hotkey, changes)
        typer.secho("Saved.", fg="green")
    else:
        profile = _call(platform.profile, hotkey)
    typer.echo(f"Name:         {profile['name'] or '(not set)'}\n"
               f"Description:  {profile['description'] or '(not set)'}\n"
               f"Logo:         {profile['logo_url'] or '(not set)'}")
    if not profile["name"]:
        typer.echo('Tutors find your agency by its name. Set it with: ttedu miner profile --name "Your agency"')


def _credits(count: float) -> str:
    """A number of agency credits: "1 credit", "12 credits", "1.5 credits"."""
    shown = f"{int(count):,}" if count == int(count) else f"{count:,.9f}".rstrip("0")
    return f"{shown} credit{'' if abs(count) == 1 else 's'}"


TOP_UP = {"pending": "the platform checks it on the chain, usually within a minute",
          "credited": "added to your credit", "rejected": "turned down"}


@miner.command("credit")
def miner_credit(as_json: Annotated[bool, typer.Option("--json", help="Print everything as JSON.")] = False,
                 api: Api = DEFAULT_API, wallet_name: WalletName = None,
                 wallet_hotkey: WalletHotkey = None, wallet_path: WalletPath = None):
    """Your agency's credit for booking fees: the balance, and how many bookings it pays for.

    Credits are bought from your agency's dashboard on the website, once buying is open there."""
    info = _call(Platform(api).credit, _hotkey(_wallet(wallet_name, wallet_hotkey, wallet_path)))
    if as_json:
        typer.echo(json.dumps(info, indent=2))
        return
    if not info["on"]:
        typer.echo("Agency credit isn't open yet. Booking costs nothing until it is.")
        return
    typer.echo(f"Credit:    {_credits(info['credits'])}, enough for {info['bookings_left']} bookings "
               f"at {_credits(info['booking_credits'])} each")
    for top_up in info["top_ups"][:5]:
        amount = f"  {_credits(top_up['credits'])}" if top_up["credits"] else ""
        reason = f": {top_up['reason']}" if top_up["status"] == "rejected" and top_up["reason"] else ""
        typer.echo(f"  {top_up['extrinsic'] or 'on its way':<16} {TOP_UP[top_up['status']]}{reason}{amount}")
    if info.get("buying", True):
        typer.echo("Add credit from your agency's dashboard. No account yet? Run ttedu miner signup.")
    else:  # credits aren't sold in the dashboard yet: what one will cost, in the subnet's alpha
        typer.echo(f"Buying credits opens soon in your agency's dashboard, at {info['alpha_per_credit']} alpha a credit.")


@miner.command("report")
def miner_report(as_json: Annotated[bool, typer.Option("--json", help="Print the full report as JSON.")] = False,
                 api: Api = DEFAULT_API, wallet_name: WalletName = None,
                 wallet_hotkey: WalletHotkey = None, wallet_path: WalletPath = None):
    """Your agency's current scores, lectures, and daily history."""
    report = _call(Platform(api).report, _hotkey(_wallet(wallet_name, wallet_hotkey, wallet_path)))
    if as_json:
        typer.echo(json.dumps(report, indent=2))
        return
    typer.echo(f"Agency score now: {report['agency_score']} live watch-minutes")
    for tutor in report["tutors"]:
        lectures = tutor["lectures"]
        typer.echo(f"  {tutor['name']:<30} score {tutor['current_score']:>8}  share {tutor['share']:>7}  "
                   f"completed {lectures['completed']}  no-show {lectures['no_show']}  "
                   f"cancelled {lectures['cancelled']}")
    if report["former_tutors_score"]:
        typer.echo(f"  (former tutors' lectures still counting: {report['former_tutors_score']})")


# ----------------------------------------------------------------------------- validators

@validator.command("run")
def validator_run(netuid: Netuid = NETUID, network: Network = "finney", api: Api = DEFAULT_API,
                  interval: Annotated[int, typer.Option(help="Seconds between rounds.")] = 1800,
                  checks: Annotated[int, typer.Option(help="Lectures to spot-check per round.")] = 3,
                  dry_run: Annotated[bool, typer.Option("--dry-run", help="Print the weights without setting them.")] = False,
                  rounds: Annotated[int | None, typer.Option(help="Stop after this many rounds.")] = None,
                  burn_rate: Annotated[float, typer.Option(
                      "--burn-rate", envvar="TTEDU_BURN_RATE", min=0.0, max=1.0,
                      help="The part of the weight that is burned, from 0 to 1: it goes to the subnet owner's UID. "
                           "The default is the subnet's rate. Keep it, so that every validator's weights agree.")] = BURN_RATE,
                  wallet_name: WalletName = None, wallet_hotkey: WalletHotkey = None,
                  wallet_path: WalletPath = None):
    """Download the dataset, score it, set weights, and spot-check, every round."""
    from . import youtube
    from .chain import SubnetChain
    from .validator import SpotChecker, run

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    wallet = _wallet(wallet_name, wallet_hotkey, wallet_path)
    hotkey, platform, chain = _hotkey(wallet), Platform(api), SubnetChain(network, netuid)
    credentials = youtube.load_credentials()
    checker = None
    if credentials and checks > 0:
        checker = SpotChecker(youtube.YouTubeChecker(credentials).live_minutes, sample_size=checks)
    else:
        typer.echo("Spot-checks are off. Run `ttedu validator connect-youtube` to turn them on.")

    def submit(weights: dict[int, float]) -> None:
        if dry_run:
            typer.echo(f"(dry run) weights: {weights}")
        else:
            chain.set_weights(wallet, weights)

    typer.echo(f"Burn rate: {burn_rate:.0%} of the weight is burned, and {1 - burn_rate:.0%} goes to the miners.")
    run(lambda: platform.eligible(hotkey), chain.snapshot, submit, interval_seconds=interval,
        checker=checker, report=typer.echo, rounds=rounds, burn_rate=burn_rate)


@validator.command("fetch")
def validator_fetch(out: Annotated[pathlib.Path | None, typer.Option(help="Write to this file.")] = None,
                    api: Api = DEFAULT_API, wallet_name: WalletName = None,
                    wallet_hotkey: WalletHotkey = None, wallet_path: WalletPath = None):
    """Download the current dataset once."""
    payload = _call(Platform(api).eligible, _hotkey(_wallet(wallet_name, wallet_hotkey, wallet_path)))
    text = json.dumps(payload, indent=2)
    if out:
        out.write_text(text)
        typer.echo(f"Saved {payload['row_count']} lectures to {out}")
    else:
        typer.echo(text)


@validator.command("score")
def validator_score(file: Annotated[pathlib.Path, typer.Option("--file", prompt="The dataset file saved by fetch",
                                                               help="A dataset saved by `fetch`.")],
                    netuid: Annotated[int | None, typer.Option(envvar="EDU_NETUID")] = None,
                    network: Network = "finney",
                    offline: Annotated[bool, typer.Option(help="Treat every miner in the file as registered.")] = False):
    """Score a saved dataset with the public rules and show the resulting weights."""
    from .dataset import parse_dataset

    read_at, records = parse_dataset(json.loads(file.read_text()))
    if offline:
        eligible = {r.miner for r in records}
    else:
        if netuid is None:
            raise typer.BadParameter("give --netuid, or use --offline")
        from .chain import SubnetChain
        from .dataset import miner_ref

        neurons, _ = SubnetChain(network, netuid).snapshot()
        eligible = {miner_ref(n.hotkey, n.registration_block) for n in neurons}
    scores = scoring.score(records, read_at, eligible)
    weights = scoring.target_weights(scores.miners)
    typer.echo(f"Dataset read at {read_at.isoformat()}: {len(records)} lectures")
    if weights.burn:
        typer.echo("Every miner score is zero: everything is burned.")
    else:
        typer.echo(f"Burn rate {float(scoring.BURN_RATE):.0%}: the subnet owner's UID gets {float(scoring.BURN_RATE):.4f}, "
                   f"and the miners share {float(1 - scoring.BURN_RATE):.4f}.")
    for miner_id, score in sorted(scores.miners.items(), key=lambda item: -item[1]):
        weight = weights.shares.get(miner_id, 0) * (1 - scoring.BURN_RATE)
        typer.echo(f"  {miner_id:<60} {score:>10}  {float(weight):.4f}")


@validator.command("check")
def validator_check(lecture: Annotated[str, typer.Option("--lecture", prompt="Lecture id", help="Lecture id to check.")],
                    api: Api = DEFAULT_API, wallet_name: WalletName = None,
                    wallet_hotkey: WalletHotkey = None, wallet_path: WalletPath = None):
    """Compare one lecture's platform number with YouTube, using your own read-only access."""
    from . import youtube

    credentials = youtube.load_credentials()
    if credentials is None:
        typer.secho("Run `ttedu validator connect-youtube` first.", fg="red", err=True)
        raise typer.Exit(1)
    payload = _call(Platform(api).eligible, _hotkey(_wallet(wallet_name, wallet_hotkey, wallet_path)))
    record = next((r for r in payload["lectures"] if r["lecture_id"] == lecture), None)
    if record is None or not record.get("query"):
        typer.secho("That lecture is not in the current dataset, or has no value yet.", fg="red", err=True)
        raise typer.Exit(1)
    found = youtube.YouTubeChecker(credentials).live_minutes(record["query"])
    same = found == record["live_minutes"]
    typer.echo(f"Platform: {record['live_minutes']} (fetched {record['fetched_at']})\nYouTube:  {found}")
    typer.secho("Same." if same else "Different. YouTube may have updated since the platform's fetch. "
                "Check again after the platform's next refresh (30 minutes).", fg="green" if same else "yellow")


@validator.command("connect-youtube")
def validator_connect_youtube(client_file: Annotated[pathlib.Path, typer.Option(
        "--client-file", prompt="The OAuth client file (JSON) from Google Cloud",
        help="OAuth client JSON (type: Desktop app) from Google Cloud.")]):
    """Sign in once with the Google account the subnet owner invited to the channels."""
    from . import youtube

    client = json.loads(client_file.read_text()).get("installed")
    if not client:
        raise typer.BadParameter("this is not a Desktop app OAuth client file")
    url, state, verifier = youtube.start_sign_in(client["client_id"])
    typer.echo(f"1. Open this link and sign in with your validator's Google account:\n\n{url}\n\n"
               "2. Click Allow. The browser then opens a 'localhost' page that may not load. That is expected.\n"
               "3. Copy the full address from the browser's address bar.")
    pasted = typer.prompt("Paste the address")
    try:
        credentials = youtube.finish_sign_in(client, pasted, state, verifier)
    except youtube.YouTubeAccessError as err:
        typer.secho(str(err), fg="red", err=True)
        raise typer.Exit(1) from None
    youtube.save_credentials(credentials)
    typer.secho(f"Connected. Credentials saved to {youtube.DEFAULT_CREDENTIALS}", fg="green")


# ----------------------------------------------------------------------------- everyone

@app.command("status")
def status(api: Api = DEFAULT_API, wallet_name: WalletName = None,
           wallet_hotkey: WalletHotkey = None, wallet_path: WalletPath = None):
    """What the platform knows about your hotkey."""
    info = _call(Platform(api).status, _hotkey(_wallet(wallet_name, wallet_hotkey, wallet_path)))
    typer.echo(f"Hotkey: {info['hotkey']}\nRole:   {info['role']}")
    if info["role"] == "agency":
        typer.echo(f"Name:   {info.get('agency_name') or '(not set: see ttedu miner profile)'}\n"
                   f"Tutors: {info['tutors_in_agency']} of 5")
    elif info["role"] == "none":
        typer.echo("The platform doesn't know this hotkey as an agency or a validator yet. "
                   "An agency starts with: ttedu miner setup")


if __name__ == "__main__":
    app()
