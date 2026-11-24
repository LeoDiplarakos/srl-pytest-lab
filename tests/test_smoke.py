import pytest

from helpers import get_value


@pytest.mark.smoke
@pytest.mark.parametrize("node", ["srl1", "srl2", "srl3"])
def test_software_version(clients, node):
    version = get_value(clients[node], "/system/information/version")
    assert version.startswith("v26."), (
        f"{node}: unexpected software version {version!r}"
    )
