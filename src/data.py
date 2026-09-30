import csv
from datetime import datetime
from pathlib import Path

from src.ratings import MapResult


def load_maps(path: Path) -> list[MapResult]:
    rows = []
    seen = set()
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            result = MapResult(
                row["match_id"], row["map_id"], datetime.fromisoformat(row["played_at"]),
                row["team_a"], row["team_b"], row["winner"], int(row["map_order"])
            )
            key = (result.match_id, result.map_id)
            if key in seen:
                raise ValueError(f"Duplicate map: {key}")
            seen.add(key)
            rows.append(result)
    if not rows:
        raise ValueError("No historical maps found.")
    return rows
