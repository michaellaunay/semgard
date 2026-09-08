import pytest

from semgard.engine import Engine
from semgard.inventory import Inventory


@pytest.fixture(scope="session")
def inv() -> Inventory:
    return Inventory.semgard()


@pytest.fixture(scope="session")
def engine() -> Engine:
    return Engine()
