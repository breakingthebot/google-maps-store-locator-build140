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


def test_cli_trip():
    """CLI trip command should calculate multi-stop route with sequential itinerary table."""
    runner = CliRunner()
    result = runner.invoke(cli, ["trip", "--origin", "Market St", "-s", "1", "-s", "2", "-s", "3", "--round-trip"])
    assert result.exit_code == 0
    assert "Optimized Trip Overview" in result.output
    assert "Sequential Stop Schedule" in result.output
    assert "Leg-by-Leg Route Segments" in result.output
    assert "Universal Google Maps Mobile Navigation URL" in result.output


def test_cli_trip_export():
    """CLI trip command with export flags should write GPX and CSV files to disk."""
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        gpx_file = os.path.join(tmpdir, "test_route.gpx")
        csv_file = os.path.join(tmpdir, "test_manifest.csv")

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "trip",
                "--origin", "Market St",
                "-s", "1",
                "-s", "3",
                "--export-gpx", gpx_file,
                "--export-csv", csv_file,
            ],
        )
        assert result.exit_code == 0
        assert "Exported GPX 1.1 route file" in result.output
        assert "Exported Driver CSV manifest" in result.output

        with open(gpx_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert "<gpx version=\"1.1\"" in content

        with open(csv_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert "Stop #" in content


def test_cli_directions_traffic():
    """CLI directions with departure time and traffic model."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "directions",
            "--from-loc", "Market St",
            "--to-store", "1",
            "--mode", "driving",
            "-d", "evening_rush",
            "--traffic-model", "pessimistic",
        ],
    )
    assert result.exit_code == 0
    assert "Route Directions (Driving)" in result.output
    assert "Traffic Condition" in result.output
    assert "In Traffic" in result.output


def test_cli_trip_traffic():
    """CLI trip with rush hour departure time."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "trip",
            "--origin", "Market St",
            "-s", "1",
            "-s", "2",
            "-s", "3",
            "-d", "morning_rush",
            "--traffic-model", "best_guess",
        ],
    )
    assert result.exit_code == 0
    assert "Traffic Condition" in result.output
    assert "Congestion Delay" in result.output


def test_cli_traffic_advisor_single():
    """CLI traffic predictive departure advisor for single store destination."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "traffic",
            "--from-loc", "Market St",
            "--to-store", "1",
        ],
    )
    assert result.exit_code == 0
    assert "Predictive Departure Time Advisor" in result.output
    assert "Best Departure Window" in result.output
    assert "Worst Departure Window" in result.output
    assert "Potential Time Saved" in result.output


def test_cli_traffic_advisor_trip():
    """CLI traffic predictive departure advisor for multi-stop itinerary."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "traffic",
            "--from-loc", "Market St",
            "-s", "1",
            "-s", "2",
            "-s", "3",
        ],
    )
    assert result.exit_code == 0
    assert "Predictive Departure Time Advisor" in result.output
    assert "Early Morning" in result.output
