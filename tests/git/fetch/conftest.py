"""
Conftest for git fetch network tests.

Network tests hit external servers (github.com, git.lyoko.io) and are skipped
by default to keep the test suite runnable offline and in restricted networks.
Enable them explicitly with:

    pytest tests/git/fetch --run-network

or select them with ``-m network`` once enabled.
"""
import pytest


def pytest_addoption(parser):
    """Add the --run-network option to pytest."""
    parser.addoption(
        "--run-network",
        action="store_true",
        default=False,
        help="run tests that require external network access",
    )


def pytest_collection_modifyitems(config, items):
    """Skip network-marked tests unless --run-network is given."""
    if config.getoption("--run-network"):
        return
    skip_network = pytest.mark.skip(reason="network test, run with --run-network")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip_network)
