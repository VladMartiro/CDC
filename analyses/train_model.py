

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder

DATA = Path(__file__).resolve().parent.parent / "data"

MAJOR_GROUPS = {
    "11": "Agriculture", "13": "Environment & Natural Resources", "14": "Architecture",
    "15": "Area & Ethnic Studies", "19": "Communications", "20": "Communications",
    "21": "Computer & Information Sciences", "22": "Other", "23": "Education",
    "24": "Engineering", "25": "Engineering Technologies", "26": "Languages & Linguistics",
    "29": "Other", "32": "Pre-Law & Legal Studies", "33": "English", "34": "Liberal Arts & Humanities",
    "35": "Other", "36": "Biology & Life Sciences", "37": "Mathematics & Statistics", "38": "Other",
    "40": "Interdisciplinary Studies", "41": "Physical Fitness & Recreation", "48": "Philosophy & Religion",
    "49": "Philosophy & Religion", "50": "Physical Sciences", "51": "Other", "52": "Psychology",
    "53": "Criminal Justice", "54": "Public Policy & Social Work", "55": "Social Sciences",
    "56": "Other", "57": "Other", "59": "Other", "60": "Fine Arts", "61": "Health & Medical",
    "62": "Business", "64": "History",
}

STATES = {
    1: "Alabama", 2: "Alaska", 4: "Arizona", 5: "Arkansas", 6: "California", 8: "Colorado",
    9: "Connecticut", 10: "Delaware", 11: "District of Columbia", 12: "Florida", 13: "Georgia",
    15: "Hawaii", 16: "Idaho", 17: "Illinois", 18: "Indiana", 19: "Iowa", 20: "Kansas",
    21: "Kentucky", 22: "Louisiana", 23: "Maine", 24: "Maryland", 25: "Massachusetts",
    26: "Michigan", 27: "Minnesota", 28: "Mississippi", 29: "Missouri", 30: "Montana",
    31: "Nebraska", 32: "Nevada", 33: "New Hampshire", 34: "New Jersey", 35: "New Mexico",
    36: "New York", 37: "North Carolina", 38: "North Dakota", 39: "Ohio", 40: "Oklahoma",
    41: "Oregon", 42: "Pennsylvania", 44: "Rhode Island", 45: "South Carolina",
    46: "South Dakota", 47: "Tennessee", 48: "Texas", 49: "Utah", 50: "Vermont", 51: "Virginia",
    53: "Washington", 54: "West Virginia", 55: "Wisconsin", 56: "Wyoming", 72: "Puerto Rico",
}

CATEGORICAL = ["major", "second_major", "sex", "race", "born_us", "state", "moved_states", "grad_degree", "year"]
NUMERIC = ["age"]
FEATURES = CATEGORICAL + NUMERIC

EMPLOYED = {1, 2, 4, 5}      # ESR: civilian or armed forces, at work or with a job
IN_LABOR_FORCE = {1, 2, 3, 4, 5}
DEGREE_JOBS = {"Bachelor's degree", "Master's degree", "Doctoral or professional degree"}


def degree_required_share():
    """Share of BLS employment in each 6-digit SOC code whose typical entry education is a bachelor's+."""
    bls = pd.read_excel(DATA / "occupation.xlsx", sheet_name="Table 1.2", header=1)
    bls = bls[bls["Occupation type"] == "Line item"]
    return pd.DataFrame({
        "soc": bls["2025 National Employment Matrix code"].str.replace("-", "", regex=False),
        "emp": pd.to_numeric(bls["Employment, 2025"], errors="coerce").fillna(0),
        "degree": bls["Typical education needed for entry"].isin(DEGREE_JOBS),
    })


def map_socp(codes, bls):
    """PUMS SOCP codes can end in X wildcards (e.g. 1110XX); match them to BLS detailed codes."""
    out = {}
    for code in codes:
        pattern = re.compile("^" + code.replace("X", r"\d").replace("Y", r"\d") + "$")
        hit = bls[bls["soc"].str.match(pattern)]
        if hit.empty:
            hit = bls[bls["soc"].str.startswith(code[:4])]  # fall back to the broad group
        if not hit.empty and hit["emp"].sum() > 0:
            out[code] = float(np.average(hit["degree"], weights=hit["emp"]))
    return out


def prepare(df):
    race = np.select(
        [df["HISP"] > 1, df["RAC1P"] == 1, df["RAC1P"] == 2, df["RAC1P"] == 6],
        ["Hispanic", "White", "Black", "Asian"], "Other / Multiracial",
    )
    us_born_elsewhere = (df["NATIVITY"] == 1) & (df["POBP"] <= 56) & (df["POBP"] != df["ST"])
    out = pd.DataFrame({
        "major": df["FOD1P"].astype("Int64").astype(str).str[:2].map(MAJOR_GROUPS).fillna("Other"),
        "second_major": df["FOD2P"].astype("Int64").astype(str).str[:2].map(MAJOR_GROUPS).fillna("None"),
        "sex": df["SEX"].map({1: "Male", 2: "Female"}),
        "race": race,
        "born_us": df["NATIVITY"].map({1: "Yes", 2: "No"}),
        "state": df["ST"].map(STATES),
        "moved_states": np.where(us_born_elsewhere, "Yes", "No"),  # lives outside the state they were born in
        "grad_degree": np.where(df["SCHL"] >= 22, "Yes", "No"),
        "year": df["year"].astype(str),
        "age": df["AGEP"],
        "weight": df["PWGTP"],
        "household": df["year"].astype(str) + df["SERIALNO"].astype(str),
    })
    esr = df["ESR"]
    employed = esr.isin(EMPLOYED)
    out["in_lf"] = esr.isin(IN_LABOR_FORCE)
    out["employed"] = employed
    out["unemployed"] = esr == 3
    out["neet"] = ~employed & (df["SCH"] == 1)

    socp = df["SOCP"].fillna("").astype(str).str.strip()
    share = map_socp(sorted(set(socp[employed]) - {""}), degree_required_share())
    out["degree_share"] = socp.map(share)
    out["underemployed"] = out["degree_share"] < 0.5
    return out.dropna(subset=["state", "sex"])


OUTCOMES = {
    "unemployed": lambda d: d[d["in_lf"]],
    "neet": lambda d: d,
    "underemployed": lambda d: d[d["employed"] & d["degree_share"].notna()],
}


def models():
    logit = make_pipeline(
        ColumnTransformer([("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=30), CATEGORICAL)],
                          remainder="passthrough"),
        LogisticRegression(max_iter=2000, C=1.0),
    )
    gbm = make_pipeline(
        ColumnTransformer([("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), CATEGORICAL)],
                          remainder="passthrough"),
        HistGradientBoostingClassifier(categorical_features=list(range(len(CATEGORICAL))),
                                       max_depth=4, learning_rate=0.05, max_iter=400,
                                       min_samples_leaf=200, l2_regularization=1.0, random_state=0),
    )
    return {"logistic_regression": logit, "gradient_boosting": gbm}


def calibration_table(y, p, w, bins=10):
    edges = np.unique(np.quantile(p, np.linspace(0, 1, bins + 1)))
    idx = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, len(edges) - 2)
    return [
        {"predicted": round(float(np.average(p[idx == b], weights=w[idx == b])), 4),
         "actual": round(float(np.average(y[idx == b], weights=w[idx == b])), 4)}
        for b in range(len(edges) - 1) if (idx == b).any()
    ]


FAIRNESS_GROUPS = ["race", "sex", "born_us"]


def fairness_table(test, y, p, w):
    """Per-group predicted vs actual rate and AUC on held-out data (calibration-in-the-large by group)."""
    rows = []
    for col in FAIRNESS_GROUPS:
        for group in sorted(test[col].unique()):
            mask = (test[col] == group).to_numpy()
            yg, pg, wg = y[mask], p[mask], w[mask]
            rows.append({
                "attribute": col, "group": group, "n": int(mask.sum()),
                "predicted": round(float(np.average(pg, weights=wg)), 4),
                "actual": round(float(np.average(yg, weights=wg)), 4),
                "auc": round(roc_auc_score(yg, pg, sample_weight=wg), 4) if 0 < yg.sum() < len(yg) else None,
            })
    return rows


def main():
    data = prepare(pd.read_parquet(DATA / "pums_grads.parquet"))
    metrics = {"rows": len(data), "years": sorted(data["year"].unique().tolist()), "outcomes": {}}

    for outcome, subset in OUTCOMES.items():
        d = subset(data)
        y, w = d[outcome].astype(int).to_numpy(), d["weight"].to_numpy()
        train, test = next(GroupShuffleSplit(test_size=0.2, random_state=0).split(d, groups=d["household"]))
        base = float(np.average(y, weights=w))
        result = {"population": len(d), "weighted_rate": round(base, 4),
                  "rate_by_year": {yr: round(float(np.average(g[outcome], weights=g["weight"])), 4)
                                   for yr, g in d.groupby("year")},
                  "models": {}}
        print(f"\n{outcome}: {len(d):,} people, weighted rate {base:.1%}")

        for name, model in models().items():
            model.fit(d.iloc[train][FEATURES], y[train], **{model.steps[-1][0] + "__sample_weight": w[train]})
            p = model.predict_proba(d.iloc[test][FEATURES])[:, 1]
            yt, wt = y[test], w[test]
            m = {
                "auc": round(roc_auc_score(yt, p, sample_weight=wt), 4),
                "brier": round(brier_score_loss(yt, p, sample_weight=wt), 5),
                "brier_baseline": round(brier_score_loss(yt, np.full_like(p, base), sample_weight=wt), 5),
                "log_loss": round(log_loss(yt, p, sample_weight=wt), 5),
                "calibration": calibration_table(yt, p, wt),
                "fairness": fairness_table(d.iloc[test], yt, p, wt),
            }
            result["models"][name] = m
            print(f"  {name:<20} AUC={m['auc']:.3f}  Brier={m['brier']:.4f} (baseline {m['brier_baseline']:.4f})")
        metrics["outcomes"][outcome] = result

    (DATA / "model_metrics.json").write_text(json.dumps(metrics, indent=2))
    print(f"\nwrote {DATA / 'model_metrics.json'}")


if __name__ == "__main__":
    main()
