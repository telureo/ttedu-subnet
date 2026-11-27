import os
from types import SimpleNamespace

import pytest

from edu_subnet import youtube
from edu_subnet.chain import SubnetChain


def test_a_subnet_that_does_not_exist_says_so():
    chain = SubnetChain("finney", 9999)  # cold: nothing connects until it is used
    chain._subtensor = SimpleNamespace(subnets=SimpleNamespace(metagraph=lambda netuid, commitments: None))
    with pytest.raises(ValueError, match="There is no subnet 9999 on finney"):
        chain.snapshot()


def test_the_metagraph_gives_uids_hotkeys_and_registration_blocks():
    neurons = [SimpleNamespace(uid=0, hotkey="owner", block_at_registration=7),
               SimpleNamespace(uid=1, hotkey="hotA", block_at_registration=100)]
    graph = SimpleNamespace(neurons=neurons, owner_hotkey="owner")
    chain = SubnetChain("finney", 2)
    chain._subtensor = SimpleNamespace(subnets=SimpleNamespace(metagraph=lambda netuid, commitments: graph))
    found, owner = chain.snapshot()
    assert [(n.uid, n.hotkey, n.registration_block) for n in found] == [(0, "owner", 7), (1, "hotA", 100)]
    assert owner == "owner"


def test_saved_credentials_are_readable_by_this_user_only(tmp_path):
    path = tmp_path / ".edu" / "youtube.json"
    youtube.save_credentials({"refresh_token": "secret"}, path)
    assert youtube.load_credentials(path) == {"refresh_token": "secret"}
    assert os.stat(path).st_mode & 0o777 == 0o600
    assert os.stat(path.parent).st_mode & 0o777 == 0o700


def test_an_older_readable_file_is_locked_before_it_is_written(tmp_path):
    path = tmp_path / "youtube.json"
    path.write_text("{}")
    os.chmod(path, 0o644)
    youtube.save_credentials({"refresh_token": "new"}, path)
    assert os.stat(path).st_mode & 0o777 == 0o600
    assert youtube.load_credentials(path) == {"refresh_token": "new"}
