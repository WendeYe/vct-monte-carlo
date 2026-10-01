from collections import Counter
from math import sqrt
from random import Random

from src.ratings import map_probability, series_probability


def play_bracket(openers: list[tuple[str, str]], play) -> dict[str, int]:
    """Eight-team double elimination; lower final and grand final BO5, no reset.

    Opening pairs must be in bracket order, with pairs 0/1 in the upper half.
    Lower round two crosses halves to avoid an immediate upper-semifinal rematch.
    """
    placements = {}
    quarters = [play(a, b, 3) for a, b in openers]
    semis = [play(quarters[i][0], quarters[i + 1][0], 3) for i in (0, 2)]
    lower_one = [play(quarters[i][1], quarters[i + 1][1], 3) for i in (0, 2)]
    for _, loser in lower_one:
        placements[loser] = 7
    lower_two = [play(lower_one[i][0], semis[1 - i][1], 3) for i in range(2)]
    for _, loser in lower_two:
        placements[loser] = 5
    lower_semi = play(lower_two[0][0], lower_two[1][0], 3)
    placements[lower_semi[1]] = 4
    upper_final = play(semis[0][0], semis[1][0], 3)
    lower_final = play(lower_semi[0], upper_final[1], 5)
    placements[lower_final[1]] = 3
    final = play(upper_final[0], lower_final[0], 5)
    placements[final[1]] = 2
    placements[final[0]] = 1
    return placements


def wilson_interval(wins: int, trials: int) -> tuple[float, float]:
    """95% Wilson interval for a binomial count; covers sampling uncertainty only."""
    if type(wins) is not int or type(trials) is not int or trials <= 0 or not 0 <= wins <= trials:
        raise ValueError("Use integer counts with 0 <= wins <= trials and trials > 0.")
    p = wins / trials
    z = 1.96
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    margin = z * sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return max(0, min(p, center - margin)), min(1, max(p, center + margin))


def simulate(openers: list[tuple[str, str]], ratings: dict[str, float], iterations: int = 100000,
             seed: int = 42) -> list[dict]:
    if type(iterations) is not int or iterations <= 0:
        raise ValueError("Simulation count must be a positive integer.")
    if len(openers) != 4 or any(len(pair) != 2 for pair in openers):
        raise ValueError("Provide four opening pairs in bracket order.")
    teams = [team for pair in openers for team in pair]
    if len(set(teams)) != 8:
        raise ValueError("The bracket must contain eight unique teams.")
    if any(team not in ratings for team in teams):
        raise ValueError("Every team needs a rating.")
    probabilities = {(a, b, best_of): series_probability(map_probability(ratings[a], ratings[b]), best_of)
                     for a in teams for b in teams if a != b for best_of in (3, 5)}
    rng = Random(seed)
    wins, finals, top_four = Counter(), Counter(), Counter()

    def play(a, b, best_of):
        return (a, b) if rng.random() < probabilities[a, b, best_of] else (b, a)

    for _ in range(iterations):
        for team, place in play_bracket(openers, play).items():
            wins[team] += place == 1
            finals[team] += place <= 2
            top_four[team] += place <= 4
    rows = []
    for team in teams:
        low, high = wilson_interval(wins[team], iterations)
        rows.append({
            "team_id": team,
            "rating": ratings[team],
            "win_probability": wins[team] / iterations,
            "final_probability": finals[team] / iterations,
            "top_four_probability": top_four[team] / iterations,
            "mc_lower": low,
            "mc_upper": high,
        })
    return sorted(rows, key=lambda row: row["win_probability"], reverse=True)
