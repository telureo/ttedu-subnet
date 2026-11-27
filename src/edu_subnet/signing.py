"""sr25519 signing and verification with Bittensor coldkeys and hotkeys."""
from bittensor_wallet import Keypair


def sign(keypair: Keypair, message: bytes) -> str:
    """Hex signature of `message`, as sent to the platform."""
    return "0x" + keypair.sign(message).hex()


def verify_signature(ss58_address: str, message: bytes, signature_hex: str) -> bool:
    try:
        signature = bytes.fromhex(signature_hex.removeprefix("0x"))
        return bool(Keypair(ss58_address=ss58_address).verify(message, signature))
    except Exception:
        return False


def is_ss58(address: str) -> bool:
    try:
        Keypair(ss58_address=address)
        return True
    except Exception:
        return False
