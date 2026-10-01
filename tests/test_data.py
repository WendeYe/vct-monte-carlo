import csv
from datetime import datetime, timezone

import pytest

from src.data import load_maps
from src.ratings import MapResult, evaluate_series
from src.tournament import play_bracket


def test_loader_rejects_duplicate_map_ids(tmp_path):
    path = tmp_path / "maps.csv"
    header = ["match_id", "map_id", "played_at", "team_a", "team_b", "winner", "map_order"]
    row = ["1", "1", "2025-01-01T00:00:00+00:00", "a", "b", "a", "1"]
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows([row, row])
    with pytest.raises(ValueError, match="Duplicate"):
        load_maps(path)


def test_held_out_series_is_predicted_before_its_maps_are_used():
    date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    maps = [MapResult("1", str(i), date, "a", "b", "a", i) for i in (1, 2)]
    evaluation = evaluate_series(maps, date, datetime(2025, 1, 2, tzinfo=timezone.utc))
    assert evaluation["series"] == 1
    assert evaluation["brier"] == 0.25
    assert evaluation["log_loss"] == pytest.approx(0.69314718)


def test_actual_paris_results_replay_through_the_bracket():
    opening = [("PRX", "G2"), ("FNC", "DRX"), ("TH", "MIBR"), ("NRG", "GX")]
    results = [("PRX", "G2", 3), ("FNC", "DRX", 3), ("MIBR", "TH", 3), ("NRG", "GX", 3),
               ("DRX", "G2", 3), ("TH", "GX", 3), ("FNC", "PRX", 3), ("NRG", "MIBR", 3),
               ("PRX", "TH", 3), ("DRX", "MIBR", 3), ("NRG", "FNC", 3), ("DRX", "PRX", 3),
               ("FNC", "DRX", 5), ("NRG", "FNC", 5)]
    lookup = {(frozenset((winner, loser)), length): (winner, loser) for winner, loser, length in results}
    calls = []

    def replay(a, b, length):
        key = (frozenset((a, b)), length)
        calls.append(key)
        return lookup[key]

    assert play_bracket(opening, replay) == {
        "NRG": 1, "FNC": 2, "DRX": 3, "PRX": 4, "TH": 5, "MIBR": 5, "G2": 7, "GX": 7
    }
    assert len(calls) == len(set(calls)) == 14


@pytest.mark.parametrize("k", [0, -32, float("nan"), float("inf")])
def test_evaluation_rejects_invalid_update_factor(k):
    date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    maps = [MapResult("1", "1", date, "a", "b", "a")]
    with pytest.raises(ValueError, match="K"):
        evaluate_series(maps, date, datetime(2025, 1, 2, tzinfo=timezone.utc), k)


def test_evaluation_rejects_mixed_opponents_in_one_series():
    date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    maps = [MapResult("1", "1", date, "a", "b", "a", 1),
            MapResult("1", "2", date, "a", "c", "c", 2)]
    with pytest.raises(ValueError, match="teams"):
        evaluate_series(maps, date, datetime(2025, 1, 2, tzinfo=timezone.utc))
