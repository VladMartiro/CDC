"""Data for the game -> frontend/public/game_data.json

Usage:
    python analyses/ai_exposure.py        # first, writes data/ai_exposure_by_major.csv
    python analyses/export_game_data.py

Contents:
    mix     share of young bachelor's graduates by sex x race x born in US. The game averages the
            model over this mix, so the score reflects choices, not the player's identity.
    states  share of young bachelor's graduates living in each state (for "search anywhere")
    second_majors  how common each second major is among graduates who have one (for "Other")
    majors  per-major facts: actual unemployment and underemployment rates (bachelor's, ages 22 to 27)
            and the share working in jobs highly exposed to AI.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from train_model import DATA, OUTCOMES, prepare

OUT = Path(__file__).resolve().parent.parent / "frontend" / "public" / "game_data.json"


def rate(frame, outcome):
    s = OUTCOMES[outcome](frame)
    return round(float(np.average(s[outcome], weights=s["weight"])) * 100, 1) if len(s) else None


def main():
    people = prepare(pd.read_parquet(DATA / "pums_grads.parquet"))
    bachelors = people[people["grad_degree"] == "No"]

    mix = (bachelors.groupby(["sex", "race", "born_us"])["weight"].sum() / bachelors["weight"].sum())
    mix = [{"sex": s, "race": r, "born_us": b, "share": round(float(v), 4)}
           for (s, r, b), v in mix.items() if v >= 0.002]

    states = (bachelors.groupby("state")["weight"].sum() / bachelors["weight"].sum()).round(4).to_dict()

    doubles = bachelors[~bachelors["second_major"].isin(["None", "Other"])]
    second_majors = (doubles.groupby("second_major")["weight"].sum() / doubles["weight"].sum()).round(4)
    second_majors = second_majors.sort_values(ascending=False).to_dict()

    ai = pd.read_csv(DATA / "ai_exposure_by_major.csv").set_index("major")
    majors = {}
    for major, g in bachelors.groupby("major"):
        if major == "Other":
            continue
        majors[major] = {
            "unemployed": rate(g, "unemployed"),
            "underemployed": rate(g, "underemployed"),
            "ai_exposed_share": float(ai.loc[major, "share_high_exposure"]) if major in ai.index else None,
        }

    OUT.write_text(json.dumps({"mix": mix, "states": states, "second_majors": second_majors, "majors": majors}, indent=1))
    print(f"wrote {OUT}: {len(mix)} demographic groups (covering {sum(m['share'] for m in mix):.1%}), "
          f"{len(majors)} majors")


if __name__ == "__main__":
    main()
