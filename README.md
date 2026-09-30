# VCT Monte Carlo

A retrospective simulation of the Champions Paris 2025 playoffs: learn Elo ratings from earlier map results, then play out the real eight-team bracket 100,000 times.

## Paper Rex were favourites. NRG won.

At K=32, the model gave Paper Rex a **50.1%** chance of winning and NRG just **3.9%**. NRG went on to beat FNATIC in the final. The model did not pick the winner.

![Simulated championship probabilities](reports/chances.png)

Changing the Elo update factor tells a more interesting story:

| Elo K | Paper Rex | G2 Esports | NRG |
| --- | ---: | ---: | ---: |
| 16 | 33.3% | 33.3% | 3.7% |
| 32 | 50.1% | 30.5% | 3.9% |
| 64 | 67.7% | 20.0% | 3.6% |

![Sensitivity to the Elo update factor](reports/sensitivity.png)

Larger K makes each new map move the ratings further. In these runs, the rating gap between Paper Rex and G2 grows from less than one point at K=16 to roughly 83 at K=64. Best-of-series probabilities amplify that gap, and winning several series compounds it into a much larger tournament advantage.

NRG stays near 4% across all three settings. So adjusting K alone does not explain their win. An unlikely outcome is still possible, but this baseline also ignores rosters, map vetoes and changes in form that an organization-level rating may miss. The result does not tell us which of those mattered most.

The main takeaway: 100,000 simulations make the calculation stable, not the assumptions correct. The error bars show sampling noise; the K comparison shows how much the model choice matters.

## Method and data

The snapshot contains **2,335 maps from 918 completed series**, from January 2024 to September 25, 2025 (exclusive, UTC). No playoff results enter the ratings. Teams start at 1500; map Elo becomes a BO3/BO5 probability assuming independent, equally likely maps. Ratings stay frozen during simulations of the actual double-elimination bracket, with no final reset. Default seed: 42.

A rolling check on 188 earlier series gives a Brier score of **0.226** and log loss of **0.644**, compared with **0.250** and **0.693** for a coin flip. Each series is predicted before its maps update the ratings. This checks series predictions, not tournament probability calibration; K=32 was not tuned to this event.

Data: [VCT Reference](https://vct-reference.com/dataset), with extraction filters and the source hash in `data/source.json`. Format: [Riot's event guide](https://playvalorant.com/en-us/news/esports/everything-you-need-to-know-champions-paris/). Opening matches: [official bracket](https://valorantesports.com/en-US/tournament/113482263742879102/stage/113482431147251336). Tests replay the fourteen actual playoff outcomes to check routing. See the data provider's [terms](https://vct-reference.com/terms); this is statistical analysis, not a betting tool.

## Run it

Python 3.11+. The bundled CSV works offline.

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py --sensitivity
python -m pytest -q
```

Charts, probabilities and run metadata are saved to `reports/`. To try another setting:

```sh
python main.py --simulations 10000 --seed 7 --k 16 --output reports/quick
```

Core code is in `src/ratings.py` and `src/tournament.py`; `main.py` produces the reports. To re-extract the historical data, run `python scripts/import_data.py --refresh`. Upstream corrections may change that snapshot, so use the committed CSV to reproduce these results.
