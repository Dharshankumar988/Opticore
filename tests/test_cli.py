"""Tests for OptiCore CLI Command Center command dispatch and handlers."""

import pytest
from opticore_cli.cli import OptiCoreCLI, build_arg_parser
from opticore_cli.config import ConfigManager


@pytest.fixture
def test_cli(tmp_path, mock_server_url):
    cfg_file = tmp_path / "cli_test_config.json"
    mgr = ConfigManager(config_path=cfg_file)
    mgr.config.server_url = mock_server_url
    cli = OptiCoreCLI(config_manager=mgr)
    yield cli
    cli.shutdown()


def test_command_dispatch_exit(test_cli):
    assert test_cli.handle_command("exit") is False
    assert test_cli.handle_command("quit") is False


def test_command_dispatch_help(test_cli):
    assert test_cli.handle_command("help") is True


def test_command_dispatch_connect_disconnect(test_cli, mock_server_url):
    # Connect
    assert test_cli.handle_command(f"connect {mock_server_url}") is True
    assert test_cli.client.base_url == mock_server_url

    # Disconnect
    assert test_cli.handle_command("disconnect") is True
    assert test_cli.client.base_url == ""


def test_command_dispatch_server_queries(test_cli, mock_server_url):
    test_cli.client.set_base_url(mock_server_url)

    assert test_cli.handle_command("health") is True
    assert test_cli.handle_command("status") is True
    assert test_cli.handle_command("metrics") is True
    assert test_cli.handle_command("events 5") is True


def test_command_dispatch_voice(test_cli):
    # Enable voice
    assert test_cli.handle_command("voice on") is True
    assert test_cli.voice.enabled is True

    # Change verbosity
    assert test_cli.handle_command("voice verbosity critical") is True
    assert test_cli.voice.verbosity == "critical"

    # Change rate
    assert test_cli.handle_command("voice rate 195") is True
    assert test_cli.voice.rate == 195

    # Change volume
    assert test_cli.handle_command("voice volume 0.75") is True
    assert test_cli.voice.volume == 0.75

    # Disable voice
    assert test_cli.handle_command("voice off") is True
    assert test_cli.voice.enabled is False


def test_command_dispatch_config(test_cli):
    assert test_cli.handle_command("config show") is True
    assert test_cli.handle_command("config set poll_interval 2.5") is True
    assert test_cli.config.poll_interval == 2.5
    assert test_cli.handle_command("config reset") is True
    assert test_cli.config.poll_interval == 1.0


def test_arg_parser_subcommands():
    parser = build_arg_parser()

    # Default interactive
    args = parser.parse_args([])
    assert args.command is None

    # Connect
    args = parser.parse_args(["connect", "https://opticore.ngrok-free.app"])
    assert args.command == "connect"
    assert args.server_url == "https://opticore.ngrok-free.app"

    # Status
    args = parser.parse_args(["status", "--url", "http://localhost:8000"])
    assert args.command == "status"
    assert args.url == "http://localhost:8000"

    # Events
    args = parser.parse_args(["events", "--limit", "15"])
    assert args.command == "events"
    assert args.limit == 15

    # Monitor
    args = parser.parse_args(["monitor", "--poll", "0.5", "--voice"])
    assert args.command == "monitor"
    assert args.poll == 0.5
    assert args.voice is True
