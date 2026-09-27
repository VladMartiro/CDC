# Analyses

Predict a college student's chance of being **unemployed, NEET, or underemployed** around age 24,
from their major, gender, race/ethnicity, whether they were born in the US, and their state.

## Run order

```
pip install -r requirements.txt openpyxl
python analyses/fetch_worldbank.py   # World Bank indicators -> data/worldbank_*.csv (Explore page)
python analyses/fetch_pums.py        # Census PUMS, ~2.3 GB download -> data/pums_grads.parquet
python analyses/train_model.py       # models + evaluation -> data/model_metrics.json
python analyses/export_model.py      # decision trees -> frontend/public/model.json (runs in the browser)
python analyses/make_charts.py       # matplotlib charts -> frontend/public/charts/*.png
```

`data/occupation.xlsx` (BLS) is downloaded by hand: https://www.bls.gov/emp/tables.htm (occupation.xlsx).

## Definitions

Population: ACS respondents aged 22–27 with a bachelor's degree or higher, not active-duty military,
survey years 2019, 2021, 2022, 2023 (2020 skipped — Census flagged it as experimental).

| Outcome | Rule | Among |
|---|---|---|
| Unemployed | `ESR` = 3 | People in the labor force |
| NEET | Not employed and `SCH` = 1 (not enrolled) | Everyone |
| Underemployed | Job (`SOCP`) where < 50% of BLS employment has a bachelor's+ as typical entry education | The employed |

Features: major group (`FOD1P`), second major (`FOD2P`), sex, race/ethnicity (`RAC1P` + `HISP`),
born in US (`NATIVITY`), state (`ST`), lives outside birth state (`POBP` vs `ST`), graduate degree,
age, survey year. Choices a student controls: major, second major, graduate degree, state. Parents' income is not available for independent adults.

## Status

- [x] World Bank pull (35 countries of the Americas, 52 indicators, 2001–2025)
- [x] Census PUMS pull script
- [x] Labels + BLS mapping (checked on Maryland 2023: 4.4% / 6.0% / 37.4%; 99% of job codes mapped)
- [x] Train + evaluate on national data (296,685 graduates) — results below
- [x] Model runs live in the browser: trees exported to `model.json` (0.6 MB), evaluated by
      `frontend/src/app/model.ts`; matches sklearn to 1e-7
- [x] Fairness check by race, sex, nativity (in `model_metrics.json` and the "Behind the scenes" panel)
- [x] Explore page: odds calculator + "what if" (born abroad, other state), 3 matplotlib charts, references
- [ ] "What if" another country (World Bank rescale)
- [ ] SHAP explanations

## Results (held-out 20% of households; full detail in `data/model_metrics.json`)

| Outcome | Rate | Best model | AUC | Calibrated? |
|---|---|---|---|---|
| Unemployed | 4.6% | Gradient boosting ≈ logistic | 0.66 | Yes, within ~1 pt per decile |
| NEET | 6.8% | Gradient boosting ≈ logistic | 0.63 | Yes |
| Underemployed | 39.7% | Gradient boosting | 0.69 | Yes, within ~2 pts |

Rates match the NY Fed benchmark (5.6% / 42%). AUC is modest because demographics and major only
partly determine an individual's outcome; the model is used for *group probabilities*, which are
well calibrated. Predictions span 1.6–10% (unemployed), 3–12.5% (NEET), 15–65% (underemployed).

## References

- US Census Bureau, American Community Survey 1-year PUMS — https://www.census.gov/programs-surveys/acs/microdata.html
- BLS Employment Projections, Table 1.2 (typical education needed for entry) — https://www.bls.gov/emp/tables.htm
- Federal Reserve Bank of New York, The Labor Market for Recent College Graduates (benchmark: 5.6% unemployed, 42% underemployed, 2026 Q2) — https://www.newyorkfed.org/research/college-labor-market
- World Bank, World Development Indicators / EdStats / JOIN / LAC Equity Lab — https://api.worldbank.org/v2
- ILOSTAT, NEET rate by sex and education — https://sdmx.ilo.org/rest

## Website

```
cd frontend && npm install && npm start      # local: http://localhost:4200
```

Deployed to GitHub Pages by `.github/workflows/deploy-pages.yml` on every push to `main`
(Settings → Pages → Source: GitHub Actions). Live at https://vladmartiro.github.io/CDC/
