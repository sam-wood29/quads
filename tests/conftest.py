import pytest

from quads.engine.run_scripted_harness import run_script
from quads.engine.script_loader import load_script


@pytest.fixture
def run_named_script():
    def _run(name: str):
        return run_script(load_script(f"tests/data/scripts/{name}.json"))
    return _run 