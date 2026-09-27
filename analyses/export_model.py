"""Export the trained gradient-boosting models so the website can run them in the browser.

Usage:
    python analyses/export_model.py

Output: frontend/public/model.json - every decision tree of the three models (unemployed, NEET,
underemployed), the category lists for each input, and the held-out evaluation metrics.
The browser evaluator (frontend/src/app/model.ts) walks these trees exactly like scikit-learn;
this script checks that a re-implementation of that logic matches sklearn's predictions.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from train_model import CATEGORICAL, DATA, FEATURES, NUMERIC, OUTCOMES, models, prepare

OUT = Path(__file__).resolve().parent.parent / "frontend" / "public" / "model.json"


def export_tree(predictor):
    n = predictor.nodes
    leaf = n["is_leaf"].astype(bool)
    return {
        "feature": n["feature_idx"].tolist(),
        "threshold": np.round(n["num_threshold"], 6).tolist(),
        "missing_left": n["missing_go_to_left"].tolist(),
        "left": np.where(leaf, -1, n["left"].astype(np.int64)).tolist(),  # uint32 in sklearn
        "right": np.where(leaf, -1, n["right"].astype(np.int64)).tolist(),
        "value": np.where(leaf, np.round(n["value"], 7), 0).tolist(),
        "categorical": n["is_categorical"].tolist(),
        "bitset": n["bitset_idx"].tolist(),
        "bitsets": predictor.raw_left_cat_bitsets.tolist(),
    }


def export_outcome(model):
    clf = model.steps[-1][1]
    known, f_idx_map = clf._bin_mapper.make_known_categories_bitsets()
    return {
        "baseline": float(clf._baseline_prediction.ravel()[0]),
        "known": {int(f): known[i].tolist() for f, i in enumerate(f_idx_map) if clf.is_categorical_[f]},
        "trees": [export_tree(p[0]) for p in clf._predictors],
    }


def has_bit(bitset, value):
    return (bitset[value // 32] >> (value % 32)) & 1


def predict_like_browser(spec, x):
    """Same logic as model.ts: walk each tree, sum the leaves, apply the logistic function."""
    raw = spec["baseline"]
    for t in spec["trees"]:
        i = 0
        while t["left"][i] != -1:
            f, v = t["feature"][i], x[t["feature"][i]]
            if np.isnan(v):
                go_left = t["missing_left"][i]
            elif t["categorical"][i]:
                c = int(v)
                known = spec["known"].get(f)
                go_left = has_bit(t["bitsets"][t["bitset"][i]], c) if known and has_bit(known, c) else t["missing_left"][i]
            else:
                go_left = v <= t["threshold"][i]
            i = t["left"][i] if go_left else t["right"][i]
        raw += t["value"][i]
    return 1 / (1 + np.exp(-raw))


def main():
    data = prepare(pd.read_parquet(DATA / "pums_grads.parquet"))
    metrics = json.loads((DATA / "model_metrics.json").read_text())
    out = {"features": FEATURES, "numeric": NUMERIC, "outcomes": {}}

    for outcome, subset in OUTCOMES.items():
        d = subset(data)
        model = models()["gradient_boosting"]
        model.fit(d[FEATURES], d[outcome].astype(int),
                  histgradientboostingclassifier__sample_weight=d["weight"])
        encoder = model.steps[0][1].named_transformers_["cat"]
        out.setdefault("categories", {c: list(v) for c, v in zip(CATEGORICAL, encoder.categories_)})
        spec = export_outcome(model)

        # verify the browser logic against sklearn on a sample of real rows
        sample = d[FEATURES].sample(1500, random_state=0)
        encoded = model.steps[0][1].transform(sample).astype(float)
        mine = np.array([predict_like_browser(spec, row) for row in encoded])
        diff = np.abs(mine - model.predict_proba(sample)[:, 1]).max()
        print(f"{outcome}: {len(spec['trees'])} trees, max difference vs sklearn = {diff:.2e}")
        assert diff < 1e-6

        m = metrics["outcomes"][outcome]["models"]["gradient_boosting"]
        bachelors = d[d["grad_degree"] == "No"]
        spec["national_rate"] = round(float(np.average(bachelors[outcome], weights=bachelors["weight"])) * 100, 1)
        spec["auc"] = m["auc"]
        spec["fairness"] = m["fairness"]
        out["outcomes"][outcome] = spec

    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
