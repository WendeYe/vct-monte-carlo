from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from math import comb, isfinite, log


@dataclass(frozen=True)
class MapResult:
    match_id: str
    map_id: str
    played_at: datetime
    team_a: str
    team_b: str
    winner: str
    map_order: int = 0

    def __post_init__(self):
        if self.team_a == self.team_b or self.winner not in (self.team_a, self.team_b):
            raise ValueError("A map needs distinct teams and a winner among them.")
        if self.played_at.tzinfo is None:
            raise ValueError("Map dates must include a timezone.")


def map_probability(rating_a: float, rating_b: float) -> float:
    if not isfinite(rating_a) or not isfinite(rating_b):
        raise ValueError("Ratings must be finite.")
    difference = max(-40, min(40, (rating_b - rating_a) / 400))
    return 1 / (1 + 10 ** difference)


def series_probability(map_probability: float, best_of: int) -> float:
    """Chance of winning a series, assuming independent, equally likely maps."""
    if not isfinite(map_probability) or not 0 <= map_probability <= 1:
        raise ValueError("Map probability must be between zero and one.")
    if best_of not in (1, 3, 5):
        raise ValueError("Supported series lengths are 1, 3 and 5.")
    return sum(
        comb(best_of, wins) * map_probability ** wins
        * (1 - map_probability) ** (best_of - wins)
        for wins in range(best_of // 2 + 1, best_of + 1)
    )


def fit_ratings(maps: list[MapResult], cutoff: datetime, k: float = 32) -> dict[str, float]:
    if not isfinite(k) or k <= 0:
        raise ValueError("Elo K must be positive and finite.")
    ratings = defaultdict(lambda: 1500.0)
    for result in sorted(maps, key=lambda m: (m.played_at, m.match_id, m.map_order, m.map_id)):
        if result.played_at >= cutoff:
            continue
        expected = map_probability(ratings[result.team_a], ratings[result.team_b])
        change = k * ((result.winner == result.team_a) - expected)
        ratings[result.team_a] += change
        ratings[result.team_b] -= change
    return dict(ratings)


def evaluate_series(maps: list[MapResult], start: datetime, cutoff: datetime, k: float = 32) -> dict:
    """Predict each held-out series before updating ratings with any of its maps."""
    ratings = defaultdict(lambda: 1500.0)
    series = defaultdict(list)
    for result in maps:
        if result.played_at < cutoff:
            series[result.match_id].append(result)
    scores = []
    for match in sorted(series.values(), key=lambda rows: (rows[0].played_at, rows[0].match_id)):
        match.sort(key=lambda row: (row.map_order, row.map_id))
        a, b = match[0].team_a, match[0].team_b
        a_wins = sum(row.winner == a for row in match)
        b_wins = len(match) - a_wins
        best_of = 2 * max(a_wins, b_wins) - 1
        if match[0].played_at >= start and a_wins != b_wins and best_of in (1, 3, 5):
            p = series_probability(map_probability(ratings[a], ratings[b]), best_of)
            actual = float(a_wins > b_wins)
            bounded = min(1 - 1e-12, max(1e-12, p))
            scores.append(((p - actual) ** 2, -(actual * log(bounded) + (1 - actual) * log(1 - bounded))))
        for row in match:
            expected = map_probability(ratings[a], ratings[b])
            change = k * ((row.winner == a) - expected)
            ratings[a] += change
            ratings[b] -= change
    if not scores:
        raise ValueError("No completed series in the evaluation window.")
    return {"series": len(scores), "brier": sum(row[0] for row in scores) / len(scores),
            "log_loss": sum(row[1] for row in scores) / len(scores)}
