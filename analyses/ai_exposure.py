"""How exposed are young graduates' jobs to AI? Joins occupation-level AI exposure scores
to the Census graduates and summarizes by major and by year.

Usage:
    python analyses/ai_exposure.py

Inputs:
    data/ai_exposure_occ_level.csv  Eloundou, Manning, Mishkin & Rock (2023), "GPTs are GPTs",
                                    github.com/openai/GPTs-are-GPTs (data/occ_level.csv).
                                    We use human_rating_beta: share of an occupation's tasks where
                                    a large language model (alone, or with tools built on it) could
                                    cut completion time by at least half.
    data/pums_grads.parquet, data/occupation.xlsx
Output:
    data/ai_exposure_by_major.csv
"""

import re

import numpy as np
import pandas as pd

from train_model import DATA, prepare

HIGH_EXPOSURE = 0.5  # at least half of the job's tasks exposed


def soc_exposure():
    """Average exposure per 6-digit SOC code (O*NET codes like 15-1252.00 -> 151252)."""
    occ = pd.read_csv(DATA / "ai_exposure_occ_level.csv")
    occ["soc"] = occ["O*NET-SOC Code"].str[:7].str.replace("-", "", regex=False)
    return occ.groupby("soc")["human_rating_beta"].mean()


def map_to_pums(codes, exposure):
    """PUMS SOCP codes may end in X wildcards; average the matching detailed codes."""
    out = {}
    for code in codes:
        pattern = re.compile("^" + code.replace("X", r"\d").replace("Y", r"\d") + "$")
        hit = exposure[exposure.index.str.match(pattern)]
        if hit.empty:
            hit = exposure[exposure.index.str.startswith(code[:4])]
        if not hit.empty:
            out[code] = float(hit.mean())
    return out


def weighted(values, weights):
    return float(np.average(values, weights=weights)) if len(values) else np.nan


def main():
    raw = pd.read_parquet(DATA / "pums_grads.parquet")
    people = prepare(raw)
    people["SOCP"] = raw.loc[people.index, "SOCP"].fillna("").astype(str).str.strip()
    workers = people[people["employed"] & (people["SOCP"] != "") & (people["grad_degree"] == "No")].copy()

    exposure = map_to_pums(sorted(workers["SOCP"].unique()), soc_exposure())
    workers["ai_exposure"] = workers["SOCP"].map(exposure)
    workers = workers.dropna(subset=["ai_exposure"])
    workers["high_exposure"] = workers["ai_exposure"] >= HIGH_EXPOSURE
    print(f"matched {len(workers):,} employed bachelor's graduates to an AI exposure score")

    w = workers["weight"]
    print(f"average exposure: {weighted(workers['ai_exposure'], w):.2f}; "
          f"share in high-exposure jobs (>= {HIGH_EXPOSURE}): {weighted(workers['high_exposure'], w):.1%}")
    for yr, g in workers.groupby("year"):
        print(f"  {yr}: high-exposure share {weighted(g['high_exposure'], g['weight']):.1%}")

    rows = []
    for major, g in workers.groupby("major"):
        rows.append({
            "major": major,
            "graduates": len(g),
            "avg_ai_exposure": round(weighted(g["ai_exposure"], g["weight"]), 3),
            "share_high_exposure": round(weighted(g["high_exposure"], g["weight"]) * 100, 1),
            "underemployed_high": round(weighted(g.loc[g["high_exposure"], "underemployed"],
                                                 g.loc[g["high_exposure"], "weight"]) * 100, 1),
            "underemployed_low": round(weighted(g.loc[~g["high_exposure"], "underemployed"],
                                                g.loc[~g["high_exposure"], "weight"]) * 100, 1),
        })
    by_major = pd.DataFrame(rows).sort_values("share_high_exposure", ascending=False)
    by_major.to_csv(DATA / "ai_exposure_by_major.csv", index=False)
    print(by_major.to_string(index=False))


if __name__ == "__main__":
    main()
