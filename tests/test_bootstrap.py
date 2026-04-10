from importlib import import_module


def test_cli_module_imports() -> None:
    module = import_module("studio.interfaces.cli")
    assert hasattr(module, "app")


def test_cli_app_is_typer_instance() -> None:
    from typer import Typer

    module = import_module("studio.interfaces.cli")
    assert isinstance(module.app, Typer)
