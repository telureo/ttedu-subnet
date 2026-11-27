"""The chain side of a validator: the subnet's metagraph and weight submission."""
from .validator import Neuron


class SubnetChain:
    def __init__(self, network: str, netuid: int):
        import bittensor

        self._bt = bittensor
        self.network = network
        self.netuid = netuid
        self._subtensor = bittensor.Subtensor(network)

    def snapshot(self) -> tuple[list[Neuron], str]:
        """Every registered neuron (uid, hotkey, registration block) and the subnet owner's hotkey."""
        graph = self._subtensor.subnets.metagraph(self.netuid, commitments=False)
        if graph is None:
            raise ValueError(f"There is no subnet {self.netuid} on {self.network}.")
        neurons = [Neuron(n.uid, n.hotkey, int(n.block_at_registration)) for n in graph.neurons]
        return neurons, graph.owner_hotkey

    def set_weights(self, wallet, weights: dict[int, float]) -> None:
        """Normalizes, quantizes, and picks commit-reveal as the subnet requires; raises on failure."""
        self._bt.set_weights(self.netuid, weights, wallet=wallet, network=self.network)
