from datetime import datetime, timezone

import pytest

from src.ratings import MapResult, fit_ratings, map_probability, series_probability
from src.tournament import play_bracket, simulate


def test_series_probability_matches_binomial_result():
    assert series_probability(0.6, 3) == pytest.approx(0.648)
    assert series_probability(0.6, 5) == pytest.approx(0.68256)
    assert series_probability(0.5, 5) == pytest.approx(0.5)
    assert series_probability(1, 3) == 1
    assert series_probability(0, 3) == 0


@pytest.mark.parametrize("p,best_of", [(-0.1, 3), (1.1, 3), (0.5, 2), (float("nan"), 3)])
def test_invalid_series_inputs_are_rejected(p, best_of):
    with pytest.raises(ValueError):
        series_probability(p, best_of)


def test_elo_probability_is_symmetric_and_bounded():
    assert map_probability(1500, 1500) == 0.5
    assert map_probability(1700, 1500) > 0.5
    assert map_probability(1700, 1500) + map_probability(1500, 1700) == pytest.approx(1)
    assert 0 <= map_probability(-1e6, 1e6) <= 1


def test_ratings_exclude_matches_on_or_after_cutoff():
    cutoff = datetime(2025, 9, 12, tzinfo=timezone.utc)
    prior = MapResult("m1", "g1", datetime(2025, 9, 1, tzinfo=timezone.utc), "a", "b", "a")
    future = MapResult("m2", "g2", cutoff, "a", "b", "b")
    ratings = fit_ratings([future, prior], cutoff)
    assert ratings == fit_ratings([prior], cutoff)
    assert ratings["a"] == 1516
    assert ratings["b"] == 1484


def openers():
    return [(f"team{i}", f"team{i + 1}") for i in range(0, 8, 2)]


def test_simulation_conserves_probabilities_and_is_reproducible():
    teams = openers()
    ratings = {team: 1500 for pair in teams for team in pair}
    first = simulate(teams, ratings, iterations=4000, seed=7)
    assert first == simulate(teams, ratings, iterations=4000, seed=7)
    assert sum(row["win_probability"] for row in first) == pytest.approx(1)
    assert sum(row["top_four_probability"] for row in first) == pytest.approx(4)
    assert sum(row["final_probability"] for row in first) == pytest.approx(2)
    assert all(abs(row["win_probability"] - 1 / 8) < 0.025 for row in first)
    for row in first:
        assert row["win_probability"] <= row["final_probability"] <= row["top_four_probability"]
        assert row["mc_lower"] <= row["win_probability"] <= row["mc_upper"]


def test_overwhelming_favourite_wins_every_run():
    teams = openers()
    ratings = {team: 0 for pair in teams for team in pair}
    ratings["team0"] = 100000
    results = simulate(teams, ratings, iterations=100, seed=1)
    assert next(row for row in results if row["team_id"] == "team0")["win_probability"] == 1


@pytest.mark.parametrize("iterations", [0, -1, 1.5])
def test_invalid_simulation_counts_are_rejected(iterations):
    with pytest.raises(ValueError):
        simulate(openers(), {}, iterations=iterations)


def test_duplicate_teams_and_missing_ratings_are_rejected():
    teams = openers()
    with pytest.raises(ValueError, match="rating"):
        simulate(teams, {}, iterations=1)
    teams[1] = ("team0", "team3")
    with pytest.raises(ValueError, match="unique"):
        simulate(teams, {}, iterations=1)


def test_bracket_allows_a_first_round_loser_to_win_without_a_reset():
    played = []

    def choose(a, b, best_of):
        if not played or "team0" not in (a, b):
            winner, loser = b, a
        else:
            winner, loser = (a, b) if a == "team0" else (b, a)
        played.append((winner, loser, best_of))
        return winner, loser

    placements = play_bracket(openers(), choose)
    assert placements["team0"] == 1
    assert len(played) == 14
    assert [match[2] for match in played].count(5) == 2
    assert sum(loser == "team0" for _, loser, _ in played) == 1
    assert sorted(placements.values()) == [1, 2, 3, 4, 5, 5, 7, 7]
