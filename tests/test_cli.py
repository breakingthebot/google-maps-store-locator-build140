# tests/test_cli.py
# Tests for Click CLI commands: version, search, get, directions, and list.
# Connects to: src/cli/main.py
# Created: 2026-09-06

from click.testing import CliRunner
from src.cli.main import cli


def test_cli_version():
    """CLI --version flag should output program version."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "store-locator, version 1.0.0" in result.output


def test_cli_list():
    """CLI list command should display registered stores."""
    runner = CliRunner()
    result = runner.invoke(cli, ["list", "--limit", "5"])
    assert result.exit_code == 0
    assert "Registered Store Locations" in result.output
    assert "Apex Retail" in result.output


def test_cli_get():
    """CLI get command should display store profile and weekly hours."""
    runner = CliRunner()
    result = runner.invoke(cli, ["get", "1"])
    assert result.exit_code == 0
    assert "Weekly Operating Hours" in result.output
    assert "Store #1" in result.output


def test_cli_search():
    """CLI search command should return tabular nearest store locations."""
    runner = CliRunner()
    result = runner.invoke(cli, ["search", "--address", "San Francisco", "--radius", "25", "--limit", "5"])
    assert result.exit_code == 0
    assert "Store Proximity Search" in result.output
    assert "Distance" in result.output


def test_cli_directions():
    """CLI directions command should calculate route and display step instructions."""
    runner = CliRunner()
    result = runner.invoke(cli, ["directions", "--from-loc", "Market St", "--to-store", "1", "--mode", "driving"])
    assert result.exit_code == 0
    assert "Route Directions (Driving)" in result.output
    assert "Turn-by-Turn Navigation Steps" in result.output
