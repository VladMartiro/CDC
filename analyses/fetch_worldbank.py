"""Pull World Bank indicators for the 35 countries of the Americas via the v2 API.

Usage:
    python analyses/fetch_worldbank.py                 # 2001-2025, writes to data/
    python analyses/fetch_worldbank.py --start 2005 --end 2024

Outputs (in data/):
    worldbank_long.csv      one row per country / year / indicator
    worldbank_panel.csv     one row per country-year, one column per indicator code
    worldbank_indicators.csv  indicator code, name, database, role
    worldbank_coverage.csv  how many countries / years each indicator actually has

To add an indicator, append it to INDICATORS below. The database id matters:
the API only finds non-WDI codes when you pass the right `source`.
"""

import argparse
import time
from pathlib import Path

import pandas as pd
import requests

API = "https://api.worldbank.org/v2"
OUT_DIR = Path(__file__).resolve().parent.parent / "data"

# World Bank database (source) ids
WDI = 2         # World Development Indicators
EDSTATS = 12    # Education Statistics
LAC_EQUITY = 37 # LAC Equity Lab (youth study/work splits, stops ~2014)
JOIN = 86       # Global Jobs Indicators Database

COUNTRIES = {
    # North America
    "CAN": "Canada", "USA": "United States", "MEX": "Mexico",
    # Central America
    "BLZ": "Belize", "CRI": "Costa Rica", "SLV": "El Salvador", "GTM": "Guatemala",
    "HND": "Honduras", "NIC": "Nicaragua", "PAN": "Panama",
    # Caribbean
    "ATG": "Antigua and Barbuda", "BHS": "Bahamas, The", "BRB": "Barbados", "CUB": "Cuba",
    "DMA": "Dominica", "DOM": "Dominican Republic", "GRD": "Grenada", "HTI": "Haiti",
    "JAM": "Jamaica", "KNA": "St. Kitts and Nevis", "LCA": "St. Lucia",
    "VCT": "St. Vincent and the Grenadines", "TTO": "Trinidad and Tobago",
    # South America
    "ARG": "Argentina", "BOL": "Bolivia", "BRA": "Brazil", "CHL": "Chile", "COL": "Colombia",
    "ECU": "Ecuador", "GUY": "Guyana", "PRY": "Paraguay", "PER": "Peru", "SUR": "Suriname",
    "URY": "Uruguay", "VEN": "Venezuela, RB",
}

# (code, database id, role in the project)
INDICATORS = [
    # --- Target: youth NEET (modeled ILO series has the best coverage) ---
    ("SL.UEM.NEET.ME.ZS", WDI, "target"),
    ("SL.UEM.NEET.FE.ME.ZS", WDI, "target"),
    ("SL.UEM.NEET.MA.ME.ZS", WDI, "target"),
    ("SL.UEM.NEET.ZS", WDI, "target"),  # national estimate, gappier; kept for comparison

    # --- Labor market the player enters ---
    ("SL.UEM.1524.ZS", WDI, "economy"),
    ("SL.UEM.1524.FE.ZS", WDI, "economy"),
    ("SL.UEM.1524.MA.ZS", WDI, "economy"),
    ("SL.TLF.ACTI.1524.ZS", WDI, "economy"),
    ("SL.EMP.VULN.ZS", WDI, "economy"),
    ("SL.UEM.TOTL.ZS", WDI, "economy"),
    ("SL.UEM.ADVN.ZS", WDI, "economy"),  # unemployment among people with a university degree
    ("NY.GDP.PCAP.PP.KD", WDI, "context"),
    ("SI.POV.GINI", WDI, "context"),
    ("SI.POV.DDAY", WDI, "context"),
    ("SP.URB.TOTL.IN.ZS", WDI, "context"),

    # --- Life events ---
    ("SP.ADO.TFRT", WDI, "event"),

    # --- Schooling (national) ---
    ("SE.PRM.CMPT.ZS", WDI, "education"),
    ("SE.SEC.CMPT.LO.ZS", WDI, "education"),
    ("SE.SEC.PROG.ZS", WDI, "education"),
    ("SE.SEC.NENR", WDI, "education"),
    ("SE.TER.ENRR", WDI, "education"),
    ("SE.PRM.UNER.ZS", WDI, "education"),
    ("SE.SEC.UNER.LO.ZS", WDI, "education"),
    ("SE.XPD.TOTL.GD.ZS", WDI, "education"),
    ("SE.XPD.SECO.PC.ZS", WDI, "education"),
    ("SE.SEC.ENRR.UP", EDSTATS, "education"),

    # --- Schooling by wealth / gender (household surveys, sparse) ---
    ("UIS.CR.3", EDSTATS, "equity"),
    ("UIS.CR.3.F", EDSTATS, "equity"),
    ("UIS.CR.3.M", EDSTATS, "equity"),
    ("UIS.CR.3.Q1", EDSTATS, "equity"),
    ("UIS.CR.3.Q5", EDSTATS, "equity"),
    ("UIS.CR.3.Q1.F", EDSTATS, "equity"),
    ("UIS.CR.3.Q1.M", EDSTATS, "equity"),
    ("UIS.CR.3.WPIA", EDSTATS, "equity"),
    ("UIS.CR.2.Q1", EDSTATS, "equity"),
    ("UIS.CR.2.Q5", EDSTATS, "equity"),
    ("UIS.CR.2.WPIA", EDSTATS, "equity"),
    ("UIS.ROFST.H.2.Q1", EDSTATS, "equity"),
    ("UIS.ROFST.H.2.WPIA", EDSTATS, "equity"),
    ("UIS.ROFST.H.3.Q1", EDSTATS, "equity"),
    ("UIS.ROFST.H.3.Q5", EDSTATS, "equity"),
    ("UIS.ROFST.H.3.WPIA", EDSTATS, "equity"),

    # --- Job chances given education (JOIN) ---
    ("JI.EMP.1524.LE.ZS", JOIN, "transition"),
    ("JI.EMP.1524.HE.ZS", JOIN, "transition"),
    ("JI.EMP.1524.FE.ZS", JOIN, "transition"),
    ("JI.EMP.1524.MA.ZS", JOIN, "transition"),
    ("JI.EMP.IFRM.YG.ZS", JOIN, "transition"),

    # --- Study / work / both / neither splits (LAC Equity Lab, 17 countries, to 2014) ---
    ("4.0.nini.15a18", LAC_EQUITY, "outcome_split"),
    ("4.0.nini.19a24", LAC_EQUITY, "outcome_split"),
    ("4.1.nini.19a24", LAC_EQUITY, "outcome_split"),
    ("4.2.nini.19a24", LAC_EQUITY, "outcome_split"),
    ("4.0.stud.19a24", LAC_EQUITY, "outcome_split"),
    ("4.0.work.19a24", LAC_EQUITY, "outcome_split"),
    ("4.0.studwork.19a24", LAC_EQUITY, "outcome_split"),
]


def get_json(url, params, retries=4):
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=60)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError):
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def fetch_indicator(code, source, start, end):
    """Return (rows, indicator name) for one indicator across all COUNTRIES."""
    url = f"{API}/country/{';'.join(COUNTRIES)}/indicator/{code}"
    params = {"source": source, "format": "json", "per_page": 20000, "date": f"{start}:{end}"}
    rows, name, page = [], None, 1
    while True:
        payload = get_json(url, {**params, "page": page})
        # Errors come back as [{"message": [...]}] with no second element
        if len(payload) < 2 or payload[1] is None:
            msg = payload[0].get("message", [{}])[0].get("value", "no data") if payload else "empty"
            print(f"  ! {code}: {msg}")
            return rows, name
        meta, data = payload
        for r in data:
            name = name or r["indicator"]["value"]
            if r["value"] is None:
                continue
            rows.append({
                "iso3": r["countryiso3code"] or r["country"]["id"],
                "year": int(r["date"]),
                "indicator": code,
                "value": float(r["value"]),
            })
        if page >= meta["pages"]:
            return rows, name
        page += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", type=int, default=2001)
    parser.add_argument("--end", type=int, default=2025)
    args = parser.parse_args()

    all_rows, meta_rows = [], []
    for code, source, role in INDICATORS:
        rows, name = fetch_indicator(code, source, args.start, args.end)
        n_countries = len({r["iso3"] for r in rows})
        print(f"{code:<24} db={source:<3} {len(rows):>4} values, {n_countries:>2}/35 countries")
        all_rows.extend(rows)
        meta_rows.append({"indicator": code, "name": name, "database": source, "role": role})

    long = pd.DataFrame(all_rows)
    long.insert(0, "country", long["iso3"].map(COUNTRIES))
    long = long.sort_values(["iso3", "year", "indicator"])

    panel = (
        long.pivot_table(index=["country", "iso3", "year"], columns="indicator", values="value")
        .reindex(columns=[code for code, _, _ in INDICATORS])
        .reset_index()
    )

    coverage = (
        long.groupby("indicator")
        .agg(countries=("iso3", "nunique"), values=("value", "size"),
             first_year=("year", "min"), last_year=("year", "max"))
        .reindex([code for code, _, _ in INDICATORS])
        .fillna(0)
        .astype(int)
        .reset_index()
    )
    coverage["missing_countries"] = coverage["indicator"].map(
        lambda c: " ".join(sorted(set(COUNTRIES) - set(long.loc[long["indicator"] == c, "iso3"])))
    )

    OUT_DIR.mkdir(exist_ok=True)
    long.to_csv(OUT_DIR / "worldbank_long.csv", index=False)
    panel.to_csv(OUT_DIR / "worldbank_panel.csv", index=False)
    pd.DataFrame(meta_rows).to_csv(OUT_DIR / "worldbank_indicators.csv", index=False)
    coverage.to_csv(OUT_DIR / "worldbank_coverage.csv", index=False)

    print(f"\nWrote {len(long)} values -> {len(panel)} country-years x {len(INDICATORS)} indicators in {OUT_DIR}")


if __name__ == "__main__":
    main()
