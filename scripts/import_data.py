"""Create a small, dated CSV from VCT Reference's downloadable database."""

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

import duckdb


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://vct-reference.com/dataset/vct.duckdb"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "data/raw/vct.duckdb")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    args.database.parent.mkdir(parents=True, exist_ok=True)
    if args.refresh or not args.database.exists():
        with urlopen(SOURCE, timeout=60) as response:
            payload = response.read()
        args.database.write_bytes(payload)
    event = json.loads((ROOT / "data/champions-paris-2025.json").read_text())
    with duckdb.connect(str(args.database), read_only=True) as database:
        # Ignore forfeits and incomplete series rather than treating absent maps as losses.
        rows = database.execute("""
            WITH complete AS (
                SELECT match_id, COUNT(*) AS map_count,
                    SUM(CASE WHEN score0 > score1 THEN 1 ELSE 0 END) AS a_wins,
                    SUM(CASE WHEN score1 > score0 THEN 1 ELSE 0 END) AS b_wins
                FROM maps GROUP BY match_id
            )
            SELECT m.match_id, mp.game_id, m.utc_timestamp, m.team0_id, m.team1_id,
                   CASE WHEN mp.score0 > mp.score1 THEN m.team0_id ELSE m.team1_id END,
                   ROW_NUMBER() OVER (PARTITION BY m.match_id ORDER BY CAST(mp.game_id AS BIGINT))
            FROM matches m JOIN maps mp USING (match_id) JOIN complete c USING (match_id)
            WHERE m.utc_timestamp >= ? AND m.utc_timestamp < ?
              AND m.listing_status = 'Completed' AND m.is_showmatch = FALSE
              AND c.map_count = m.score0 + m.score1
              AND c.a_wins = m.score0 AND c.b_wins = m.score1
              AND m.score0 <> m.score1 AND GREATEST(m.score0, m.score1) IN (1, 2, 3)
            ORDER BY m.utc_timestamp, m.match_id, CAST(mp.game_id AS BIGINT)
        """, [event["training_start"], event["cutoff"]]).fetchall()
    if not rows:
        raise ValueError("No complete matches in the requested period.")
    output = ROOT / "data/maps.csv"
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["match_id", "map_id", "played_at", "team_a", "team_b", "winner", "map_order"])
        for match, game, played, a, b, winner, order in rows:
            writer.writerow([match, game, played.replace(tzinfo=timezone.utc).isoformat(), a, b, winner, order])
    metadata = {
        "source": SOURCE, "source_documentation": "https://vct-reference.com/dataset",
        "source_terms": "https://vct-reference.com/terms",
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "database_sha256": hashlib.sha256(args.database.read_bytes()).hexdigest(),
        "training_start": event["training_start"], "cutoff_exclusive": event["cutoff"],
        "maps": len(rows), "series": len({row[0] for row in rows}),
        "filter": "Completed, non-showmatch series with all played maps present and consistent with the series score."
    }
    (ROOT / "data/source.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Saved {len(rows)} maps from {metadata['series']} series to {output}")


if __name__ == "__main__":
    main()
