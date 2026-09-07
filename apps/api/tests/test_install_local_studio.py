import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "install_local_studio", Path(__file__).parents[3] / "tools/install_local_studio.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def binding(address, published=8000, target=8000):
    return {"URL": address, "TargetPort": target, "PublishedPort": published, "Protocol": "tcp"}


def test_network_entry_precedes_server_loopback():
    assert MODULE.studio_urls({"Publishers": [
        binding("127.0.0.1"), binding("::1"), binding("192.168.11.91"),
    ]}) == [
        "http://192.168.11.91:8000/", "http://127.0.0.1:8000/", "http://[::1]:8000/",
    ]


def test_allocated_port_and_ipv6_are_preserved():
    assert MODULE.studio_urls({"Publishers": [binding("::1", 58307)]}) == [
        "http://[::1]:58307/",
    ]


def test_wildcard_addresses_are_usable_locally_and_duplicates_removed():
    assert MODULE.studio_urls({"Publishers": [
        binding("0.0.0.0"), binding("127.0.0.1"), binding("::"), binding("127.0.0.1", target=9000),
    ]}) == ["http://127.0.0.1:8000/", "http://[::1]:8000/"]


def test_missing_binding_is_an_explicit_failure():
    with pytest.raises(RuntimeError, match="no published API port"):
        MODULE.studio_urls({"Publishers": None})
