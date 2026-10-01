from datetime import datetime, timezone

import pytest

from src.ratings import MapResult, fit_ratings, map_probability, series_probability
from src.tournament import play_bracket, simulate, wilson_interval


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


@pytest.mark.parametrize("iterations", [0, -1, 1.5, True])
def test_invalid_simulation_counts_are_rejected(iterations):
    ratings = {team: 1500 for pair in openers() for team in pair}
    with pytest.raises(ValueError, match="count"):
        simulate(openers(), ratings, iterations=iterations)


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


@pytest.mark.parametrize("wins,trials", [(-1, 10), (11, 10), (0, 0), (1.5, 10), (1, True)])
def test_wilson_interval_rejects_invalid_counts(wins, trials):
    with pytest.raises(ValueError):
        wilson_interval(wins, trials)


def test_wilson_interval_at_boundaries():
    assert wilson_interval(0, 100)[0] == 0
    assert wilson_interval(100, 100)[1] == 1
    low, high = wilson_interval(50, 100)
    assert low == pytest.approx(0.40383, abs=0.00001)
    assert high == pytest.approx(0.59617, abs=0.00001)


def test_sampling_agrees_with_exact_bracket_probabilities():
    # Fourteen binary series outcomes give 16,384 paths, small enough to enumerate.
    teams = openers()
    ratings = {f"team{i}": 1400 + i * 35 for i in range(8)}
    exact = {team: 0.0 for team in ratings}
    probabilities = {(a, b, length): series_probability(map_probability(ratings[a], ratings[b]), length)
                     for a in ratings for b in ratings if a != b for length in (3, 5)}
    for path in range(1 << 14):
        weight = 1.0
        series_index = 0

        def play(a, b, length):
            nonlocal weight, series_index
            a_wins = bool(path & (1 << series_index))
            p = probabilities[a, b, length]
            weight *= p if a_wins else 1 - p
            series_index += 1
            return (a, b) if a_wins else (b, a)

        placements = play_bracket(teams, play)
        champion = next(team for team, place in placements.items() if place == 1)
        exact[champion] += weight
    assert sum(exact.values()) == pytest.approx(1)
    trials = 30000
    for row in simulate(teams, ratings, trials, seed=19):
        p = exact[row["team_id"]]
        standard_error = (p * (1 - p) / trials) ** 0.5
        assert abs(row["win_probability"] - p) < 5 * standard_error
