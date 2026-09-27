"""Matplotlib charts for the Explore page -> frontend/public/charts/*.png

Usage:
    python analyses/make_charts.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from train_model import DATA, OUTCOMES, prepare

OUT = Path(__file__).resolve().parent.parent / "frontend" / "public" / "charts"
NAVY, CAROLINA, CREAM, GREY = "#13294b", "#7bafd4", "#f7f4ed", "#b8c2cc"

plt.rcParams.update({
    "figure.facecolor": CREAM, "axes.facecolor": CREAM, "savefig.facecolor": CREAM,
    "axes.edgecolor": NAVY, "axes.labelcolor": NAVY, "text.color": NAVY,
    "xtick.color": NAVY, "ytick.color": NAVY, "font.size": 12, "font.weight": "bold",
    "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 2,
})


WB_TOOLS = "Chart built in Python (pandas, matplotlib) with data retrieved through the World Bank API."
CENSUS_TOOLS = "Survey-weighted rates computed in Python (pandas, NumPy); chart built with matplotlib."
CENSUS_SOURCE = ("Source: US Census Bureau, American Community Survey 1-year PUMS, 2019 and 2021–2023; "
                 "BLS Employment Projections, Table 1.2.\nGraduates aged 22 to 27 with a bachelor's degree. ")


def save(fig, name, note):
    fig.tight_layout()
    fig.text(0.01, 0, note, ha="left", va="top", fontsize=8.5, style="italic",
             fontweight="normal", color=NAVY, alpha=0.75, linespacing=1.5)
    fig.savefig(OUT / name, dpi=160, bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)
    print("wrote", OUT / name)


def neet_by_country(wb):
    """Youth NEET rate by country, latest year, United States highlighted."""
    neet = wb[wb["indicator"] == "SL.UEM.NEET.ME.ZS"]
    year = neet["year"].max()
    latest = neet[neet["year"] == year].set_index("country")["value"].sort_values()
    fig, ax = plt.subplots(figsize=(8, 0.3 * len(latest) + 1.4))
    colors = [CAROLINA if c == "United States" else GREY for c in latest.index]
    ax.barh(latest.index, latest.values, color=colors, edgecolor=NAVY, linewidth=1.2, height=0.65)
    for i, v in enumerate(latest.values):
        ax.text(v + 0.5, i, f"{v:.0f}%", va="center", fontsize=10)
    ax.set_xlim(0, latest.max() * 1.12)
    ax.set_xlabel("% of youth aged 15 to 24 who are NEET")
    ax.margins(y=0.01)
    ax.set_title(f"Youth NEET rate by country, {year}", loc="left", fontsize=15)
    save(fig, "neet_americas.png",
         "Source: World Bank, World Development Indicators (SL.UEM.NEET.ME.ZS), ILO modelled estimates.\n"
         + WB_TOOLS)


def degree_protection(wb):
    """Graduate unemployment minus overall unemployment, latest year per country."""
    latest = (wb[wb["indicator"].isin(["SL.UEM.TOTL.ZS", "SL.UEM.ADVN.ZS"])]
              .sort_values("year").groupby(["country", "indicator"]).last()["value"].unstack().dropna())
    gap = (latest["SL.UEM.ADVN.ZS"] - latest["SL.UEM.TOTL.ZS"]).sort_values()
    fig, ax = plt.subplots(figsize=(8, 0.3 * len(gap) + 1.4))
    colors = [CAROLINA if v > 0 else GREY for v in gap.values]
    ax.barh(gap.index, gap.values, color=colors, edgecolor=NAVY, linewidth=1.2, height=0.65)
    for i, v in enumerate(gap.values):
        ax.text(v + (0.3 if v >= 0 else -0.3), i, f"{v:+.1f}", va="center",
                ha="left" if v >= 0 else "right", fontsize=10)
    ax.axvline(0, color=NAVY, lw=1.5)
    ax.set_xlim(gap.min() - 2, gap.max() + 2.5)
    ax.set_xlabel("Percentage points, graduates minus all workers")
    ax.margins(y=0.01)
    ax.set_title("Where a degree does not lower unemployment", loc="left", fontsize=15)
    save(fig, "degree_unemployment.png",
         "Source: World Bank, World Development Indicators (SL.UEM.TOTL.ZS, SL.UEM.ADVN.ZS).\n"
         "Latest year available for each country, mostly 2023–2025.\n" + WB_TOOLS)


def majors(people):
    """Underemployment by major (US, bachelor's only, ages 22 to 27)."""
    s_ = OUTCOMES["underemployed"](people)
    weighted = (s_["underemployed"] * s_["weight"]).groupby(s_["major"]).sum()
    rate = (weighted / s_["weight"].groupby(s_["major"]).sum() * 100).drop(index="Other", errors="ignore").sort_values()
    fig, ax = plt.subplots(figsize=(8, 0.3 * len(rate) + 1.4))
    ax.barh(rate.index, rate.values, color=CAROLINA, edgecolor=NAVY, linewidth=1.2, height=0.65)
    for i, v in enumerate(rate.values):
        ax.text(v + 1, i, f"{v:.0f}%", va="center", fontsize=10)
    ax.set_xlim(0, 85)
    ax.set_xlabel("% of employed graduates in a job that doesn't need a degree")
    ax.margins(y=0.01)
    ax.set_title("Underemployment by major", loc="left", fontsize=15)
    save(fig, "majors.png", CENSUS_SOURCE + "Underemployed: working in an occupation whose typical "
         "entry requirement is below a bachelor's degree.\n" + CENSUS_TOOLS)


def grads_breakdown(people):
    """What young US grads (bachelor's only) are doing: a horizontal bar chart."""
    p = people[~(people["employed"] & people["degree_share"].isna())]  # ~1% with unmatched job codes
    groups = {
        "Job that needs a degree": p["employed"] & ~p["underemployed"],
        "Job that doesn't need a degree": p["employed"] & p["underemployed"],
        "In school, not working": ~p["employed"] & ~p["unemployed"] & ~p["neet"],
        "Unemployed (looking)": p["unemployed"],
        "Not working, not looking": p["neet"] & ~p["unemployed"],
    }
    shares = [np.average(mask, weights=p["weight"]) * 100 for mask in groups.values()]
    colors = [GREY, CAROLINA, GREY, GREY, GREY]

    fig, ax = plt.subplots(figsize=(8, 4.2))
    y = np.arange(len(groups))[::-1]
    ax.barh(y, shares, color=colors, edgecolor=NAVY, linewidth=1.5, height=0.6)
    for yi, share in zip(y, shares):
        ax.text(share + 1, yi, f"{share:.0f}%", va="center")
    ax.set_yticks(y, list(groups))
    ax.set_xlim(0, 60)
    ax.set_xlabel("% of graduates aged 22 to 27")
    ax.set_title("What young US graduates are doing", loc="left", fontsize=15)
    save(fig, "grads_breakdown.png", CENSUS_SOURCE + "\n" + CENSUS_TOOLS)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    wb = pd.read_csv(DATA / "worldbank_long.csv")
    people = prepare(pd.read_parquet(DATA / "pums_grads.parquet"))
    neet_by_country(wb)
    degree_protection(wb)
    majors(people[people["grad_degree"] == "No"])
    grads_breakdown(people[people["grad_degree"] == "No"])


if __name__ == "__main__":
    main()
