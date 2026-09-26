"""Precompute model predictions for every input combination -> frontend/public/predictions.json.

Usage:
    python analyses/export_predictions.py

Predictions are for a 24-year-old with a bachelor's degree, using the 2023 survey year.
values[] is a flat array in the order major x sex x race x born_us x state x outcome,
each value = percent * 10 (integer, so 123 means 12.3%).
"""

import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from train_model import DATA, FEATURES, OUTCOMES, models, prepare

OUT = Path(__file__).resolve().parent.parent / "frontend" / "public" / "predictions.json"


def main():
    data = prepare(pd.read_parquet(DATA / "pums_grads.parquet"))
    dims = {
        "major": sorted(data["major"].unique()),
        "sex": ["Female", "Male"],
        "race": ["Asian", "Black", "Hispanic", "White", "Other / Multiracial"],
        "born_us": ["Yes", "No"],
        "state": sorted(data["state"].unique()),
    }
    grid = pd.DataFrame(list(itertools.product(*dims.values())), columns=list(dims))
    grid["grad_degree"], grid["year"], grid["age"] = "No", "2023", 24

    preds = {}
    for outcome, subset in OUTCOMES.items():
        d = subset(data)
        model = models()["gradient_boosting"]
        model.fit(d[FEATURES], d[outcome].astype(int),
                  histgradientboostingclassifier__sample_weight=d["weight"])
        preds[outcome] = model.predict_proba(grid[FEATURES])[:, 1]
        print(f"{outcome}: {preds[outcome].min():.1%} - {preds[outcome].max():.1%}")

    values = np.round(np.column_stack([preds[o] for o in OUTCOMES]) * 1000).astype(int).ravel()
    bachelors = data[data["grad_degree"] == "No"]
    national = {o: round(float(np.average(s[o], weights=s["weight"])) * 100, 1)
                for o, s in ((o, f(bachelors)) for o, f in OUTCOMES.items())}

    OUT.write_text(json.dumps({
        "dims": dims, "outcomes": list(OUTCOMES), "national": national,
        "values": values.tolist(),
    }, separators=(",", ":")))
    print(f"wrote {len(grid):,} combinations -> {OUT} ({OUT.stat().st_size / 1e3:.0f} KB)")


if __name__ == "__main__":
    main()
