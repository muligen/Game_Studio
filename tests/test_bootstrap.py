from importlib import import_module


def test_cli_module_imports() -> None:
    module = import_module("studio.interfaces.cli")
    assert hasattr(module, "app")
