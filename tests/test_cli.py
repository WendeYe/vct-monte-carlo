import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from src.data import load_maps


ROOT = Path(__file__).resolve().parents[1]


def test_bundled_snapshot_is_strictly_before_playoffs():
    event = json.loads((ROOT / "data/champions-paris-2025.json").read_text())
    rows = load_maps(ROOT / "data/maps.csv")
    assert all(datetime.fromisoformat(event["training_start"]) <= row.played_at
               < datetime.fromisoformat(event["cutoff"]) for row in rows)
    teams = {team for row in rows for team in (row.team_a, row.team_b)}
    assert set(event["teams"]) <= teams


def test_cli_writes_results_and_chart(tmp_path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "--simulations", "100",
         "--output", str(tmp_path)], capture_output=True, text=True, check=True,
    )
    assert "Champions Paris 2025 playoffs" in result.stdout
    with (tmp_path / "results.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 8
    assert sum(float(row["win_probability"]) for row in rows) == pytest.approx(1)
    assert (tmp_path / "chances.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["simulations"] == 100
    assert summary["evaluation"]["series"] == 188


@pytest.mark.parametrize("arguments", [["--simulations", "0"], ["--maps", "/nonexistent/maps.csv"]])
def test_cli_reports_invalid_input_without_traceback(arguments, tmp_path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "--output", str(tmp_path), *arguments],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "Simulation failed:" in result.stderr
    assert "Traceback" not in result.stderr
