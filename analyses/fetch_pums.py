"""Download Census ACS 1-year PUMS person files and keep young college graduates.

Usage:
    python analyses/fetch_pums.py              # 2019, 2021, 2022, 2023
    python analyses/fetch_pums.py --years 2023

Raw zips (~600 MB each) go to data/raw/pums/ (git-ignored).
Output: data/pums_grads.parquet - people aged 22-27 with a bachelor's degree or higher.
2020 is skipped: the Census Bureau flagged its 1-year data as experimental (COVID).
"""

import argparse
import zipfile
from pathlib import Path

import pandas as pd
import requests

URL = "https://www2.census.gov/programs-surveys/acs/data/pums/{year}/1-Year/csv_pus.zip"
DATA = Path(__file__).resolve().parent.parent / "data"
RAW = DATA / "raw" / "pums"

COLUMNS = [
    "SERIALNO", "ST", "STATE", "PWGTP", "AGEP", "SEX", "RAC1P", "HISP", "NATIVITY", "POBP",
    "SCHL", "SCH", "FOD1P", "ESR", "SOCP", "OCCP", "WKHP", "COW", "MIL",
]
NUMERIC = ["PWGTP", "AGEP", "SEX", "RAC1P", "HISP", "NATIVITY", "POBP", "SCHL", "SCH",
           "FOD1P", "ESR", "OCCP", "WKHP", "COW", "MIL"]


def download(year):
    path = RAW / f"csv_pus_{year}.zip"
    if path.exists():
        return path
    RAW.mkdir(parents=True, exist_ok=True)
    print(f"downloading {year} ...")
    with requests.get(URL.format(year=year), stream=True, timeout=120) as r:
        r.raise_for_status()
        tmp = path.with_suffix(".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        tmp.rename(path)
    return path


def extract(year, path):
    frames = []
    with zipfile.ZipFile(path) as z:
        for name in sorted(n for n in z.namelist() if n.endswith(".csv")):
            with z.open(name) as f:
                for chunk in pd.read_csv(f, usecols=lambda c: c in COLUMNS, dtype=str, chunksize=500_000):
                    for c in NUMERIC:
                        chunk[c] = pd.to_numeric(chunk[c], errors="coerce")
                    keep = chunk["AGEP"].between(22, 27) & (chunk["SCHL"] >= 21) & (chunk["MIL"] != 1)
                    frames.append(chunk[keep])
    df = pd.concat(frames, ignore_index=True)
    # 2023 renamed ST -> STATE
    df["ST"] = pd.to_numeric(df.pop("STATE") if "STATE" in df else df["ST"], errors="coerce")
    df = df.drop(columns=[c for c in ("MIL",) if c in df])
    df.insert(0, "year", year)
    print(f"{year}: {len(df):,} graduates aged 22-27")
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", type=int, nargs="+", default=[2019, 2021, 2022, 2023])
    args = parser.parse_args()

    df = pd.concat([extract(y, download(y)) for y in args.years], ignore_index=True)
    df.to_parquet(DATA / "pums_grads.parquet", index=False)
    print(f"wrote {len(df):,} rows -> {DATA / 'pums_grads.parquet'}")


if __name__ == "__main__":
    main()
