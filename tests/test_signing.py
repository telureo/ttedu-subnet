from bittensor_wallet import Keypair

from edu_subnet.signing import is_ss58, sign, verify_signature


def test_signature_round_trip():
    key = Keypair.create_from_mnemonic(Keypair.generate_mnemonic())
    signature = sign(key, b"hello")
    assert signature.startswith("0x")
    assert verify_signature(key.ss58_address, b"hello", signature)


def test_wrong_message_key_or_garbage_is_rejected():
    key = Keypair.create_from_mnemonic(Keypair.generate_mnemonic())
    other = Keypair.create_from_mnemonic(Keypair.generate_mnemonic())
    signature = sign(key, b"hello")
    assert not verify_signature(key.ss58_address, b"hello!", signature)
    assert not verify_signature(other.ss58_address, b"hello", signature)
    assert not verify_signature(key.ss58_address, b"hello", "0xnot-hex")
    assert not verify_signature("not-an-address", b"hello", signature)


def test_is_ss58():
    key = Keypair.create_from_mnemonic(Keypair.generate_mnemonic())
    assert is_ss58(key.ss58_address)
    assert not is_ss58("5Fnot-a-real-address")
