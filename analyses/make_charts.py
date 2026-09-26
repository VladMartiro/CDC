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


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=160)
    plt.close(fig)
    print("wrote", OUT / name)


def neet_over_time(wb):
    """Youth NEET rate across the Americas; a few countries highlighted."""
    neet = wb[wb["indicator"] == "SL.UEM.NEET.ME.ZS"]
    highlight = {"United States": NAVY, "Mexico": "#d9822b", "Brazil": "#3a7d44", "Honduras": "#b23a48"}
    fig, ax = plt.subplots(figsize=(8, 5))
    for country, g in neet.groupby("country"):
        if country not in highlight:
            ax.plot(g["year"], g["value"], color=GREY, lw=1, alpha=0.7)
    for country, color in highlight.items():
        g = neet[neet["country"] == country]
        ax.plot(g["year"], g["value"], color=color, lw=3)
        ax.annotate(country, (g["year"].iloc[-1], g["value"].iloc[-1]), xytext=(6, 0),
                    textcoords="offset points", va="center", color=color)
    ax.set_ylabel("% of youth (15–24) who are NEET")
    ax.set_xlim(neet["year"].min(), neet["year"].max() + 5)
    ax.set_xticks(range(2005, 2026, 5))
    ax.set_title("Youth NEET rate across the Americas", loc="left", fontsize=15)
    save(fig, "neet_americas.png")


def degree_protection(wb):
    """Overall unemployment vs unemployment of people with a university degree, latest year."""
    latest = (wb[wb["indicator"].isin(["SL.UEM.TOTL.ZS", "SL.UEM.ADVN.ZS"])]
              .sort_values("year").groupby(["country", "indicator"]).last()["value"].unstack().dropna())
    latest = latest.sort_values("SL.UEM.ADVN.ZS")
    fig, ax = plt.subplots(figsize=(8, 0.34 * len(latest) + 1.5))
    y = np.arange(len(latest))
    ax.hlines(y, latest["SL.UEM.ADVN.ZS"], latest["SL.UEM.TOTL.ZS"], color=GREY, lw=3)
    ax.scatter(latest["SL.UEM.TOTL.ZS"], y, color=GREY, s=60, zorder=3, label="Everyone")
    ax.scatter(latest["SL.UEM.ADVN.ZS"], y, color=NAVY, s=60, zorder=3, label="University degree")
    ax.set_yticks(y, latest.index)
    ax.set_xlabel("Unemployment rate (%)")
    ax.legend(frameon=False, loc="lower right")
    ax.set_title("Does a degree protect you from unemployment?", loc="left", fontsize=15)
    save(fig, "degree_unemployment.png")


def majors(people):
    """Actual unemployment vs underemployment by major (US, bachelor's only, ages 22–27)."""
    rates = {}
    for outcome, subset in OUTCOMES.items():
        s = subset(people)
        weighted = (s[outcome] * s["weight"]).groupby(s["major"]).sum()
        rates[outcome] = weighted / s["weight"].groupby(s["major"]).sum() * 100
    r = pd.DataFrame(rates).drop(index="Other", errors="ignore")
    fig, ax = plt.subplots(figsize=(9, 6.5))
    ax.scatter(r["unemployed"], r["underemployed"], s=70, color=CAROLINA, edgecolor=NAVY, lw=1.5, zorder=3)
    for major, row in r.iterrows():
        ax.annotate(major, (row["unemployed"], row["underemployed"]), xytext=(5, 3),
                    textcoords="offset points", fontsize=8, fontweight="normal")
    ax.set_xlabel("Unemployed (%)")
    ax.set_ylabel("Underemployed: job doesn't need a degree (%)")
    ax.set_title("Young US graduates by major", loc="left", fontsize=15)
    save(fig, "majors.png")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    wb = pd.read_csv(DATA / "worldbank_long.csv")
    people = prepare(pd.read_parquet(DATA / "pums_grads.parquet"))
    neet_over_time(wb)
    degree_protection(wb)
    majors(people[people["grad_degree"] == "No"])


if __name__ == "__main__":
    main()
