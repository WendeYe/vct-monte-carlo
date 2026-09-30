"""Replay the Champions Paris 2025 playoff bracket with pre-playoff Elo ratings."""

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from src.data import load_maps
from src.plots import plot_chances, plot_sensitivity
from src.ratings import evaluate_series, fit_ratings
from src.tournament import simulate


ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulations", type=int, default=100000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--k", type=float, default=32)
    parser.add_argument("--maps", type=Path, default=ROOT / "data/maps.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "reports")
    parser.add_argument("--sensitivity", action="store_true", help="Also compare Elo K=16,32,64")
    args = parser.parse_args()
    try:
        event = json.loads((ROOT / "data/champions-paris-2025.json").read_text())
        cutoff = datetime.fromisoformat(event["cutoff"])
        start = datetime.fromisoformat(event["validation_start"])
        maps = load_maps(args.maps)
        # Keep the cutoff here even when a user supplies a CSV containing later games.
        training_start = datetime.fromisoformat(event["training_start"])
        maps = [row for row in maps if training_start <= row.played_at < cutoff]
        ratings = fit_ratings(maps, cutoff, args.k)
        opening = [tuple(pair) for pair in event["opening_matches"]]
        rows = simulate(opening, ratings, args.simulations, args.seed)
        evaluation = evaluate_series(maps, start, cutoff, args.k)
        args.output.mkdir(parents=True, exist_ok=True)
        with (args.output / "results.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["team"] + list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows({"team": event["teams"][row["team_id"]], **row} for row in rows)
        summary = {"event": event["name"], "cutoff": event["cutoff"], "simulations": args.simulations,
                   "seed": args.seed, "k": args.k, "maps": len(maps), "evaluation": evaluation,
                   "brier_coin_flip": 0.25, "log_loss_coin_flip": 0.69314718056}
        plot_chances(rows, event["teams"], args.output / "chances.png")
        if args.sensitivity:
            samples = {k: simulate(opening, fit_ratings(maps, cutoff, k), args.simulations, args.seed)
                       for k in (16, 32, 64)}
            plot_sensitivity(samples, event["teams"], args.output / "sensitivity.png")
            summary["sensitivity"] = {str(k): sample for k, sample in samples.items()}
        (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f"Simulation failed: {error}\n")
    print(f"{event['name']} | {args.simulations:,} simulations | cutoff {event['cutoff']}")
    print(f"{'Team':<20} {'Win':>8} {'Final':>8} {'Top 4':>8}")
    for row in rows:
        print(f"{event['teams'][row['team_id']]:<20} {row['win_probability']:>8.1%} "
              f"{row['final_probability']:>8.1%} {row['top_four_probability']:>8.1%}")
    print(f"\nRolling evaluation: {evaluation['series']} series, Brier {evaluation['brier']:.3f} "
          f"(coin flip 0.250), log loss {evaluation['log_loss']:.3f} (coin flip 0.693)")
    print(f"Reports saved to {args.output}")


if __name__ == "__main__":
    main()
